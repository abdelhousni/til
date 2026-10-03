# An inventory as a directory: a hosts file without variables, and group_vars per role

Second entry in the Ansible inventory from scratch series. [Item 1](inventory-hosts-groups-all-ungrouped.md) wrote an inventory, the list of hosts Ansible manages sorted into groups, as a single YAML file, and kept its variables out of it. This entry gives those variables a place: an inventory *directory*, with a `group_vars/` directory beside the hosts file. It's the layout the Red Hat Community of Practice's *automation good practices* recommend, and it has a few rules that fail silently. Everything below ran with ansible-core 2.21.4.

## The layout

A *variable* is a named value that tasks and templates read; a *role* is a packaged set of tasks that configures one thing, such as PostgreSQL, and reads its settings from variables named after it, `postgresql_version` or `postgresql_server_conf`. The inventory from item 1, grown into a directory:

```
inventory/
├── hosts.yml
└── group_vars/
    ├── all/ansible.yml
    ├── app/podman.yml
    ├── backup/backup.yml
    └── postgresql/postgresql.yml
```

- **`hosts.yml` is unchanged**: hosts and groups, no variables.
- **`group_vars/<group>/`** holds the variables of every host in that group. Ansible reads it because the inventory source is the directory: `inventory = inventory` in `ansible.cfg`, or `-i inventory`.
- **One file per role** inside it: `postgresql.yml` holds only `postgresql_*` variables, `podman.yml` only `podman_*`. Ansible doesn't care about the names, only about the directory; the good practices name each file after the role it steers, so that a role's `defaults/main.yml`, where it declares its variables with their default values, can be copied in and edited. They reserve `ansible.yml` for Ansible's own settings, such as how to connect.

`group_vars/postgresql/postgresql.yml`:

```yaml
postgresql_version: "16"
postgresql_server_conf:
  port: 5432
  max_connections: 200
```

The example's playbook printed the role variables each host received:

```
app1:
  podman_firewall: [{"port": "8080/tcp", "state": "enabled"}]
  podman_registries_conf: {"unqualified-search-registries": ["registry.example.org"]}
db1:
  backup_keep: 7
  backup_schedule: "daily"
  postgresql_server_conf: {"port": 5432, "max_connections": 200}
  postgresql_version: "16"
jump1:
  (no role variables)
```

`db1` got the `postgresql` group's variables although the hosts file lists it under `db`: `db` is a child of `postgresql`, and item 1 showed that a host of a child group is a host of its parent. `jump1`, in no group of its own, got only `all`'s connection settings, from `all/ansible.yml`.

Why bother, rather than writing the variables in `hosts.yml`:
- **Finding a setting** is a matter of group and role: PostgreSQL's settings for the database servers are in `group_vars/postgresql/postgresql.yml`, nowhere else.
- **Changes stay small**: adding an app server touches the hosts file only; changing a port touches one variable file.
- **Secrets get their own file**, which can be encrypted on its own; [this entry](what-ansible-vault-actually-encrypts.md) explains what Ansible Vault encrypts.

## Which files Ansible reads

The inventory guide, *Organizing host and group variables*, says Ansible reads *"all the files in these directories in lexicographical order"*, with the extensions `.yml`, `.yaml`, `.json` or none. ansible-core's loader, `parsing/dataloader.py`, adds the details, and the example tested each one with a small inventory of its own, printed with `ansible-inventory --host db1`.

| Layout | Result |
|---|---|
| `group_vars/postgresql.yml` beside `group_vars/postgresql/` | the file is never read |
| `group_vars/postgres/`, for a group called `postgresql` | never read, and no warning |
| `9-base.yml` and `10-upgrade.yml` set the same variable | `9-base.yml`'s value wins |
| a `~` backup, a hidden `.postgresql.yml`, a `notes.md` | all three skipped |
| a subdirectory, `tuning/memory.yml` | read |
| a `README` with no extension | the inventory fails to load |

- **A directory hides a file of the same name.** The loader tries the group's name with no extension first, finds the directory, and stops looking. `postgresql.yml` beside it is ignored, even at `-vvv`.
- **A misspelled directory is just ignored.** `group_vars/` can hold directories for groups that don't exist, and Ansible doesn't say so. The variables simply aren't there.
- **Lexicographical means as text.** The files are sorted as strings, so `10-…` comes before `9-…`, and when two files set the same variable, the later one replaces it: `9-base.yml` won. Pad the numbers, `09-` and `10-`, if order matters; better, don't set one variable in two files.
- **Only names ending in `~`, starting with `.`, or with another extension are skipped.** A file with no extension counts as YAML. A `README` written as prose made `ansible-inventory` and `ansible-playbook` fail with *"YAML parsing failed: Mapping values are not allowed in this context"*, which names neither the file nor the group, at any verbosity. Call it `README.md`.

## In short

- **Inventory as a directory**: `hosts.yml` with hosts and groups only, `group_vars/<group>/` beside it.
- **One file per role** in each group's directory, holding only that role's variables.
- **Never** a `group_vars/<group>.yml` next to a `group_vars/<group>/`, nor two files setting the same variable.
- **Check names**: a directory for a group that doesn't exist is silently ignored, and `ansible-inventory --host <host>` shows what a host actually gets.
- **Notes go in `.md` files**; a file without an extension is read as YAML.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/02-inventory-directory), holds this inventory, with every host connecting locally. `vars.yml` writes each host's role variables to its `out/` directory, and `run.sh` runs it, then prints what Ansible makes of each of the five layouts in `pitfalls/`. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*Organizing host and group variables*).
- ansible-core 2.21.4: `parsing/dataloader.py` (`find_vars_files` and `_get_dir_vars_files`: the name without extension tried first, the sort, the skipped names) and `plugins/vars/host_group_vars.py`.
- Red Hat Community of Practice, [automation good practices](https://github.com/redhat-cop/automation-good-practices): `inventories/README.adoc`, *Define your inventory as structured directory instead of single file*.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
