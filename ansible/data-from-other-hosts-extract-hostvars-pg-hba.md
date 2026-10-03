# Data from other hosts: pg_hba rules from the app servers' facts, with hostvars and extract

Eleventh entry in the Shaping data in Ansible series. Every part so far shaped data that one host already had. A common need goes across hosts: the PostgreSQL server must allow connections from the application servers, so its rules need their addresses. Those addresses are in the application servers' *facts*, the information Ansible gathers about each host when a play starts (its `gather_facts` step, done by the `setup` module). This entry reads them from the PostgreSQL server's play with `hostvars`, `groups` and the `extract` filter, and looks at what happens when a host has no facts. Everything below ran with ansible-core 2.21.4.

## The hosts and the variables that reach across them

The inventory, the list of hosts Ansible manages, puts them in groups:

```yaml
all:
  children:
    app:
      hosts:
        app1:
        app2:
        app3:    # added since the last run that gathered facts
    db:
      hosts:
        db1:
```

Two variables are the same in every play, on every host:
- **`groups`** maps each group name to its hosts: `groups['app']` was `['app1', 'app2', 'app3']`.
- **`hostvars`** maps each host name to that host's variables, its facts included: `hostvars['app1'].ansible_facts.default_ipv4.address` is app1's main IPv4 address.

[Part 5](subelements-versus-product-quadlet-volumes-pg-hba.md) explains `pg_hba.conf`, PostgreSQL's client authentication rules, and builds them with the PostgreSQL system role. Here the play runs on `db1` and needs one rule per application server, with its address as a */32*, the subnet that holds exactly one address.

## extract: hostvars for a list of host names

`map(attribute=…)` ([part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md)) reads an attribute of each item. Here the items are host names, plain strings, and the data is elsewhere, in `hostvars`. `extract` does the lookup the other way round: `'app1' | extract(hostvars)` is `hostvars['app1']`. A third argument, a list of keys, goes further down:

```yaml
"{{ groups['app'] | map('extract', hostvars, ['ansible_facts', 'default_ipv4', 'address']) | list }}"
```

Part 5 already used `extract` with a dict, to list each rule's fields in order. With `hostvars`, it's the usual way to collect one fact from every host of a group.

In the example, `app1` and `app2` had facts from an earlier run, and `app3`, added since, had none. The expression failed:

> object of type 'dict' has no attribute 'default_ipv4'

`app3`'s `ansible_facts` was an empty dict. The message doesn't say which host, and the whole task failed.

## Facts exist only where something gathered them

A host's facts are there in three cases:
- a play in the same run targeted the host and gathered its facts;
- the *fact cache* holds them from an earlier run;
- a task gathered them on the host's behalf (below).

The PostgreSQL server's play targets `db1` only. Without a cache, the app hosts' facts are never gathered in that run, whatever they hold. The *fact cache* keeps facts between runs: the example's `ansible.cfg` sets `fact_caching = jsonfile`, one JSON file per host in a directory, and they stay valid for 24 hours (`fact_caching_timeout`, 86400 seconds by default). In the example, a first playbook stores the facts that an earlier run would have gathered on `app1`, `app2` and `db1`.

`--limit` restricts a run to some hosts. It doesn't change what the other hosts' variables hold:

| Run of the PostgreSQL server's play | `groups['app']` | App hosts with an address |
|---|---|---|
| with the fact cache | `app1`, `app2`, `app3` | `app1`, `app2` |
| with `--limit db1` | `app1`, `app2`, `app3` | `app1`, `app2` |
| with the cache emptied | `app1`, `app2`, `app3` | none |

`groups` comes from the inventory, so it lists every host, gathered or not. A rule for every member of `groups['app']` can't come straight from it: a host with no facts has to be dropped or reported.

## Keep the hosts with an address, and report the rest

`map('extract', hostvars)` without keys gives one dict of variables per host, and part 4's `selectattr` and `rejectattr` sort them with the `defined` test:

```yaml
app_hostvars: "{{ groups['app'] | map('extract', hostvars) | list }}"
app_with_address: "{{ app_hostvars | selectattr('ansible_facts.default_ipv4.address', 'defined') }}"
app_without_address: "{{ app_hostvars | rejectattr('ansible_facts.default_ipv4.address', 'defined')
  | map(attribute='inventory_hostname') | list }}"
```

`inventory_hostname` is each host's own name. From the addresses, part 5's `product` built the rules, and the role's template wrote:

```
hostssl app all 10.10.0.11/32 scram-sha-256
hostssl app all 10.10.0.12/32 scram-sha-256
```

No rule for `app3`, and no error either. Writing that file would lock `app3` out of the database. An `assert` task before it names the hosts:

```yaml
- name: Assert that no app host is missing
  ansible.builtin.assert:
    that: app_without_address | length == 0
    fail_msg: "no address in the facts of: {{ app_without_address | join(', ') }}"
```

It gave *"no address in the facts of: app3"*, and with the cache emptied *"no address in the facts of: app1, app2, app3"*. `selectattr` is still worth having: with the assert in front, it keeps the expression from failing with a message that doesn't name the host.

## Gathering the missing facts from the PostgreSQL server

A task can gather another host's facts. `delegate_to` runs it on that host instead of the current one, and `delegate_facts: true` stores what it returns as that host's facts, not the current host's:

```yaml
- name: Gather the facts of each app host that has none, stored as theirs
  ansible.builtin.setup:
  delegate_to: "{{ item }}"
  delegate_facts: true
  loop: "{{ app_without_facts }}"
```

In the example, the app hosts without facts went from `app1`, `app2` and `app3` (cache emptied) to none, and `db1` got no facts of its own from the task. The other way works too, and is simpler: a first play on `hosts: app` with `gather_facts: true`, before the PostgreSQL server's play. Both mean connecting to every app host, which `--limit db1` was perhaps meant to avoid; the fact cache doesn't.

## ansible_facts, not the top-level variables

Each fact can also be read as a variable of its own, with an `ansible_` prefix: `ansible_default_ipv4` for `ansible_facts.default_ipv4`. That's the `INJECT_FACTS_AS_VARS` setting, true by default. Reading `hostvars['app3'].ansible_system` gave the same value as `hostvars['app3'].ansible_facts.system`, with a warning:

> INJECT_FACTS_AS_VARS default to `True` is deprecated, top-level facts will not be auto injected after the change. This feature will be removed from ansible-core version 2.24.

The ansible-core 2.20 porting guide confirms that the default switches to false in 2.24. The delegation docs, *Delegating facts*, still show the old form, `hostvars['dbhost1']['ansible_default_ipv4']['address']`. Write `hostvars[host].ansible_facts.default_ipv4.address`; it works in every version.

## Which one

- **One value from every host of a group:** `groups[name] | map('extract', hostvars, ['ansible_facts', …])`, once you know every host has it.
- **Some hosts may have no facts:** `map('extract', hostvars)`, then `selectattr`/`rejectattr` with `defined`, and an `assert` that names the missing hosts.
- **Facts of hosts not in the play:** a fact cache, a first play that gathers them, or `setup` with `delegate_to` and `delegate_facts: true`.
- **Always:** read facts through `ansible_facts`, not the top-level `ansible_*` variables.
- **Doing something for each host of a group on one other host,** such as creating a database role per app host on db1: a play on the group with `delegate_to`, not a loop over a list of hosts, as [item 13 of the inventory series](inventory-is-the-loop-delegate-to.md) measures.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/11-data-from-other-hosts), runs all of the above on the local machine, changing nothing outside its `out/` directory. Every host in its inventory runs locally, so `record-facts.yml` stands for the earlier run: it stores each host's address from the inventory in the fact cache, with `set_fact` and `cacheable: true`. `pg_hba.yml` builds the rules on `db1`, and `run.sh` runs it with the cache, with `--limit db1` and with the cache emptied, then runs `gather-missing.yml`. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/extract.yml`, `config/base.yml` (`INJECT_FACTS_AS_VARS`, `CACHE_PLUGIN_TIMEOUT`) and `vars/manager.py` (the deprecation warning).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_vars_facts.rst` (facts and fact caching), `playbook_guide/playbooks_delegation.rst` (*Delegating facts*), `reference_appendices/special_variables.rst` (`groups`, `hostvars`, `inventory_hostname`) and `porting_guides/porting_guide_core_2.20.rst` (*INJECT_FACTS_AS_VARS*).
- [linux-system-roles.postgresql](https://github.com/linux-system-roles/postgresql) 1.9.0: `templates/pg_hba.conf.j2`.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine. No PostgreSQL server was configured.
