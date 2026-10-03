# Targeting hosts with patterns, --limit and constructed groups

Eleventh entry in the Ansible inventory from scratch series. [Item 1](inventory-hosts-groups-all-ungrouped.md) put hosts into groups, and [item 5](inventory-environments-directories-or-groups.md) kept prod and staging in one inventory, where `hosts: app` runs on both. This entry is about choosing which hosts a command or a play runs on. A *host pattern* is the expression that does it: the `hosts:` line of a play, the first argument of the `ansible` command, and the value of `--limit` all take one. Patterns work on the inventory once Ansible has merged every source into one set of hosts and groups, so they don't care whether a host came from a YAML file or from a dynamic plugin such as [the Foreman one](foreman-dynamic-inventory-plugin.md). Everything below ran with ansible-core 2.21.4.

## The inventory

One inventory directory, three sources, read in file-name order:

- `10-hosts.yml`: `app` holds app1, app2 and stg-app1; `db` holds db1 and stg-db1; `prod` holds app1, app2 and db1; `staging` holds stg-app1 and stg-db1.
- `20-extra.yml`: a second YAML file that adds app3 to `app`, in no environment group.
- `30-constructed.yml`: the `constructed` plugin, which builds groups from variables (below).

`group_vars/prod/` and `group_vars/staging/` set `env: prod` and `env: staging`. Every host connects locally, so nothing needs a server.

## The patterns

`ansible <pattern> --list-hosts` prints the hosts a pattern matches and runs nothing: the way to check a pattern before a playbook uses it.

| Pattern | Means | Matched |
|---|---|---|
| `app` | one group | app1 app2 stg-app1 app3 |
| `app:db`, or `app,db` | union: in either | app1 app2 stg-app1 app3 db1 stg-db1 |
| `app:&prod` | intersection: in both | app1 app2 |
| `app:!staging` | exclusion: in `app`, not in `staging` | app1 app2 app3 |
| `app[0]`, `app[1:]`, `app[-1]` | by position in the group | app1; app2 stg-app1 app3; app3 |
| `stg-*` | wildcard on names | stg-app1 stg-db1 |
| `~^(app\|db)\d$` | regular expression, after the `~` | app1 app2 db1 app3 |

Quote the patterns in a shell: `!` and `&` mean something to it. A position counts in the group's order, which is the order the sources added the hosts, so `app[-1]` is app3 only because `20-extra.yml` comes second.

## The operators don't apply left to right

The Ansible docs give the processing order: first `:` and `,`, then `&`, then `!`, wherever each appears. So `prod:&app:db` doesn't mean "prod and app, then add db":

- `prod:&app:db` matched app1 app2: the union `prod:db` first, then `&app`.
- `app:db:&prod` matched app1 app2 db1: the union `app:db`, then `&prod`.
- `!staging:app` matched app1 app2 app3, the same as `app:!staging`.

When a pattern mixes operators, check it with `--list-hosts` before trusting it.

## --limit narrows the play

A play's `hosts:` is the most it can reach; `--limit` (or `-l`) keeps only the hosts that also match another pattern, without editing the playbook. With `site.yml` on `hosts: app`:

- no `--limit`: app1, app2, stg-app1, app3;
- `--limit staging`: stg-app1;
- `--limit @limit.txt`, a file holding db1 and stg-app1, one per line: stg-app1. db1 is in the file but not in `app`, so the play doesn't reach it.

The `@file` form reads one pattern per line. The Ansible docs show it with `site.retry`, the file of failed hosts Ansible can write after a run, but it writes one only when `RETRY_FILES_ENABLED` is true, and it defaults to false.

## A second source

Two `-i` options, or one directory holding several files, give Ansible several sources, merged into one inventory before any pattern applies. `ansible app -i inventory/10-hosts.yml --list-hosts` matched app1 app2 stg-app1; adding `-i inventory/20-extra.yml` added app3. The same goes for a static file next to a dynamic plugin's configuration: their groups of the same name merge, and only `ansible-inventory --graph`, from [item 6](inventory-checking-with-ansible-inventory.md), shows the result, since no single file holds it.

## Groups built from a variable

`ansible.builtin.constructed` is an inventory plugin that reads the hosts the earlier sources added and creates groups from their variables. Its `keyed_groups` option makes one group per value of an expression, named with a prefix:

```yaml
plugin: ansible.builtin.constructed
strict: false
use_vars_plugins: true
keyed_groups:
  - key: env
    prefix: env
```

It built `env_prod` (app1 app2 db1) and `env_staging` (stg-app1 stg-db1). `app:!env_prod:!env_staging` then found app3, the one app host with no environment: a pattern that checks the inventory itself.

- **`use_vars_plugins: true` is what lets it see `group_vars/`.** `env` lives there, and the plugin's documentation says vars plugins, which read `group_vars/` and `host_vars/`, normally run only after every source is parsed. Without the option, `env` is undefined for every host when `constructed` runs.
- **`strict` decides what a missing key does.** With `strict: false`, app3, which has no `env`, is skipped silently. With `strict: true`, the source stops at app3: four warnings, *Could not generate group for host app3 from env entry: 'env' is undefined* followed by one per inventory plugin Ansible tried, then *Unable to parse*. Yet `env_prod` and `env_staging` were still complete, because app3 was the last host and the groups built before it stayed. A warning that looks fatal, and an inventory that looks right: with `strict: true`, read the warnings.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/11-host-patterns), holds the inventory, the `strict: true` variant, `limit.txt` and `site.yml`. `run.sh` lists the hosts of each pattern above, adds the second source, uses the constructed groups, runs the strict variant, runs `site.yml` with each `--limit`, and prints the tree. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_patterns.rst` (processing order, `--limit @file`, `RETRY_FILES_ENABLED`).
- ansible-core 2.21.4: the `constructed` plugin's documentation, `lib/ansible/plugins/inventory/constructed.py` (`use_vars_plugins`, `strict`), and `RETRY_FILES_ENABLED` in `lib/ansible/config/base.yml`.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
