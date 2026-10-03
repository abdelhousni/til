# Several inventories at once: -i dir/, load order, and which source wins

Fourteenth entry in the Ansible inventory from scratch series. [Item 2](inventory-directory-group-vars-per-role.md) turned the inventory into a directory, and [item 11](targeting-hosts-static-and-dynamic-inventory.md) put a second YAML file and a `constructed` source in it, merged into one set of hosts before any pattern applies. This entry is about what happens when those sources disagree: the order Ansible loads them in, which value wins, what a directory skips, and where `group_vars/` applies once two directories are combined. Everything below ran with ansible-core 2.21.4.

An *inventory source* is anything given to `-i` (or to `inventory =` in `ansible.cfg`): a file, a directory, or a comma-separated list of hosts. Ansible hands each one to its *inventory plugins* in turn, `host_list`, `script`, `auto`, `yaml`, `ini` and `toml` by default (`INVENTORY_ENABLED` in `config/base.yml`), and the first plugin that accepts the source parses it. A directory isn't parsed itself: each file in it becomes a source of its own.

## One directory, a static file and a script

The example's `inventory/` holds the prod hosts in `10-prod.yml` and the staging hosts in `20-staging.py`. That second file is an *inventory script*: an executable program that Ansible runs with `--list` and that prints the hosts and groups as JSON. It stands in for a CMDB or a cloud API.

```python
INVENTORY = {
    "app": {"hosts": ["stg-app1"]},
    "db": {"hosts": ["stg-db1"]},
    "staging": {"hosts": ["stg-app1", "stg-db1"]},
    "_meta": {"hostvars": {}},
}
```

`ansible-inventory --graph -vvv` names each source it parsed and the plugin that took it:

```
Parsed .../inventory/10-prod.yml inventory source with yaml plugin
Parsed .../inventory/20-staging.py inventory source with script plugin
```

The graph has both halves in the same groups: `app` holds app1, app2 and stg-app1. The `script` plugin accepts a file only when it's executable. Without the execute bit, the same file went on to the `ini` plugin, which failed on the first line of Python; Ansible warned *Unable to parse …/20-staging.py as an inventory source*, loaded `10-prod.yml`, and the run had no staging hosts at all. A `git clone` keeps the bit only if it was committed, so check `git ls-files -s`: mode `100755`.

## What a directory skips

The directory also holds `README.md`, `notes.txt` and `old-run.retry`, and `-vvv` doesn't mention them: they're skipped before any plugin sees them, silently. The rules are in `lib/ansible/inventory/manager.py`: names starting with `.`, the `host_vars`, `group_vars` and `vars_plugins` directories, and names matching `INVENTORY_IGNORE_EXTS` (`inventory_ignore_extensions` in `ansible.cfg`). Its default is `.pyc`, `.pyo`, `.swp`, `.bak`, `~`, `.rpm`, `.md`, `.txt`, `.rst`, `.orig`, `.cfg` and `.retry`. `INVENTORY_IGNORE_PATTERNS` (`inventory_ignore_patterns`) adds regular expressions, and is empty by default. Subdirectories are read, recursively.

A `README` without an extension is not skipped. In [item 2](inventory-directory-group-vars-per-role.md), the same file inside `group_vars/` made every command fail. Here it's a source like any other: the `yaml` plugin accepts files with no extension and failed (*Mapping values are not allowed in this context*), then the `ini` plugin failed (*Expected key=value host variable assignment, got: directory*), and Ansible warned and went on with the other sources, exit 0. With `ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED=true`, or `any_unparsed_is_failed = true` under `[inventory]`, the same run exited 1. [Item 3](inventory-ini-or-yaml-hosts-file.md) set its sibling, `unparsed_is_failed`, which only fails when no source at all could be parsed.

## Two sources, one host: the last loaded wins

In `conflicts/`, `10-hosts.yml` sets `app_port: 8080` and `app_workers: 4` on group `app`, and `pg_version: 15`, `pg_max_connections: 100` on host db1. `20-override.yml` sets `app_port: 9090` on `app`, `pg_max_connections: 200` on db1, and also puts db1 in `prod`. The variables sit in the sources here, against the series' own advice, because which source wins is the question.

| Host | Result |
|---|---|
| app1 | `app_port=9090, app_workers=4` |
| db1 | `pg_max_connections=200, pg_version=15`, groups `db,prod` |

The later source overwrote the keys it set, and only those: `app_workers` and `pg_version` stayed. Group memberships add up. The docs put it as *"If you define a variable multiple times, Ansible overwrites the previous value. The last definition wins."* One thing does stay with the first source: db1's `inventory_file` magic variable, the file that defined the host, was `10-hosts.yml`.

## Load order: names sort as text, -i in the order given

Ansible loads the files of a directory in `sorted()` order. The docs say *"alphabetically sorted order"*, which hides that digits sort as characters too. In `name-order/`, the override was renamed `9-override.yml`, to load before `10-hosts.yml` and let it win. It loaded after: `10-hosts.yml` starts with `1`, which comes before `9`, and db1 still got `pg_max_connections=200`. [Item 2](inventory-directory-group-vars-per-role.md) found the same inside a group's directory. Prefixes of the same width, `10-`, `20-`, `90-`, sort the way they read.

Separate `-i` options load in the order given: `-i conflicts/10-hosts.yml -i conflicts/20-override.yml` gave db1 200, and the reverse gave 100.

## Two directories: group_vars/ applies to every host

[Item 5](inventory-environments-directories-or-groups.md) quoted the docs' way of reaching both environments at once, `-i staging -i production`. In the example, `environments/prod/` and `environments/staging/` each have a hosts file and a `group_vars/`: `group_vars/all/env.yml` sets `env: prod` in one and `env: staging` in the other, and `prod/group_vars/app/` sets `app_replicas: 3`, meant for the prod app hosts.

| Command | app1 | stg-app1 |
|---|---|---|
| `-i environments/prod -i environments/staging` | `env=staging`, `app_replicas=3` | `env=staging`, `app_replicas=3` |
| `-i environments/staging -i environments/prod` | `env=prod`, `app_replicas=3` | `env=prod`, `app_replicas=3` |

A `group_vars/` directory beside a source is not scoped to that source's hosts. Once the sources are parsed, `lib/ansible/inventory/manager.py` reads the `group_vars/` and `host_vars/` beside every source and applies them by group name to the merged inventory, the later source winning (`get_vars_from_inventory_sources` in `lib/ansible/vars/plugins.py`). So `all` from the last directory sets `env` for every host, and the staging app host gets the prod replicas. Combining environment directories is safe only when they share no group names with different values, and `all` is always shared. Item 5's single inventory with `prod` and `staging` groups is the layout made for runs that need both.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/14-several-inventories), holds the directory with the script, the conflicting sources, the two environment directories and the two pitfalls. `run.sh` prints the sources each command parsed and with which plugin, the files skipped, the variables each case gives, and what the non-executable script and the `README` do. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*Passing multiple inventory sources*, *Managing inventory load order*, *Managing inventory variable load order*).
- ansible-core 2.21.4: `lib/ansible/inventory/manager.py` (`IGNORED_ALWAYS`, `parse_source`), `lib/ansible/config/base.yml` (`INVENTORY_ENABLED`, `INVENTORY_IGNORE_EXTS`, `INVENTORY_IGNORE_PATTERNS`, `INVENTORY_ANY_UNPARSED_IS_FAILED`), `lib/ansible/constants.py` (`REJECT_EXTS`), `lib/ansible/plugins/inventory/script.py` and `yaml.py` (`verify_file`), `lib/ansible/vars/plugins.py`.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
