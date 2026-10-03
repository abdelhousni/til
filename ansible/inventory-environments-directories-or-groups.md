# Environments in an Ansible inventory: separate directories, or prod and staging as groups

Fifth entry in the Ansible inventory from scratch series. [Item 2](inventory-directory-group-vars-per-role.md) turned the inventory into a directory, with a hosts file and `group_vars/`, and [item 4](inventory-connection-variables-ssh-docker-local.md) told Ansible how to reach each host. Most real setups have the same stack more than once: an *environment* is one complete copy of it, such as *prod*, the servers users depend on, and *staging*, a smaller copy where changes are tried first. This entry writes a PostgreSQL and application stack for prod and staging two ways, one inventory directory per environment, then one inventory with `prod` and `staging` groups, and tests what each layout targets and which value a host gets. Everything below ran with ansible-core 2.21.4.

## Groups named for what the hosts do

Both layouts keep the groups of the earlier items: `app` for the application servers, `db` for the database servers. These are *functional groups*, named for the job the hosts do, not for where they are or which environment they serve. The Ansible docs' *General tips* page puts it this way: *"If you create groups named for the function of the nodes in the group, for example, `webservers` or `dbservers`, your playbooks can target machines based on function."* A play written for `hosts: app` then works in any environment that has an `app` group.

The hosts:

| Environment | `app` | `db` |
|---|---|---|
| prod | `app1`, `app2` | `db1` |
| staging | `stg-app1` | `stg-db1` |

Two variables differ between environments: `app_log_level` (`warning` in prod, `debug` in staging) and `postgresql_max_connections` (200 and 50). Every host connects locally, as in item 2.

## One inventory directory per environment

```
inventories/
├── prod/
│   ├── hosts.yml
│   └── group_vars/
│       ├── all/ansible.yml
│       ├── app/app.yml
│       └── db/postgresql.yml
└── staging/
    ├── hosts.yml
    └── group_vars/
        ├── all/ansible.yml
        ├── app/app.yml
        └── db/postgresql.yml
```

Each directory is a complete inventory, as in item 2, with the same group names and its own hosts and values. `inventories/staging/hosts.yml`:

```yaml
all:
  children:
    app:
      hosts:
        stg-app1:
    db:
      hosts:
        stg-db1:
```

`inventories/staging/group_vars/app/app.yml` holds `app_log_level: debug`, prod's holds `warning`. You pick the environment with `-i`, the option that names the inventory. The example's playbook, `app.yml`, runs on `hosts: app` and records the hosts it reached with the value each got:

```
-i inventories/prod, hosts: app
  app1: app_log_level=warning
  app2: app_log_level=warning
-i inventories/staging, hosts: app
  stg-app1: app_log_level=debug
```

Nothing in the staging inventory can reach a prod host. That's the point the docs make, in *Example: One inventory per environment*: *"it is harder to, for example, accidentally change the state of nodes inside the "test" environment when you wanted to update some "staging" servers."* The same page lays out `inventories/production/` and `inventories/staging/` in its sample directory layout. The *General tips* page adds a second reason: *"all vault passwords used in an inventory need to be available when using that inventory. If an inventory contains both production and development environments, developers using that inventory would be able to access production secrets."* ([This entry](what-ansible-vault-actually-encrypts.md) explains what Ansible Vault encrypts.)

The cost: every group and every variable file exists once per environment, and nothing keeps the copies in step.

## One inventory with prod and staging groups

The other layout puts both environments in one inventory and adds a group per environment. Each host is in one functional group and one environment group:

```yaml
all:
  children:
    app:
      hosts:
        app1:
        app2:
        stg-app1:
    db:
      hosts:
        db1:
        stg-db1:
    prod:
      hosts:
        app1:
        app2:
        db1:
    staging:
      hosts:
        stg-app1:
        stg-db1:
```

`group_vars/` then has a directory for `prod` and `staging` beside `app` and `db`: `app/app.yml` holds a value for every app server, `app_log_level: info`, and `prod/app.yml` and `staging/app.yml` hold each environment's own.

### Targeting one environment

The same `hosts: app` play, on this inventory:

```
-i single, hosts: app (both environments)
  app1: app_log_level=warning
  app2: app_log_level=warning
  stg-app1: app_log_level=debug
```

That's the risk of this layout: `hosts: app` means every app server, in every environment. Two ways keep a run to one environment, both written with a *host pattern*, the expression `hosts:` and `--limit` accept, which the *Patterns* guide documents:

- **`--limit staging`** on the command line restricts the play's hosts to the `staging` group.
- **`hosts: app:&staging`** in the play: `&` is the pattern's intersection, *"any hosts in webservers that are also in staging"* in the guide's table.

```
-i single --limit staging, hosts: app
  stg-app1: app_log_level=debug
-i single, hosts: app:&staging
  stg-app1: app_log_level=debug
```

Both depend on someone writing them every time. A misspelled limit at least stops the run: `--limit stagign` printed a warning, *"Could not match supplied host pattern, ignoring: stagign"*, then *"Specified inventory, host pattern and/or --limit leaves us with no hosts to target."* and exited 1. Forgetting the limit altogether gives no message: the play just runs on prod too.

## Which group wins a variable

`app1` is in `app`, which sets `app_log_level: info`, and in `prod`, which sets `warning`. The inventory guide gives the order, from lowest to highest: the `all` group, a parent group, a child group, the host. `app` and `prod` are both direct children of `all`, so neither is a parent of the other; for that case the guide says: *"By default, Ansible merges groups at the same parent/child level in alphabetical order. Variables from the last group that Ansible loads overwrite variables from the previous groups."* ansible-core's `inventory/helpers.py` sorts a host's groups by `(g.depth, g.priority, g.name)`, where *depth* is how far a group is below `all`.

What `ansible-inventory --host` printed for each host of the single inventory:

| Host | `app_log_level` | `postgresql_max_connections` |
|---|---|---|
| `app1` | `"warning"` | `200` |
| `db1` | `"warning"` | `200` |
| `stg-app1` | `"debug"` | `50` |
| `stg-db1` | `"debug"` | `50` |

- **The environment won**, but only because `prod` and `staging` sort after `app` and `db`. Not because it's the environment.
- **An environment group's variables reach all its hosts.** `db1` got `app_log_level` and `app1` got `postgresql_max_connections`, because both are in `prod`. Harmless for a role that never reads them; worth knowing when listing a host's variables.

Three small inventories in the example tested the edge. Each has `app1` in `prod`, setting `app_log_level: warning`, and in a group called `web`, setting `info`:

| Layout | `app1`'s `app_log_level` |
|---|---|
| `prod` and `web`, nothing else | `"info"`: `web` sorts after `prod` and wins |
| `ansible_group_priority: 10` on `prod` in the hosts file | `"warning"`: `prod` wins |
| `ansible_group_priority: 10` in `group_vars/prod/` | `"info"`, and `ansible_group_priority: 10` listed as an ordinary variable |

`ansible_group_priority` is the guide's way to change the order among groups at the same level: *"The larger the number, the later Ansible merges the group, giving it higher priority. This variable defaults to `1` if you do not set it."* It adds: *"You can set `ansible_group_priority` only in an inventory source, not in `group_vars/`."* The run confirmed it: in `group_vars/` it changed nothing. In ansible-core, `inventory/group.py` treats it as a priority in `set_variable`, which the YAML hosts file parser, `plugins/inventory/yaml.py`, calls for each group variable; `plugins/vars/host_group_vars.py`, which reads `group_vars/`, never calls it. So the one environment variable that has to be in the hosts file is this one, which breaks item 2's rule of a hosts file without variables.

With separate directories the question doesn't come up: there is no environment group, and each environment's `group_vars/app/` holds its own value.

## Which one

- **Separate directories** when a run must never reach the other environment by mistake, or when environments have different secrets. It's the layout both Ansible docs pages recommend.
- **One inventory with environment groups** when a run has to see both, for example to compare them, and every play is written with `&prod` or `&staging`, or run with `--limit`. The docs offer another way to combine both for a one-off: *"`ansible-playbook get_logs.yml -i staging -i production`"*, two inventories at once.

## In short

- **Name groups for what the hosts do**: `app`, `db`. The same play then works in every environment.
- **One inventory directory per environment**, same group names in each, chosen with `-i`: a staging run can't reach prod.
- **One inventory with `prod` and `staging` groups**: `hosts: app` hits both. Use `--limit staging` or `hosts: app:&staging` every time.
- **Same-level groups merge by name**: `prod` beats `app`, but a group named `web` beats `prod`. `ansible_group_priority` changes that only in the hosts file, never in `group_vars/`.
- **Check** with `ansible-inventory --host <host>`.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/05-environments), holds both layouts, with every host connecting locally, and the three precedence inventories. `run.sh` runs `app.yml` (`hosts: app`) and `app_staging.yml` (`hosts: app:&staging`) against each layout, tries a misspelled `--limit`, and prints the variables each host gets. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*How variables are merged*, *Passing multiple inventory sources*, *Example: One inventory per environment*), `inventory_guide/intro_patterns.rst` (the intersection pattern), `tips_tricks/ansible_tips_tricks.rst` (*Group inventory by function*, *Separate production and staging inventory*) and `tips_tricks/sample_setup.rst`.
- ansible-core 2.21.4: `inventory/helpers.py` (`sort_groups`), `inventory/group.py` (`set_variable`, `ansible_group_priority`), `plugins/inventory/yaml.py` and `plugins/vars/host_group_vars.py`.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
