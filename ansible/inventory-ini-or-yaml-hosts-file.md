# INI or YAML for the hosts file, and why variables stay out of both

Third entry in the Ansible inventory from scratch series. [Item 1](inventory-hosts-groups-all-ungrouped.md) wrote the hosts file, the inventory file that lists hosts and the groups they belong to, in YAML; [item 2](inventory-directory-group-vars-per-role.md) moved its variables into `group_vars/`. Ansible also reads hosts files in *INI*, the older `[section]` and `key=value` format many examples still use. This entry writes the same hosts file in both formats, then the same variables in both, to see where the choice matters. Everything below ran with ansible-core 2.21.4.

## The same hosts file, twice

```ini
jump1

[app]
app1
app2
app3

[postgresql:children]
db

[db]
db1

[backup]
db1
```

- **A host before any section** is in no group of its own, like `jump1` under `all:` in YAML.
- **`[name]`** is a group and the hosts under it.
- **`[name:children]`** lists the groups inside a group, YAML's `children:`.

`ansible-inventory --list`, which prints the whole inventory as JSON, gave byte-for-byte the same output for this file and item 1's `hosts.yml`. Without variables, the two formats describe the same thing, and the choice is taste. The Red Hat Community of Practice's *automation good practices*, which recommend a hosts file without variables, even lean to INI there: it's easier to read when no variable is involved, and easier for automation to edit line by line, with no indentation to get right.

## The same variables, three ways

INI has two places for variables: on the host line, `db1 key=value key=value`, and in a `[group:vars]` section, one `key=value` per line. The example wrote the same eight values on db1's host line, in a `[postgresql:vars]` section, and under db1 in YAML, then printed the value and type each gave:

| Written as | INI host line | INI `:vars` section | YAML |
|---|---|---|---|
| `5432` | `5432` (int) | `5432` (int) | `5432` (int) |
| `true` | `"true"` (str) | `"true"` (str) | `true` (bool) |
| `True` | `true` (bool) | `true` (bool) | `true` (bool) |
| `no` | `"no"` (str) | `"no"` (str) | `false` (bool) |
| `0770` | `"0770"` (str) | `"0770"` (str) | `504` (int) |
| `"16"` | `16` (int) | `"16"` (str) | `"16"` (str) |
| `['10.10.0.1', '127.0.0.1']` | list | list | list |
| `{'max_connections': 200}` | dict | dict | dict |

- **INI values go through Python's `ast.literal_eval`**, a function that reads Python literals: numbers, quoted strings, `True`, lists, dicts. What it can't read stays a string. `true` and `no` aren't Python, so they stayed strings; `True` is, so it became a boolean. `0770` isn't valid Python 3 either: a string.
- **YAML has its own rules.** `true` and `no` are booleans, and `0770`, with its leading zero, is an octal number: 504. A file mode or a version written that way changes value.
- **Quotes don't mean the same thing on an INI host line.** The line is first split into words the way a shell would, which removes the quotes: `"16"` reached `literal_eval` as `16`, a number. In a `:vars` section, the quotes stayed, and `"16"` was a string.
- **The docs are out of date on `:vars`.** The inventory guide, *Defining variables in INI format*, says a value in a `:vars` section is a string. In ansible-core 2.21.4 it went through the same parsing: `5432`, the list and the dict came out typed. The source, `plugins/inventory/ini.py`, calls the same `_parse_value` for both.

That's why the good practices keep variables out of the hosts file, whatever its format: the same text means three different things depending on where it's written. In `group_vars/` files there is one format, YAML, one set of rules, and ansible-lint checks it. Its `yaml` rule flagged `True`, `no` and `0770` in the YAML version; nothing checks an INI file's values. Wherever a variable lives, quote what must stay a string, `"0770"` or `"16"`, and the guide's advice still holds: convert with a filter, such as `| int` or `| bool`, where the type matters.

## A typo that empties the inventory

On an INI host line, spaces separate variables. `db1 postgresql_data_dir=/srv/pg data`, without quotes, ended with a word that isn't `key=value`, and Ansible didn't read the rest of the file, or any of it:
- `ansible-inventory` warned *"Expected key=value host variable assignment, got: data"*, then *"No inventory was parsed, only implicit localhost is available"*, and exited 0.
- A playbook on the `postgresql` group printed *"skipping: no hosts matched"*, and exited 0 as well.

A pipeline would have gone green having touched nothing. `ANSIBLE_INVENTORY_UNPARSED_FAILED=true`, or `unparsed_is_failed = true` under `[inventory]` in `ansible.cfg`, turned it into an error: exit 1, *"No inventory was parsed"*. It's worth setting in any project, whatever the hosts file's format; with several inventory sources, `INVENTORY_ANY_UNPARSED_IS_FAILED` (`ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED`) makes any one of them failing an error, according to its description in `config/base.yml`; the example didn't test it.

## In short

- **Hosts and groups only:** INI or YAML, as you prefer; both gave the same inventory.
- **Variables:** in neither. In `group_vars/` and `host_vars/` YAML files, with strings quoted.
- **If an INI file must hold variables:** know that `true`, `no` and `0770` stay strings, quotes vanish on host lines, and `:vars` values are parsed too.
- **Always:** `unparsed_is_failed = true`, so a broken inventory fails instead of matching no hosts.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/03-ini-or-yaml), holds both hosts files, the three variable layouts and the broken file. `run.sh` compares the hosts files, runs `types.yml` against each variable layout to write db1's values and types to its `out/` directory, and shows what the broken file does to `ansible-inventory` and to a playbook. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*Inventory basics: formats, hosts, and groups*, *Defining variables in INI format*).
- ansible-core 2.21.4: `plugins/inventory/ini.py` (`_parse_value` and `ast.literal_eval`, for host lines and `:vars` alike) and `config/base.yml` (`INVENTORY_UNPARSED_FAILED`, `INVENTORY_ANY_UNPARSED_IS_FAILED`).
- Red Hat Community of Practice, [automation good practices](https://github.com/redhat-cop/automation-good-practices): `inventories/README.adoc`, *Define your inventory as structured directory instead of single file*.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
