# Picking from a list of dicts: selectattr, rejectattr and map on Proxmox guests and host facts

Fourth entry in the Shaping data in Ansible series. [Part 1](readable-sudoers-with-dict-kv.md) explains lists, dicts (key–value mappings) and filters (the functions after a `|`). Much of the data Ansible hands you is a list of dicts: the VMs a module returns, the mounts of a host. This entry is about taking part of such a list:
- some of its items, with `select`, `reject`, `selectattr` and `rejectattr`;
- one field of each item, with `map(attribute=…)`.

The examples are Proxmox VE guests and the facts of a PostgreSQL host. Everything below ran with ansible-core 2.21.4.

## Tests, and the four filters that use them

A *test* is a Jinja check that answers yes or no, written after `is`: `x is defined`, `x is match('^pg')`. Jinja is the template language Ansible evaluates inside `{{ }}`. The tests this entry uses:
- **`defined`**: the value exists;
- **`equalto(y)`**, or `==`: the value equals `y`;
- **`ge(y)`**, **`lt(y)`**, and their siblings `gt`, `le`: greater than or equal to, less than…;
- **`in(y)`**: the value is an item of the list `y`, or a substring of the string `y`;
- **`match(regex)`** and **`search(regex)`**: the value matches a *regular expression*, a text pattern. `match` only looks at the start of the value, `search` anywhere in it.

The filters take a test's name as a string, followed by its argument:
- **`select(test, arg)`** keeps the items for which the test is true, and **`reject`** the others. With no test at all, `select` keeps the items that are *truthy*: not empty, zero, `false` or `None`.
- **`selectattr(attr, test, arg)`** and **`rejectattr`** do the same on one attribute of each item, here one key of each dict. With no test, they check that the attribute is truthy.
- **`map(attribute=attr)`** replaces each item by that attribute. A dotted name reaches into a nested dict: `map(attribute='ipv4.address')`.

In Jinja these filters return a *generator*, a sequence computed only when it's read. Older versions of Ansible could print it as `<generator object …>`, which is why examples end with `| list`. In ansible-core 2.21, the result printed and indexed as a list without it. The examples here keep `| list`, so they also work on older versions.

## Proxmox VE guests

*Proxmox VE* runs virtual machines and containers, together called *guests*. Each has a numeric *VMID*, unique in the cluster, a name, which doesn't have to be unique, the *node* (the server) it runs on, and optionally a *pool*, a group of guests. `community.proxmox.proxmox_vm_info` returns them as `proxmox_vms`, a list with one dict per guest. The data here is the output that module's unit test expects in community.proxmox 2.0.0, trimmed to a few fields:

| vmid | type | name | node | status | pool | maxmem |
|---|---|---|---|---|---|---|
| 100 | qemu | `pxe.home.arpa` | pve | running | | 4 GiB |
| 101 | qemu | `test1` | pve2 | stopped | pool1 | 512 MiB |
| 102 | lxc | `test-lxc.home.arpa` | pve | running | | 512 MiB |
| 103 | lxc | `test1-lxc.home.arpa` | pve2 | stopped | pool1 | 512 MiB |
| 104 | lxc | `test-lxc.home.arpa` | pve2 | stopped | pool1 | 512 MiB |
| 105 | lxc | `""` | pve2 | stopped | pool1 | 512 MiB |

`qemu` is a virtual machine, `lxc` a container. Two guests share a name, one has an empty name, and two have no `pool` key at all.

Filters chain, each one working on what the previous one kept. The guests running on `pve`:

```yaml
"{{ proxmox_vms | selectattr('node', 'equalto', 'pve')
  | selectattr('status', 'equalto', 'running') | map(attribute='name') | list }}"
```

That gave `['pxe.home.arpa', 'test-lxc.home.arpa']`. A few more on the same data:

| Expression | Result |
|---|---|
| `rejectattr('status', 'equalto', 'running') \| map(attribute='name')` | `['test1', 'test1-lxc.home.arpa', 'test-lxc.home.arpa', '']` |
| the same, then `\| select` | the same without `''` |
| `selectattr('type', 'equalto', 'qemu') \| selectattr('maxmem', 'ge', 1024 ** 3)` | `pxe.home.arpa` |
| `map(attribute='name') \| select \| unique` | `['pxe.home.arpa', 'test1', 'test-lxc.home.arpa', 'test1-lxc.home.arpa']` |

`select` with no test is the short way to drop empty values, and `unique` drops the repeated `test-lxc.home.arpa`.

### match is anchored, search isn't

| Expression | Result |
|---|---|
| `selectattr('name', 'match', 'test')` | the four names starting with `test` |
| `selectattr('name', 'match', 'lxc')` | `[]` |
| `selectattr('name', 'search', 'lxc')` | `test-lxc.home.arpa`, `test1-lxc.home.arpa`, `test-lxc.home.arpa` |

`match('lxc')` finds nothing because no name *starts* with `lxc`. Use `search` for "contains", and add `$` to anchor the end: `search('\.home\.arpa$')`.

### A key that some items don't have

`selectattr('pool', 'defined')` gave VMIDs 101, 103, 104 and 105, and `rejectattr('pool', 'defined')` gave 100 and 102. Testing the value instead fails the task:

```yaml
"{{ proxmox_vms | selectattr('pool', 'equalto', 'pool1') | list }}"
```

*"object of type 'dict' has no attribute 'pool'"*, on guest 100. `map(attribute='pool')` fails the same way. The fixes:
- `map` takes a `default`: `map(attribute='pool', default='-')` gave `['-', 'pool1', '-', 'pool1', 'pool1', 'pool1']`;
- `selectattr` doesn't, so drop those items first: `selectattr('pool', 'defined') | selectattr('pool', 'equalto', 'pool1')`.

API responses often leave a key out instead of setting it to `null`, so check which keys every item really has.

## Facts of a PostgreSQL host

*Facts* are what Ansible finds out about a host when a play starts, through the `setup` module: its operating system, disks, network interfaces and so on. They're in `ansible_facts`. These came from `pg-prod-1`, a Rocky Linux 9 container prepared for the example: PostgreSQL's data directory, `/var/lib/pgsql`, on a small file system 94 % full, backups on another at 32 %, and a second network interface, `eth1`, set down.

### Interfaces: a list of names, and one fact per name

`ansible_facts.interfaces` is a list of names, `['eth0', 'eth1', 'lo']`. The details of each are a separate fact named after it, `ansible_facts.eth0` and so on. `map('extract', ansible_facts)` looks each name up in `ansible_facts` and gives the list of dicts:

```yaml
interfaces: "{{ ansible_facts.interfaces | map('extract', ansible_facts) | list }}"
```

| Expression | Result |
|---|---|
| `interfaces \| selectattr('active') \| map(attribute='device')` | `['eth0', 'lo']` |
| `interfaces \| rejectattr('active') \| map(attribute='device')` | `['eth1']` |
| `interfaces \| selectattr('active') \| rejectattr('type', 'equalto', 'loopback') \| map(attribute='ipv4.address')` | `['172.17.0.2']` |

`active` is a boolean, so `selectattr('active')` with no test is enough. The last line uses the dotted attribute: each interface's `ipv4` is a dict, and `address` one of its keys.

### Mounts: free space

Each item of `ansible_facts.mounts` has `mount`, `device`, `fstype`, `size_total` and `size_available`, in bytes. The mounts with under 32 MiB free:

```yaml
"{{ ansible_facts.mounts | selectattr('size_available', 'lt', 32 * 1024 ** 2)
  | map(attribute='mount') | list }}"
```

That gave `['/var/lib/pgsql']`. A test compares one attribute with a fixed value, so "under 10 % free", which compares two attributes of the same item, can't be written with `selectattr`. A loop can, with a `when` condition evaluated for each item:

```yaml
- name: Report mounts with under 10 % free
  ansible.builtin.debug:
    msg: "{{ item.mount }}: {{ (100 * item.size_available / item.size_total) | round(2) }} %"
  loop: "{{ ansible_facts.mounts }}"
  when: item.size_available < item.size_total * 0.10
```

It reported `/var/lib/pgsql` at 6.18 %, and `/etc/resolv.conf`, `/etc/hostname` and `/etc/hosts` at 0.13 %. Those three are files that Docker mounts into every container, from a host disk that was nearly full at the time. To leave them out:

```yaml
"{{ ansible_facts.mounts
  | rejectattr('mount', 'in', ['/etc/hosts', '/etc/hostname', '/etc/resolv.conf']) | list }}"
```

### in, with a list and with a string

With a list, `in` is exact membership: `'/etc/host' in ['/etc/hosts']` is false. With a string, it's a substring test: `['/etc/host', '/etc/hosts', '/etc/hosts.allow'] | select('in', '/etc/hosts.allow')` keeps all three.

That second behaviour is behind a bug in Ansible's own *Data manipulation* guide. Its *Find mount point* example picks the mount a path is on with:

```yaml
msg: "{{(ansible_facts.mounts | selectattr('mount', 'in', path) | list | sort(attribute='mount'))[-1]['mount']}}"
```

It keeps every mount whose mount point is a substring of `path`, sorts them, and takes the last one's mount point. On these facts:

| `path` | The guide's way | By relpath |
|---|---|---|
| `/var/lib/pgsql/data/base` | `/var/lib/pgsql` | `/var/lib/pgsql` |
| `/srv/backups/daily` | `/srv/backups` | `/srv/backups` |
| `/srv/backups-old/base.tar` | `/srv/backups` | none |
| `/etc/hosts.allow` | `/etc/hosts` | none |

`/srv/backups-old` isn't inside `/srv/backups`, but the string `/srv/backups` is in `/srv/backups-old/base.tar`. The same goes for `/etc/hosts` and `/etc/hosts.allow`.

A mount point contains a path when the path, relative to it, doesn't go up a level. The `relpath(start)` filter gives that relative path: `/srv/backups/daily | relpath('/srv/backups')` is `daily`, and `/srv/backups-old/base.tar | relpath('/srv/backups')` is `../backups-old/base.tar`. Here the filter runs the other way round, mount point relative to the path, which gives only `..` steps when the mount point contains the path. With part 2's `zip` to keep each mount point next to its result:

```yaml
mount_points: "{{ ansible_facts.mounts | map(attribute='mount') | list }}"
mount_point: "{{ mount_points | zip(mount_points | map('relpath', path))
  | selectattr('1', 'match', '^\\.\\.?(/\\.\\.)*$') | map(attribute='0')
  | sort | last }}"
```

1. `zip` gives `[mount point, relative path]` pairs.
2. `selectattr('1', …)` tests the second item of each pair: an attribute name that is a number indexes a list. The guide uses the same syntax in `hostvars|dictsort|selectattr("1.ansible_host", "defined")`, where `dictsort` has turned every host's variables into a `[name, variables]` pair. The regular expression accepts `.`, `..`, `../..` and so on.
3. `map(attribute='0')` keeps the mount point, and `sort | last` the longest.

For the last two paths, no mount point here contains them, which the table shows as none. On a real host `/` is always mounted and would come out instead. This container's root file system isn't in its facts, so `/` isn't either.

## Which one

- **Items by value:** `select`/`reject` for a list of plain values, `selectattr`/`rejectattr` for a list of dicts. Chain them for "and".
- **One field of each item:** `map(attribute='…')`, dotted for nested dicts, with `default` when some items lack it.
- **A key that may be missing:** `selectattr(key, 'defined')` before any other test on it.
- **Starts with or contains:** `match` is anchored at the start, `search` isn't.
- **`in`:** exact with a list, substring with a string. Don't use it to compare paths.
- **Two attributes of the same item:** a loop with `when`.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/04-picking-from-lists), runs all of the above on the local machine, changing nothing outside its `out/` directory. `picking.yml` reads the Proxmox guests and the facts from `fixtures/` and writes every result above to `out/picking.txt`, including both errors and both ways of finding the mount point. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/test/core.py` (`match`, `search`), `plugins/filter/core.py` (`extract`) and `plugins/filter/mathstuff.py` (`unique`). Jinja 3.1: `filters.py` (`select`, `reject`, `selectattr`, `rejectattr`, `map`) and `tests.py` (`defined`, `equalto`, `ge`, `lt`, `in`).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/complex_data_manipulation.rst`, *Find mount point* and the `dictsort | selectattr("1.ansible_host", …)` example.
- [community.proxmox](https://github.com/ansible-collections/community.proxmox) 2.0.0: `tests/unit/plugins/modules/test_proxmox_vm_info.py`, `EXPECTED_VMS_OUTPUT`.
- The facts were gathered on 2026-10-01 with ansible-core 2.21.4's `setup` module, over community.docker 5.3.0's `docker` connection, from a Rocky Linux 9.8 container. Every result above came from ansible-core 2.21.4 on the same day, on the recorded data. No Proxmox server was involved.
