# json_query or native filters: part 4's Proxmox selections written in JMESPath

Thirteenth entry in the Shaping data in Ansible series. Many answers online pick items from Ansible data with `json_query`, a filter from the community.general collection that runs a *JMESPath* query. JMESPath is a query language for JSON data, with its own syntax for filtering and reshaping. [Part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md) did the same selections with filters built into Ansible, `selectattr`, `rejectattr` and `map`. This entry runs part 4's selections on its recorded Proxmox guests both ways, to see where `json_query` helps and where it gets in the way. Everything below ran with ansible-core 2.21.4, community.general 13.4.0 and jmespath 1.1.0.

## A library to install first

`json_query` runs the query with the `jmespath` Python library, which ansible-core doesn't install. It must be on the *controller*, the machine running `ansible-playbook`; without it, the filter fails with *"You need to install "jmespath" prior to running json_query filter"*. The example repository had to add it to its requirements. Native filters need nothing.

## The same selections, side by side

The guests are part 4's six, with `node`, `status`, `type`, `maxmem` and, on four of them, `pool`:

```yaml
# running on pve
native:   selectattr('node', 'equalto', 'pve') | selectattr('status', 'equalto', 'running') | map(attribute='name')
jmespath: "[?node=='pve' && status=='running'].name"
# not running
native:   rejectattr('status', 'equalto', 'running') | map(attribute='name')
jmespath: "[?status!='running'].name"
# in a pool
native:   selectattr('pool', 'defined') | map(attribute='vmid')
jmespath: "[?pool].vmid"
# in pool1
native:   selectattr('pool', 'defined') | selectattr('pool', 'equalto', 'pool1') | map(attribute='vmid')
jmespath: "[?pool=='pool1'].vmid"
# VMs with 1 GiB or more
native:   selectattr('type', 'equalto', 'qemu') | selectattr('maxmem', 'ge', 1024**3) | map(attribute='name')
jmespath: "[?type=='qemu' && maxmem >= `1073741824`].name"
# names containing lxc
native:   selectattr('name', 'search', 'lxc') | map(attribute='name')
jmespath: "[?contains(name, 'lxc')].name"
```

Each gave the same result both ways. The JMESPath reads:
- `[? … ]` keeps the items for which the condition is true, and `.name` takes one key of each;
- `&&` and `!=` are *and* and *not equal*;
- `contains()` is one of JMESPath's built-in functions.

Two differences already show:
- **A missing key isn't an error.** Part 4's `selectattr('pool', 'equalto', 'pool1')` failed on the guests without a pool, so the native version needs `selectattr('pool', 'defined')` first. In JMESPath, a missing key is `null`, and `null == 'pool1'` is just false.
- **Reshaping is shorter.** `{running: [?status=='running'].vmid, stopped: [?status=='stopped'].vmid}` builds a dict in one expression; [part 12](groupby-lists-mergeby-proxmox-guests.md) needed `groupby`, `zip` and `dict()` for the same `{'running': [100, 102], 'stopped': [101, 103, 104, 105]}`. `[?node=='pve'].{id: vmid, n: name}` renames keys as it goes.

## Missing keys disappear from projections

| Every guest's pool | Result |
|---|---|
| `map(attribute='pool', default='-')` | `['-', 'pool1', '-', 'pool1', 'pool1', 'pool1']` |
| `[*].pool` | `['pool1', 'pool1', 'pool1', 'pool1']` |

JMESPath leaves `null` out of the result of `[*].key`, which it calls a *projection*: six guests in, four values out. The list no longer lines up with the guests, so zipping it back with their names, as part 2 does, pairs the wrong items. The native version keeps one value per guest.

## Three kinds of quotes, and only one is a number

Inside a query, each quote means something different:

| Query | Means | Result |
|---|---|---|
| ``[?vmid==`100`].name`` | the JSON number 100 | `['pxe.home.arpa']` |
| `[?vmid=='100'].name` | the string `'100'` | `[]` |
| `[?vmid=="100"].name` | the key named `100` | `[]` |
| `[?vmid==100].name` | nothing: a parse error | *invalid token: Parse error at column 8* |

Backticks hold a JSON literal, single quotes a string, and double quotes a key name, an *identifier*. The two wrong ones return an empty list, with no error, the same silent type mismatch [part 6](set-operations-union-difference-proxmox-drift.md) found in set operations. All of this sits inside a YAML string, which has its own quotes: the community.general guide, *Selecting JSON data*, recommends backticks for literals partly because they don't clash with YAML's.

## Ansible variables don't go into the query

JMESPath has no variables, and jmespath 1.1.0 doesn't accept `$` for the root of the data either (*"Unknown token $"*). The usual way to compare with an Ansible variable is to build the query as a string:

```yaml
"{{ vms | community.general.json_query(\"[?node=='\" ~ node ~ \"'].vmid\") }}"
```

That works until the value holds a single quote. With `node: "o'brien"`, the query became `[?node=='o'brien'].vmid`, and failed: *"Unclosed ' delimiter"*. It's the same mistake as building SQL by string concatenation. Passing the value as a JSON literal is safer: ``'[?node==`' ~ (node | to_json) ~ '`].vmid'`` gave ``[?node==`"o'brien"`].vmid``, which ran and found no guest. It still breaks on a value containing a backtick, which `to_json` doesn't escape. A native filter takes the variable as an argument, `selectattr('node', 'equalto', node)`, and quoting never comes up.

## to_json | from_json is no longer needed

The Ansible docs, *Selecting JSON data: JSON queries*, say that with `starts_with` and `contains` *"you have to use `to_json | from_json` filter for correct parsing of data structure"*. JMESPath's functions check the type of their arguments, and Ansible's strings, read from YAML, aren't Python's plain `str`. community.general now handles that itself: `json_query` adds Ansible's own string, list and dict types to the list of types jmespath accepts, citing [ansible/ansible#85600](https://github.com/ansible/ansible/issues/85600). `contains(name, 'lph')` on a name defined in YAML worked directly. The round trip is only needed with older versions of the collection.

## Which one

- **Filtering and taking one key:** native filters. They need no extra library, take Ansible variables as arguments, and their errors point at Ansible data, not at a query string.
- **Reshaping, several conditions or renamed keys in one step:** `json_query` is shorter. Write literals in backticks, and keep the query in a variable of its own so that YAML's quotes stay out of it.
- **Values from Ansible variables:** native filters, or `to_json` between backticks.
- **One value per item, even when a key is missing:** native `map(attribute=…, default=…)`; a JMESPath projection drops the missing ones.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/13-json-query), runs all of the above on the local machine, changing nothing outside its `out/` directory. `query.yml` runs each selection both ways on part 4's recorded guests, records whether they agree, and records the quoting pitfalls. Its CI runs it on every push and compares the output with the expected one.

## Sources

- community.general 13.4.0: `plugins/filter/json_query.py` (the missing-library error and the type map) and `docs/docsite/rst/filter_guide_selecting_json_data.rst`.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Selecting JSON data: JSON queries*.
- [JMESPath specification](https://jmespath.org/specification.html): literals, raw strings, identifiers, projections and functions. jmespath 1.1.0, the Python library.
- [community.proxmox](https://github.com/ansible-collections/community.proxmox) 2.0.0: the recorded `proxmox_vm_info` output, from part 4.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine. No Proxmox server was involved.
