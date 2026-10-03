# set_fact in a loop or one expression: part 11's pg_hba rules, built both ways

Fifteenth entry in the Shaping data in Ansible series. Every part so far built data in one expression: a chain of filters in a variable. Many playbooks build it another way, one item at a time: a `set_fact` task, which sets a variable on the current host, run in a loop, each turn appending to the result of the last. This entry builds [part 11](data-from-other-hosts-extract-hostvars-pg-hba.md)'s `pg_hba` rules both ways, and compares what they produce, what happens when the tasks run again, and how long they take. Everything below ran with ansible-core 2.21.4.

## The two versions

The play runs on the PostgreSQL server, `db1`, and needs one `hostssl` rule per application server that has an address ([part 5](subelements-versus-product-quadlet-volumes-pg-hba.md) explains the rules). In the example, each app host's address is an inventory variable, `app_ipv4`, and one host in three from the fourth on has none.

The loop, one rule per turn:

```yaml
- name: Append a rule for each app host
  ansible.builtin.set_fact:
    rules_loop: "{{ rules_loop | default([]) + [pg_hba_base
      | combine({'database': 'app', 'address': hostvars[item].app_ipv4 ~ '/32'})] }}"
  loop: "{{ groups['app'] }}"
  when: hostvars[item].app_ipv4 is defined
```

`loop` runs the task once per app host, with the host's name in `item`, and `when` skips the hosts without an address. On the first turn, `rules_loop` doesn't exist yet, so `default([])` starts from an empty list; `+` adds a one-rule list to it.

The expression, as in part 11, in the play's `vars`:

```yaml
rules_expression: "{{ [pg_hba_base] | product([{'database': 'app'}],
  groups['app'] | map('extract', hostvars) | selectattr('app_ipv4', 'defined')
  | map(attribute='app_ipv4') | map('regex_replace', '$', '/32') | map('community.general.dict_kv', 'address'))
  | map('combine') | list }}"
```

On six app hosts, five with an address, both gave the same five rules, in the same order:

```
hostssl app all 10.10.0.2/32 scram-sha-256
…
hostssl app all 10.10.0.6/32 scram-sha-256
```

The loop also printed one line per host, five `ok` and one `skipping`, where the expression prints nothing until something uses it.

## Run the loop twice and the rules double

The loop's `default([])` only applies the first time. When the same tasks ran a second time in the play, as they would from a second `include_tasks` or a role applied twice, `rules_loop` already held five rules, and the second pass appended five more: **10 rules**, every app server twice. PostgreSQL uses the first matching line, so the duplicates do no harm there, but in a list of users, mounts or firewall rules, they might.

The expression has no memory: it's computed from `groups` and `hostvars` each time it's read, and gave five rules however often it ran.

## A set_fact value can't be reset from vars

Resetting the list before the second pass seems easy: give the variable an empty value. Neither obvious place worked:

| Where `rules_loop: []` was set | What the task saw |
|---|---|
| the task's own `vars` | 10 rules |
| a later play's `vars`, on the same host | 10 rules |

That's *variable precedence*, the order in which Ansible picks a variable's value when it's defined in several places. In the docs' list, *Using Variables*, *"Registered vars and set_facts"* rank 19th of 22, above play vars (12th) and task vars (17th); only role and include parameters and extra vars from the command line rank higher. And the `set_fact` documentation says the variables *"will be available to subsequent plays during an ansible-playbook run via the host they were set on"*. Once set, the loop's list stays for the whole run, and only another `set_fact` replaces it. A play's variable is safe from this; a variable some role filled with `set_fact` earlier isn't.

## The loop's cost grows with the square of the hosts

Each turn of the loop is a task run: templating, a result to record, a line of output. And each turn builds a new list from the previous one plus one rule, so the hundredth turn copies 99 rules. With `time.sh` from the example, on generated inventories, on a 4-CPU machine:

| App hosts | `set_fact` loop | One expression |
|---|---|---|
| 100 | 1.4 s | 0.7 s |
| 500 | 8.2 s | 1.0 s |
| 2000 | 101 s | 2.1 s |

Much of the expression's time is `ansible-playbook` itself starting up. Five times the hosts made the loop six times slower, and four times more made it twelve times slower again. The run was repeated three times at 500 hosts: 8.1 to 8.7 s for the loop, 1.0 to 1.1 s for the expression.

## When set_fact is right

`set_fact` isn't the problem; the loop around it is. A single `set_fact` task that stores an expression's result has its uses:
- **To compute once.** A variable in `vars` is computed again each time it's read. An expensive expression read in many tasks can be stored once with `set_fact`, as the example's `time-expression.yml` does.
- **To keep a value fixed** when what it's computed from changes later in the play, such as a timestamp or a host list before some hosts fail.
- **To pass a value to later plays**, as part 11 did with recorded facts.

## Which one

- **Building a list or dict from other data:** one expression, in `vars`, with the filters of the earlier parts.
- **The expression is expensive and read often:** the same expression, stored once with `set_fact`.
- **A loop that appends with `set_fact`:** only for small lists, and never where the tasks can run twice. To start over, reset it with another `set_fact`; `vars` can't.
- **A loop over hosts, to act once per host:** neither; a play on those hosts, with `delegate_to` when the action runs elsewhere, as [item 13 of the inventory series](inventory-is-the-loop-delegate-to.md) shows.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/15-set-fact-or-expression), runs all of the above on the local machine, changing nothing outside its `out/` directory. `build.yml` builds the rules both ways on six app hosts, runs the loop twice and tries both resets; its CI runs it on every push and compares the output with the expected one. `time.sh` reproduces the timings, outside CI, since they depend on the machine.

## Sources

- ansible-core 2.21.4: `modules/set_fact.py` (its documentation on later plays and precedence).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_variables.rst` (*Understanding variable precedence*), `playbook_guide/playbooks_loops.rst`.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine, timings included. No PostgreSQL server was configured.
