# --limit in practice: every play, run_once per batch, and the facts of hosts left out

Twelfth entry in the Ansible inventory from scratch series. [Item 11](targeting-hosts-static-and-dynamic-inventory.md) covered *host patterns*, the expressions that choose hosts, and `--limit`, the option that keeps only the hosts of a run that also match another pattern. This entry is about what `--limit` does beyond choosing hosts: to a playbook with several plays, to tasks that run once, to what one host knows about another, and when it matches nothing. Everything below ran with ansible-core 2.21.4, on item 11's inventory without its extra sources: `app` holds app1, app2 and stg-app1, `db` holds db1 and stg-db1, and `group_vars/` gives each environment's hosts an `env` variable.

## --limit applies to every play

A *playbook* is a list of *plays*, each with its own `hosts:` pattern. The example's `site.yml` has two: one on `db`, then one on `app`. `--limit` narrows each of them, not just the first:

- without `--limit`, the db play ran on db1 and stg-db1, then the app play on the three app hosts;
- with `--limit app`, the db play printed *skipping: no hosts matched* and the app play ran as before.

A skipped play doesn't stop the run. That's convenient for running part of a site playbook, and a trap when a later play counts on something an earlier one did on hosts the limit left out. `ansible-playbook site.yml --limit app --list-hosts` shows each play's hosts before anything runs: `hosts (0)` for the db play.

## run_once runs once per batch

`serial: 2` on a play makes Ansible run it on two hosts at a time: the whole play on the first *batch*, then the whole play on the next. `run_once: true` on a task runs it on one host only, and the Ansible docs, *Controlling playbook execution*, say which: *"the first host in your batch of hosts"*. With `serial`, that's once per batch:

- the app play's batches were app1 and app2, then stg-app1; the `run_once` task ran on app1, then again on stg-app1;
- with `--limit 'app:!app2'`, a single batch, app1 and stg-app1; it ran once, on app1.

So `--limit` can change how many times a `run_once` task runs, because it changes the batches. A task that must run exactly once in a play with `serial` belongs in a play of its own.

## What a host outside the limit still has

`hostvars` is the variable that holds every host's variables, so a task on app1 can read `hostvars.db1.env`. The example's `facts.yml` gathers facts on `db` in a first play, then prints, from the app play, what app1 knows about db1:

| | Without `--limit` | `--limit app` |
|---|---|---|
| `ansible_limit` | not set | `app` |
| `groups.db` | db1 stg-db1 | db1 stg-db1 |
| `hostvars.db1.env`, an inventory variable | prod | prod |
| `hostvars.db1.ansible_facts.system`, a fact | Linux | missing |

- **The inventory doesn't shrink.** `groups` and every host's inventory variables are the same with or without `--limit`; only the plays' hosts change.
- **Facts disappear**, because facts are gathered from a host, and the play that would have gathered db1's skipped it. [Part 11 of the data-shaping series](data-from-other-hosts-extract-hostvars-pg-hba.md) hits the same thing building `pg_hba.conf` from the app servers' facts, and filters out the hosts that have none.
- **`ansible_limit`** holds the value given to `--limit`, so a play can tell whether it runs limited.

## Two ways to get the facts back

- **Gather them from the play that needs them.** A `setup` task, the module that gathers facts, with `delegate_to: "{{ item }}"` looping over `groups.db`, runs on each db host; `delegate_facts: true` stores the facts under that host instead of the current one. With `--limit app1`, `hostvars.db1.ansible_facts.system` was then `Linux`. It still connects to the db hosts, which the limit was perhaps meant to avoid.
- **Keep facts from an earlier run.** A *fact cache* stores gathered facts between runs; with the `jsonfile` cache plugin (`ANSIBLE_CACHE_PLUGIN=jsonfile`, files in `ANSIBLE_CACHE_PLUGIN_CONNECTION`), a full run filled it, and the run with `--limit app` then read db1's system as `Linux` without connecting to db1. The facts are as old as that earlier run.

## When the limit matches nothing

- `--limit dbs`, a group that doesn't exist: a warning, *Could not match supplied host pattern, ignoring: dbs*, then *Specified inventory, host pattern and/or --limit leaves us with no hosts to target*, exit code 1. Nothing ran.
- `--limit 'app1,ap2'`, with a typo in one host: the same warning for `ap2`, then the run went ahead on app1 with exit code 0. A mistyped host is silently left out, so read the warnings.
- A play whose `hosts:` matches nothing, `hosts: dbs`, without `--limit`: the warning, *skipping: no hosts matched*, exit code 0.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/12-limit-in-practice), holds the inventory and the four playbooks. `run.sh` runs each case above and prints the debug messages, warnings and skipped plays; its `ansible.cfg` sets `forks = 1`, one host at a time, so the output comes in the same order on every run. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_strategies.rst` (`serial`, `run_once`), `playbook_guide/playbooks_delegation.rst` (*Delegating facts*), and `reference_appendices/special_variables.rst` (`ansible_limit`).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
