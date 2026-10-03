# group_by: groups from facts, built during the run

Twenty-second entry in the Ansible inventory from scratch series. The earlier items gave each group a place in the inventory before the run: in a hosts file, or built by an inventory plugin from the data of another system. Some groups depend on what a host turns out to be: its distribution, its OS family. `ansible.builtin.group_by` is the module that builds those during a play, from *facts*, the values Ansible gathers from a host (see [item 7](inventory-facts-or-variables-as-is-to-be.md)). [The previous entry](inventory-add-host-provision-then-configure.md) used its sibling `add_host`, which adds hosts rather than groups. Everything below ran with ansible-core 2.21.4.

## Facts from several distributions on one machine

The example's six hosts, web1, web2, db1, db2, lb1 and lb2, all run on the local machine, so gathering facts would give each the same distribution. Instead, the example uses recorded facts and a *fact cache*, the store where Ansible keeps facts between runs (see [item 12](inventory-limit-in-practice.md#two-ways-to-get-the-facts-back)): `facts/` holds one file per host, in the format the `jsonfile` cache plugin writes, and `run.sh` copies them to the cache directory that `ansible.cfg` sets. With `fact_caching_timeout = 0` they never expire, and with `gather_facts: false` the plays read them without connecting to anything. It's cheaper than one container per distribution, and the output is the same on every run.

| Host | `distribution` | `distribution_major_version` | `os_family` |
|---|---|---|---|
| web1 | Ubuntu | 24 | Debian |
| web2 | Debian | 12 | Debian |
| db1 | Rocky | 9 | RedHat |
| db2 | AlmaLinux | 9 | RedHat |
| lb1 | openSUSE Leap | 15 | Suse |
| lb2 | no facts | | |

The values are the names `setup`, the module that gathers facts, reports for these distributions; ansible-core maps each to its family in `module_utils/facts/system/distribution.py`. The format of the cache files belongs to ansible-core (an `s1_` prefix in 2.21), so the fixtures need re-recording when it changes.

## Grouping by OS family

The hosts file only has `web`, `db` and `lb`. The playbook's first play runs on all hosts:

```yaml
- name: Add each host to the group of its OS family
  ansible.builtin.group_by:
    key: os_{{ group_os_family }}
    parents: by_os
```

with `group_os_family: "{{ ansible_facts.os_family | default('unknown') }}"` in the play's variables.

- **`key`** is the name of the group, here a prefix and a fact. The task runs once per host, and each host joins the group its own value names: os_Debian, os_RedHat or os_Suse. Groups that don't exist yet are created. The prefix keeps a group called `RedHat` from clashing with a host or another group of that name.
- **`parents`** names the groups the new group goes under; it defaults to `all`. `by_os` didn't exist either; group_by created it, with each `os_` group as its child.
- **`default('unknown')`** gives lb2, which has no facts, a group too: os_unknown. Without it, lb2's task fails (below).

A second task groups by distribution and major version, under the family: `parents: os_{{ group_os_family }}`, so db1 lands in rocky9, a child of os_RedHat. Each host's `group_names`, the variable that lists the groups it's in, after the two tasks:

```
db1: by_os db os_RedHat rocky9
lb1: by_os lb opensuse_leap15 os_Suse
lb2: by_os lb os_unknown unknown
web1: by_os os_Debian ubuntu24 web
```

A second play with `hosts: os_RedHat` then ran on db1 and db2. That's the pattern the Ansible docs give in *Handling OS and distro differences* for running across operating systems: one play that groups, then plays on the groups.

## group_vars of a group that doesn't exist yet

`group_vars/<group>/` holds a group's variables (see [item 2](inventory-directory-group-vars-per-role.md)), and nothing stops it from naming a group the hosts file lacks. The example's inventory has `group_vars/os_Debian/`, `os_RedHat/` and `os_Suse/`, each setting `package_manager` to apt, dnf or zypper. A task before group_by and one after, in the same play, recorded it:

- before: undefined for every host;
- after: apt, dnf or zypper, from the very next task, and in the later play on os_RedHat;
- lb2, in os_unknown, which has no `group_vars/`: still undefined.

So the variables follow the group as soon as the host joins it. The docs' note on this pattern says all three names must match: the key, the play's `hosts:`, and the `group_vars/` directory. A typo in one of them is silent: the group gets no variables, or the play matches no hosts.

## Group names with spaces

`distribution` can contain a space: openSUSE Leap, Linux Mint. The module's documentation says spaces in group names become dashes. In ansible-core 2.21.4, `pitfalls/spaces.yml` found otherwise with `key: distro_{{ ansible_facts.distribution }}`:

- the task's result said `add_group: distro_openSUSE-Leap`, with a dash;
- the host's `group_names` held `distro_openSUSE Leap`, with the space: the action plugin replaces it in the name it reports, not in the name it creates;
- a warning, *Invalid characters were found in group names but not replaced*;
- a play with `hosts: distro_openSUSE-Leap` printed *Could not match supplied host pattern* and *skipping: no hosts matched*. A pattern with the space doesn't work either, since Ansible splits it there.

Sanitise the value yourself: the example's key uses `ansible_facts.distribution | regex_replace('\\W', '_') | lower`, which replaces anything other than a letter, a digit or `_` with `_`, and gives `opensuse_leap15`. That's also a name `group_vars/` can hold and a pattern can match.

## --limit and failed hosts

`--limit` keeps only the hosts of a run that match a pattern (see [item 11](targeting-hosts-static-and-dynamic-inventory.md)).

- **`--limit web1,db1`**: only those two ran the group_by tasks, so os_RedHat held db1 only and the play on it ran on db1. Groups hold the hosts that ran the task, not every host that would qualify.
- **`--limit os_RedHat`**: *Could not match supplied host pattern, ignoring: os_RedHat*, then *no hosts to target*, exit code 1. The limit is read against the inventory before any play runs, when the group doesn't exist.

`pitfalls/no-default.yml` uses `key: os_{{ ansible_facts.os_family }}` without the default. lb2's task failed, *object of type 'dict' has no attribute 'os_family'*, and the run ended with exit code 2. lb2 joined no group, and the next play, on `all`, ran on the five other hosts only: a host that fails is left out of the rest of the run.

## The groups end with the run

group_by changes the *in-memory inventory*, the copy `ansible-playbook` works from, never the inventory's files. After the run, `ansible-inventory --graph` showed no `os_` group, and `ansible-inventory --host db1` had no `package_manager`: the `group_vars/os_RedHat/` directory applies to nobody until a play builds the group again.

## When keyed_groups is the better tool

[Item 11](targeting-hosts-static-and-dynamic-inventory.md) built groups with the `constructed` inventory plugin's `keyed_groups`, and [item 18](inventory-constructed-keyed-groups-compose.md) covered it in full. constructed builds its groups when the inventory is parsed, from variables the earlier sources set and from the fact cache. The example's `keyed/constructed.yml`:

```yaml
plugin: ansible.builtin.constructed
strict: false
keyed_groups:
  - key: ansible_os_family
    prefix: os
    parent_group: by_os
```

The cached facts carry the `ansible_` prefix, hence `ansible_os_family`. `ansible-inventory -i inventory -i keyed/constructed.yml --graph by_os` showed os_Debian, os_RedHat and os_Suse with their hosts before any play, and `os_RedHat` worked as a pattern, so as a `--limit` too. lb2, with no facts, is in none of them.

- **constructed** when the value is known before the run: in the source of truth, in the fact cache, in `group_vars/`. The groups show in `ansible-inventory`, work with `--limit`, and don't need a play.
- **group_by** when the value only exists once the run has looked at the host: facts gathered now, a registered result. It needs a first play on all the hosts, its groups only hold the hosts that ran it, and they vanish at the end.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/22-group-by), holds the inventory with its `group_vars/` for the dynamic groups, the recorded facts, the playbook, both pitfalls and the constructed source. `run.sh` prints the facts, runs the playbook without and with each `--limit`, checks what's left after the run, runs the pitfalls and the constructed version. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `lib/ansible/modules/group_by.py` (options and the note on spaces), `lib/ansible/plugins/action/group_by.py` (the reported and the created group name), `lib/ansible/inventory/manager.py` (`add_dynamic_group`), `lib/ansible/plugins/inventory/constructed.py` (facts from the cache), `lib/ansible/plugins/cache/jsonfile.py` and `lib/ansible/_internal/_plugins/_cache.py` (the cache format), `lib/ansible/module_utils/facts/system/distribution.py` (distribution names and families).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `tips_tricks/ansible_tips_tricks.rst` (*Handling OS and distro differences*).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
