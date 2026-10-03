# Checking what Ansible sees: ansible-inventory --graph, --list and --host

Sixth entry in the Ansible inventory from scratch series. Items [1](inventory-hosts-groups-all-ungrouped.md) to [4](inventory-connection-variables-ssh-docker-local.md) built an inventory, the list of hosts Ansible manages sorted into groups, with its variables in [`group_vars/` directories](inventory-directory-group-vars-per-role.md). This entry breaks it on purpose, three ways, and finds each mistake with `ansible-inventory`, the command that prints the inventory as Ansible understood it. Each of its views shows something and hides something else. Everything below ran with ansible-core 2.21.4.

## The broken inventory

The same stack as before, jump1, app1 to app3, and db1 in `db` under `postgresql` and in `backup`, with three mistakes:
- **A host in the wrong group**: `app3` written under `db`, beside `db1`, instead of under `app`.
- **A misspelled directory**: `group_vars/backups/` for a group called `backup`.
- **A forgotten override**: `group_vars/db/postgresql.yml`, left over from a test, sets `postgresql_version: "15"`, while `group_vars/postgresql/` says `"16"`.

`ansible-inventory` needs one of three actions, `--graph`, `--list` or `--host`; the inventory comes from `ansible.cfg` or `-i`, as for `ansible-playbook`.

## --graph: the tree

`--graph` prints the groups and their hosts as a tree; [item 1](inventory-hosts-groups-all-ungrouped.md) used it to check the groups:

```
@all:
  |--@ungrouped:
  |  |--jump1
  |--@app:
  |  |--app1
  |  |--app2
  |--@postgresql:
  |  |--@db:
  |  |  |--db1
  |  |  |--app3
  |--@backup:
  |  |--db1
```

`app3` under `db` is the first mistake, plain to see. It's also the mistake no variable view shows well: app3 simply gets the database settings and none of app's.

The tree also lists every group that exists, and there's no `backups` in it. Asking for that branch, `--graph backups` (`--graph` takes a group name to print only its branch), says so:

```
[ERROR]: Pattern must be valid group name when using --graph
```

That's the second mistake. Ansible never reads a `group_vars/` directory that matches no group, and never warns ([item 2](inventory-directory-group-vars-per-role.md) showed it); so when a variable is missing, check that its group exists before checking the file.

## --graph --vars: who sets what

`--vars` adds variables to the tree. For the `postgresql` branch, connection variables left out here:

```
@postgresql:
  |--@db:
  |  |--db1
  |  |  |--{postgresql_server_conf = {'port': 5432, 'max_connections': 200}}
  |  |  |--{postgresql_version = 15}
  |  |--app3
  |  |  |--{postgresql_server_conf = {'port': 5432, 'max_connections': 200}}
  |  |  |--{postgresql_version = 15}
  |  |--{postgresql_version = 15}
  |--{postgresql_server_conf = {'port': 5432, 'max_connections': 200}}
  |--{postgresql_version = 16}
```

Each host shows its merged variables, and each group, at the end of its branch, the variables its own `group_vars/` set: `db` says 15, `postgresql` says 16, and the hosts get 15. That's the third mistake, and the view that finds it, because it shows where both values come from. The inventory guide explains the winner: *"A child group's variables have higher precedence (they override) than a parent group's variables."*

The values are printed the way Python prints them, so `"15"`, a string, shows as `15`, without quotes.

## --host: one host, merged

`--host db1` prints the variables db1 ends up with, as JSON (*JavaScript Object Notation*, the brace-and-quote format), already merged:

```json
{
    "ansible_connection": "local",
    "ansible_python_interpreter": "{{ ansible_playbook_python }}",
    "postgresql_server_conf": {
        "max_connections": 200,
        "port": 5432
    },
    "postgresql_version": "15"
}
```

This is where the second mistake shows from the other side: db1 is in `backup`, and has no `backup_*` variable. It hides where each value came from, which `--graph --vars` shows.

The values aren't rendered: `ansible_python_interpreter` is still the *Jinja* expression `{{ ansible_playbook_python }}`, the template syntax Ansible evaluates only when a task uses the variable. `ansible-inventory` shows what the files say, not what a task would get.

## --list: everything, per host or per group

`--list` prints the whole inventory. By default it's JSON with every host's merged variables under `_meta.hostvars`, and groups with only their hosts and children; `--yaml` prints YAML instead. Limited to db1 (`--limit` restricts a command to the hosts matching a pattern, a host or group name here), `--list --yaml` gave:

```yaml
all:
  children:
    backup:
      hosts:
        db1: {}
    postgresql:
      children:
        db:
          hosts:
            db1:
              ansible_connection: local
              ansible_python_interpreter: '{{ ansible_playbook_python }}'
              postgresql_server_conf:
                max_connections: 200
                port: 5432
              postgresql_version: '15'
```

db1's variables appear once, under the first group that lists it, and `db1: {}` elsewhere. Under `backup`, that reads as "db1 has no variables", which isn't what it means; ansible-core's `cli/inventory.py` does it on purpose, *"avoid defining host vars more than once"*.

`--export` turns the view around: each group gets the variables of its own `group_vars/`, and hosts get only their own, here none:

```yaml
all:
  children:
    app:
      vars:
        podman_firewall: ...
    backup:
      hosts:
        db1: {}
    postgresql:
      children:
        db:
          hosts:
            db1: {}
          vars:
            postgresql_version: '15'
      vars:
        postgresql_server_conf: ...
        postgresql_version: '16'
  vars:
    ansible_connection: local
    ansible_python_interpreter: '{{ ansible_playbook_python }}'
```

The option's help says it: *"represent in a way that is optimized for export, not as an accurate representation of how Ansible has processed it"*. It's the view to copy into another inventory; it hides which value each host ends up with. `app` stayed, with its variables and no hosts, although the limit excluded every one of them.

`--output <file>` writes the result to a file instead of the screen. `--toml` prints TOML, another configuration format, but only with an extra Python library: *"The Python library "tomli-w" is required when using the TOML output format."* ansible-core doesn't install it.

## --limit: only --list obeys it

The help says `--graph` and `--host` ignore `--limit`, and they did: `--graph --limit app` printed the full tree, and `--host db1 --limit app` printed db1 although db1 isn't in `app`. `--list --limit app` did apply it, with an odd result (the JSON condensed here):

```json
"all": {"children": ["ungrouped", "app", "postgresql", "backup"]},
"app": {"hosts": ["app1", "app2"]},
"postgresql": {"children": ["db"]}
```

`db`, `backup` and `ungrouped`, left without hosts, lost their own entries but are still named as children.

## What ansible-inventory doesn't see

- **The implicit localhost.** [Item 1](inventory-hosts-groups-all-ungrouped.md) showed the `localhost` Ansible creates when a play targets it. `--host localhost` answered, with `ansible_connection: local` and the controller's own Python, while `--list --limit localhost` printed `{}` and `--graph` doesn't list it.
- **`group_vars/` beside a playbook.** The example's playbook lives in `playbooks/`, next to a `group_vars/all/backup.yml` setting `backup_keep: 30`. The playbook saw it on every host, `db1: postgresql_version=15, backup_keep=30`, but `ansible-inventory --host db1` didn't show it: `ansible-inventory` has no playbook. The inventory guide: *"not all Ansible commands have a playbook (for example, `ansible` or `ansible-console`). For those commands, you can use the `--playbook-dir` option to provide the directory on the command line."* `--host db1 --playbook-dir playbooks` added `"backup_keep": 30`, and the guide says those variables *"override the variables that it sources relative to the inventory source"*.

## In short

- **`--graph`** for groups: a host in the wrong group, a group that doesn't exist (`--graph <group>` fails).
- **`--graph --vars <group>`** for where a value comes from: each group's own variables, and what each host ends up with.
- **`--host <host>`** for one host's merged variables, unrendered, ignoring `--limit`.
- **`--list`** for everything, merged per host; **`--export`** per group, as written. `--yaml` prints a host's variables only once.
- **Add `--playbook-dir`** when playbooks have their own `group_vars/`; the implicit localhost only answers `--host`.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/06-ansible-inventory), holds the broken inventory and the playbook with its own `group_vars/`. `run.sh` runs every command above and writes what the playbook sees to its `out/` directory. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `cli/inventory.py` (the options and their help, the `--limit` handling, the `--yaml` host variables printed once, `--export`) and the `INVENTORY_EXPORT` entry of `config/base.yml`.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*Inheriting variable values: group variables for groups of groups*, the child group's precedence; *Organizing host and group variables*, `--playbook-dir`).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
