# groupby, groupby_as_dict and lists_mergeby: Proxmox guests by node, and joined to what the team declares

Twelfth entry in the Shaping data in Ansible series. [Part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md) picked items out of a list of dicts, Proxmox VE's guests as `community.proxmox.proxmox_vm_info` reports them. This entry does two more things with the same list:
- **group it**: the guests of each *node*, a physical server of the Proxmox cluster, or of each status;
- **merge it with another list**: what the team declares about each guest, its owner and backup schedule, joined to the guest by its VMID.

Three filters do this: Jinja's own `groupby`, and `groupby_as_dict` and `lists_mergeby` from the community.general collection. Everything below ran with ansible-core 2.21.4 and community.general 13.4.0, on part 4's six recorded guests:

| VMID | Name | Node | Status | Pool |
|---|---|---|---|---|
| 100 | `pxe.home.arpa` | pve | running | none |
| 101 | `test1` | pve2 | stopped | pool1 |
| 102 | `test-lxc.home.arpa` | pve | running | none |
| 103 | `test1-lxc.home.arpa` | pve2 | stopped | pool1 |
| 104 | `test-lxc.home.arpa` | pve2 | stopped | pool1 |
| 105 | (empty) | pve2 | stopped | pool1 |

## groupby returns pairs, not a dict

`guests | groupby('node')` gave a list of two items, one per node, sorted by node name. Each item is a pair: the value grouped on, called `grouper`, and the `list` of guests that have it. Its type, from the `type_debug` filter, was `GroupTuple`; it works like a 2-item list, so `first` gives the grouper and `last` the guests:

```
[('pve', [{… vmid 100 …}, {… vmid 102 …}]),
 ('pve2', [{… vmid 101 …}, {… 103 …}, {… 104 …}, {… 105 …}])]
```

That's convenient to loop over, but not to look up: there is no `groups['pve']`. To get a dict, pass the pairs to `dict()`, Python's dict constructor, which Jinja makes available. Here with each list of guests turned into a list of VMIDs first, with [part 2](lists-and-dicts-dict2items-items2dict-zip.md)'s `zip`:

```yaml
by_node: "{{ guests | groupby('node') }}"
vmids_by_node: "{{ dict(by_node | map('first')
  | zip(by_node | map('last') | map('map', attribute='vmid') | map('list'))) }}"
```

That gave `{'pve': [100, 102], 'pve2': [101, 103, 104, 105]}`, and the same by status, `{'running': [100, 102], 'stopped': [101, 103, 104, 105]}`.

**Case is ignored by default.** On three items with the statuses `running`, `Running` and `stopped`, `groupby('status')` gave two groups, `running` with two items and `stopped` with one. `case_sensitive=true` gave three.

### default doesn't work in ansible-core 2.21

Guests 100 and 102 have no `pool` key. Jinja's `groupby` has a `default` argument for that case, documented since Jinja 3.0, and it worked in plain Jinja 3.1.6 and in ansible-core 2.18.19. In ansible-core 2.21.4, `guests | groupby('pool', default='(none)')` failed:

> object of type 'dict' has no attribute 'pool'

It's a known bug, [ansible/ansible#86827](https://github.com/ansible/ansible/issues/86827), reported against 2.20 and still open on 2026-10-02, with a fix proposed in [ansible/ansible#86858](https://github.com/ansible/ansible/pull/86858) but not merged. Until it is, give every guest the default before grouping, with [part 5](subelements-versus-product-quadlet-volumes-pg-hba.md)'s `product` and [part 3](combine-recursive-list-merge-postgresql-quadlets.md)'s `combine`, the default on the left so that a guest's own `pool` wins:

```yaml
by_pool: "{{ [{'pool': '(none)'}] | product(guests) | map('combine') | groupby('pool') }}"
```

That gave `{'(none)': [100, 102], 'pool1': [101, 103, 104, 105]}`.

## groupby_as_dict: one item per key, or an error

When each value appears at most once, `community.general.groupby_as_dict` gives a dict straight away, each key mapped to its one item instead of a list. VMIDs are unique, so `guests | community.general.groupby_as_dict('vmid')` worked, and `(… )[104].name` was `test-lxc.home.arpa`.

Names aren't unique. Guests 102 and 104 are both `test-lxc.home.arpa`, on different nodes, which is why part 2 recommended the VMID as a key. `groupby_as_dict('name')` failed:

> Multiple sequence entries have attribute value 'test-lxc.home.arpa'

That's the filter's design, from its source: it refuses duplicates rather than keeping one silently. It also fails on an item without the key, *"Attribute not contained in element #3 of sequence"*, where `#3` counts from 0. Its documentation sends you back to `groupby` when values repeat.

## lists_mergeby: joining two lists on a key

The team keeps what Proxmox doesn't know, in `vars/declared.yml`:

```yaml
declared_guests:
  - vmid: 100
    owner: infra
    backup: {schedule: daily, keep: [daily-7]}
  - vmid: 101
    owner: dev
    backup: {schedule: weekly}
  - vmid: 103
    owner: dev
  - name: pg1       # VMID not known yet
    owner: data
```

`community.general.lists_mergeby` merges the dicts of several lists that share a value for one key, the *index*:

```yaml
merged: "{{ guests | community.general.lists_mergeby(declared_guests, 'vmid') }}"
```

`[guests, declared_guests] | community.general.lists_mergeby('vmid')`, with the lists in a list, gave the same result. Each guest got its declared keys:

```
100 | pxe.home.arpa | running | infra
101 | test1 | stopped | dev
102 | test-lxc.home.arpa | running | -
103 | test1-lxc.home.arpa | stopped | dev
104 | test-lxc.home.arpa | stopped | -
105 |  | stopped | -
```

Three things the result doesn't say:
- **An item without the index is dropped.** `pg1` has no `vmid`, and it isn't in the result: four declared guests went in, six guests came out, with no error or warning. The source skips any dict whose keys don't include the index. Check for it before merging, for example with `rejectattr('vmid', 'defined')` from part 4.
- **The result is sorted by the index**, whatever the input order.
- **That sort needs comparable values.** With one declared VMID typed as the string `"105"`, the filter failed: *"'<' not supported between instances of 'str' and 'int'"*. Python can't order a string and a number. At least that one is loud; [part 6](set-operations-union-difference-proxmox-drift.md) shows the same mismatch silently breaking set operations. Convert with `int` first ([part 9](forcing-types-extra-vars-conditionals.md)).

### recursive and list_merge, as in combine

Each merge uses `combine`'s merge function, with the same two options, which part 3 explains. A third list overrides how long guest 100's backups are kept:

```yaml
backup_overrides:
  - vmid: 100
    backup: {keep: [weekly-4]}
```

| `lists_mergeby(…, 'vmid', …)` | Guest 100's `backup` |
|---|---|
| default | `{'keep': ['weekly-4']}` |
| `recursive=true` | `{'schedule': 'daily', 'keep': ['weekly-4']}` |
| `recursive=true, list_merge='append'` | `{'schedule': 'daily', 'keep': ['daily-7', 'weekly-4']}` |

By default the later list's `backup` replaced the whole dict, and the daily schedule was lost. As with `combine`, the list given last wins.

## Which one

- **A loop over groups:** `groupby(attribute)`, and `dict()` when you need to look a group up. Pass `case_sensitive=true` if case matters.
- **Items without the attribute:** combine a default into each item first; `default=` fails on ansible-core 2.20 and 2.21 until [ansible/ansible#86827](https://github.com/ansible/ansible/issues/86827) is fixed.
- **A unique key, such as a VMID:** `community.general.groupby_as_dict(key)`. Its error on a duplicate is a feature.
- **Joining lists on a key:** `community.general.lists_mergeby(…, key)`, after checking that every item has the key, with the same type everywhere. `recursive=true` for nested dicts.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/12-grouping-and-merging), runs all of the above on the local machine, changing nothing outside its `out/` directory. `group.yml` groups part 4's recorded guests every way above, errors included, and `merge.yml` joins `vars/declared.yml` to them. Its CI runs both on every push and compares the output with the expected one.

## Sources

- Jinja 3.1.6: the built-in `groupby` filter (`grouper` and `list`, `default`, `case_sensitive`).
- community.general 13.4.0: `plugins/filter/groupby_as_dict.py`, `plugins/filter/lists_mergeby.py` (the skipped items, the sort by index, `merge_hash`), and `docs/docsite/rst/filter_guide_abstract_informations_grouping.rst`.
- [ansible/ansible#86827](https://github.com/ansible/ansible/issues/86827), *ansible.builtin.groupby filter: default value not working*, and its proposed fix [ansible/ansible#86858](https://github.com/ansible/ansible/pull/86858), both open on 2026-10-02.
- [community.proxmox](https://github.com/ansible-collections/community.proxmox) 2.0.0: the recorded `proxmox_vm_info` output, from part 4.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine, except the `default` comparison, run with ansible-core 2.18.19 and plain Jinja 3.1.6. No Proxmox server was involved.
