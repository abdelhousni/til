# Set operations on lists: declared Proxmox guests against the cluster, and why the order changes between runs

Sixth entry in the Shaping data in Ansible series. *Drift* is the gap between what a configuration declares and what actually exists. Finding it means comparing two lists:
- what is declared but missing, to create;
- what exists but isn't declared, the strays, to investigate or remove.

ansible-core has five filters for this, from set theory: `unique`, `union`, `intersect`, `difference` and `symmetric_difference`. The example compares the Proxmox VE guests a cluster should have with the ones it reports. Everything below ran with ansible-core 2.21.4.

## The five filters on Proxmox guests

[Part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md) used six Proxmox guests, with VMIDs 100 to 105, from the output that `community.proxmox.proxmox_vm_info` returns. The VMID is each guest's unique number ([part 2](lists-and-dicts-dict2items-items2dict-zip.md) explains why it beats the name as a key). The declared list has a guest not created yet, 106, and 101 twice by mistake:

```yaml
declared_vmids: [106, 100, 101, 104, 101]
actual_vmids: "{{ proxmox_vms | map(attribute='vmid') | list }}"   # [100, 101, 102, 103, 104, 105]
```

| Expression | Means | Result |
|---|---|---|
| `declared_vmids \| unique` | the list without repeats | `[106, 100, 101, 104]` |
| `declared_vmids \| difference(actual_vmids)` | declared, not on the cluster | `[106]` |
| `actual_vmids \| difference(declared_vmids)` | on the cluster, not declared | `[105, 102, 103]` |
| `declared_vmids \| intersect(actual_vmids)` | in both | `[104, 100, 101]` |
| `declared_vmids \| symmetric_difference(actual_vmids)` | in one but not the other | `[102, 103, 105, 106]` |
| `declared_vmids \| union(actual_vmids)` | in either | `[100, 101, 102, 103, 104, 105, 106]` |

- **`difference` depends on the direction.** `a | difference(b)` keeps what's in `a` and not in `b`. Both directions are needed: one gives the guests to create, the other the strays.
- **`symmetric_difference` mixes the two.** It answers "is there any drift?" in one list, but not which side each item came from.
- **Every result drops duplicates.** 101 appears once in `intersect` although it's declared twice. The docs, *Selecting from sets or lists*, say so: *"all of the following filters imply uniqueness"*.

## The order isn't the order you gave

`strays` came out as `[105, 102, 103]`, neither sorted nor in the cluster's order. The source explains why. In ansible-core's `plugins/filter/mathstuff.py`, the four two-list filters are Python set operations, for example `list(set(a) - set(b))` for `difference`. A Python *set* is an unordered collection that keeps each item once. It finds items by their *hash*, a number computed from the value, and the order you get back follows the hashes, not the input. `unique` is the exception: it keeps the order in which items first appear.

For integers the hash is the number itself, so the order is odd but the same on every run. **For strings it changes from one run to the next.** Python computes string hashes with a random seed chosen when each process starts, unless the `PYTHONHASHSEED` environment variable fixes it. Every `ansible-playbook` run is a new process. Four runs of the same expression on the guests' names:

```yaml
"{{ declared_names | union(actual_names) }}"
```

```
['pg1', 'pxe.home.arpa', 'test-lxc.home.arpa', 'test1', 'test1-lxc.home.arpa']
['test-lxc.home.arpa', 'test1-lxc.home.arpa', 'pg1', 'pxe.home.arpa', 'test1']
['test-lxc.home.arpa', 'test1-lxc.home.arpa', 'test1', 'pxe.home.arpa', 'pg1']
['test-lxc.home.arpa', 'test1-lxc.home.arpa', 'pg1', 'pxe.home.arpa', 'test1']
```

Three different orders in four runs, with nothing changed. A task that writes this list into a file, a monitoring configuration or an inventory, changes the file on most runs. Ansible then reports the task as *changed* and runs its *handlers*, the tasks that only run on a change, such as a service restart. With `| sort` at the end, the list and the file were identical in every run.

**Sort the result of a set operation before writing it anywhere,** or before comparing it with something that has an order.

Items that can't go into a set, such as dicts, take a fallback in the same source file that keeps the first list's order: `proxmox_vms | difference(proxmox_vms[:2])` returned the guests 102 to 105, in order.

## A VMID is not "101"

The comparison is exact, type included. VMIDs from `proxmox_vm_info` are integers. Declared as strings, which is how they arrive from a form, a CSV file or an extra var on the command line, nothing matches:

| Declared | `… \| difference(actual_vmids) \| sort` |
|---|---|
| `["106", "100", "101", "104"]` | `['100', '101', '104', '106']`: all four "missing" |
| `["106", "100", "101", "104"] \| map('int')` | `[106]` |

There's no error or warning: the integer 101 and the string `"101"` are just different items. Convert one side with `map('int')` or `map('string')` before comparing.

## Which one

- **To create:** `declared | difference(actual)`.
- **To investigate or remove:** `actual | difference(declared)`.
- **Anything different at all:** `symmetric_difference`, then the two `difference`s to see which side.
- **Order matters:** add `| sort`. Only `unique` keeps the input order.
- **Values from outside Ansible:** check both lists hold the same type. The `type_debug` filter shows a value's type, for example `int` or `str`.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/06-set-operations), runs all of the above on the local machine, changing nothing outside its `out/` directory. `drift.yml` compares the declared guests in `vars/declared.yml` with part 4's recorded data and writes every result to `out/`. `run.sh` runs it twice more with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`, standing for two separate runs, and shows the unsorted file of names differ while the sorted one doesn't. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/mathstuff.py` (`unique`, `union`, `intersect`, `difference`, `symmetric_difference`, and their fallback for unhashable items).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Selecting from sets or lists (set theory)*.
- Python documentation: [`PYTHONHASHSEED`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED) and [set types](https://docs.python.org/3/library/stdtypes.html#set-types-set-frozenset).
- [community.proxmox](https://github.com/ansible-collections/community.proxmox) 2.0.0: `tests/unit/plugins/modules/test_proxmox_vm_info.py`, `EXPECTED_VMS_OUTPUT`, as recorded for part 4.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine, with the recorded Proxmox data. No Proxmox server was involved.
