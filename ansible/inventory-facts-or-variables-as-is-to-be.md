# Facts or variables: what Ansible discovers (as-is) against what you declare (to-be)

Seventh entry in the Ansible inventory from scratch series. The entries so far put variables in the inventory: [item 2](inventory-directory-group-vars-per-role.md) in `group_vars/`, [item 4](inventory-connection-variables-ssh-docker-local.md) connection settings in `host_vars/`. Ansible also learns things about each host by itself, its *facts*. This entry looks at the difference between the two, with a PostgreSQL version that drifted, and at which of them belongs in the inventory. Everything below ran with ansible-core 2.21.4 and community.docker 5.3.0, on 2026-10-03.

## As-is and to-be

The Red Hat Community of Practice's *automation good practices*, a guide written by Red Hat consultants, has a rule on this in its inventory chapter, *Differentiate clearly between "As-Is" and "To-Be" information*:

> As you combine multiple sources, some will represent:
>
> * discovered information grabbed from the existing environment, this is the "As-Is" information.
> * managed information entered in a tool, expressing the state to be reached, hence the "To-Be" information.
>
> In general, the focus of an inventory is on the managed information because it represents the desired state you want to reach with your automation. This said, some discovered information is required for the automation to work.

and gives the reason:

> Mixing up these two kind of information can lead to your automation taking the wrong course of action by thinking that the current situation is aligned with the desired state.
> That can make your automation go awry and your automation engineers confused.
> There is a reason why Ansible makes the difference between "facts" (As-Is) and "variables" (To-Be), and so should you.
> In the end, automation is making sure that the As-Is situation complies to the To-Be description.

In Ansible's terms:
- **Variables** are what you write: in the inventory, in a playbook, on the command line. The inventory's are the to-be.
- **Facts** are what a module reports about a host, kept in the `ansible_facts` variable of that host. The `setup` module, run by a play's `gather_facts` step, gathers the general ones (operating system, addresses, memory); others come from modules like `ansible.builtin.package_facts`, which lists the installed packages in `ansible_facts.packages`. [Part 11 of Shaping data in Ansible](data-from-other-hosts-extract-hostvars-pg-hba.md) reads another host's facts through `hostvars`, the variable that maps each host name to its variables.

## Declared against installed

The example's inventory has one group, `postgresql`, with two hosts, both containers reached with the `community.docker.docker` connection from item 4. The group declares the major version its hosts should run:

```yaml
# group_vars/postgresql/postgresql.yml
postgresql_version: 16
```

db1 is an Ubuntu 24.04 container with the `postgresql-client-16` package; db2 a Debian 12 container with `postgresql-client-15`. A playbook runs `package_facts` on both, takes the major version from the name of the installed `postgresql-client-NN` package, and compares it with `postgresql_version`:

```yaml
- name: Gather the installed packages
  ansible.builtin.package_facts:
```

```jinja
{% set declared = hostvars[host].postgresql_version | string %}
{% set installed = hostvars[host].ansible_facts.packages
     | select('match', '^postgresql-client-[0-9]+$')
     | map('regex_replace', '^postgresql-client-', '') | list %}
```

It wrote:

```
db1: declared 16, installed 16: ok
db2: declared 16, installed 15: drift
```

The declaration says what db2 should be; the fact says what it is; the difference is the work left to do. On Debian and Ubuntu, `package_facts` needs the `python3-apt` package on the host: the first images had none, and the module failed with *"Could not detect a supported package manager"*.

## Don't write the discovered value back

Say someone, seeing db2 runs 15, "fixes" the inventory to match:

```yaml
# host_vars/db2/postgresql.yml
postgresql_version: 15
```

A host variable overrides a group variable, so db2's declaration is now 15. The same playbook, with this file added, wrote:

```
db1: declared 16, installed 16: ok
db2: declared 15, installed 15: ok
```

Nothing changed on db2, and the drift is gone from the report. The variable is no longer a declaration: it describes what db2 was when someone looked, and it stays that way after an upgrade, or a failed one. The guide notes the same of configuration management databases (CMDBs), the inventories of record many companies keep: *"many CMDBs have failed because they don't respect this principle."* When a host must stay on another version for a while, that's a decision, and it can go in `host_vars/` with a comment saying why; a value copied from the host isn't.

## Where facts live: not in the inventory, but close

Facts don't come from the inventory. Before any play, `ansible-inventory --host db1`, which prints the variables a host gets, listed:

```
ansible_connection, ansible_host, ansible_python_interpreter, postgresql_version
```

By default facts last only as long as the run. A *fact cache* keeps them between runs; the example's `ansible.cfg` turned one on, a JSON file per host:

```ini
[defaults]
fact_caching = ansible.builtin.jsonfile
fact_caching_connection = out/facts
```

After the playbook ran, the same command listed:

```
ansible_connection, ansible_host, ansible_python_interpreter, packages, postgresql_version
```

`packages`, a fact, now looked like one of db1's inventory variables. ansible-core's `cli/inventory.py` explains it: without `--export`, `--host` asks for *"all vars flattened by host"*, which includes cached facts. With `--export`, which only reads variables *"defined directly"* on the host and from vars plugins, it listed:

```
ansible_connection, ansible_host, ansible_python_interpreter
```

No facts, and no `postgresql_version` either: `--export` leaves out the group's variables too. So with a fact cache, check what `ansible-inventory --host` shows before taking it for the inventory's content.

## When a fact and a variable share a name

`packages` appeared without its `ansible_facts.` prefix because of `INJECT_FACTS_AS_VARS`. Its description in ansible-core's `config/base.yml`:

> Facts are available inside the `ansible_facts` variable, this setting also pushes them as their own vars in the main namespace.

It's on by default, and the [ansible-core 2.20 porting guide](https://docs.ansible.com/projects/ansible/latest/porting_guides/porting_guide_core_2.20.html) deprecated that: *"it will switch to `False` in Ansible 2.24."*

In Ansible's variable precedence, *"Host facts and cached set_facts"* come after, so override, *"Inventory host_vars/*"* and every inventory group variable. An injected fact therefore wins over an inventory variable of the same name. The example declared a list in `group_vars/postgresql/packages.yml`:

```yaml
packages:
  - postgresql-client-16
```

and printed its type after `package_facts`:

```
injected (the default): packages is a dict
warning: INJECT_FACTS_AS_VARS default to `True` is deprecated
inject_facts_as_vars=false: packages is a list
```

With injection on, the declared list was replaced by the fact's dict of installed packages, the as-is overwriting the to-be under the same name, and ansible-core 2.21.4 printed the deprecation warning. With `ANSIBLE_INJECT_FACT_VARS=false`, the inventory's list stayed. Reading facts as `ansible_facts.packages`, never as `packages`, works the same with both settings.

## In short

- **The inventory holds the to-be**: what each host should be, written by hand. Facts are the as-is, reported by the host at run time.
- **Compare them, don't merge them**: a play reads both and reports or fixes the difference.
- **Never copy a discovered value into `host_vars/`**: it stops being a declaration and hides the drift.
- **A fact cache makes facts show up in `ansible-inventory --host`**; `--export` shows the host's own inventory variables only.
- **Read facts through `ansible_facts.`**, and keep inventory variables off fact names, at least until `INJECT_FACTS_AS_VARS` defaults to false in 2.24.
- **Local facts from `facts.d` blur the split:** a hand-written one is a declared value that looks measured. [Item 26](inventory-local-facts-facts-d-risks.md) shows what it does to a drift check.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/07-facts-or-variables), holds this inventory, the two images behind db1 and db2, pinned by digest, and the two wrong inventories, each added as a second `-i` source. `run.sh` needs Docker: it starts both containers, runs the drift report, prints `ansible-inventory --host` before and after the fact cache fills, then repeats the two mistakes above. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Red Hat Community of Practice, [automation good practices](https://github.com/redhat-cop/automation-good-practices), `inventories/README.adoc` at commit `fb5fcd6` (2026-09-09): *Differentiate clearly between "As-Is" and "To-Be" information*.
- ansible-core 2.21.4: `config/base.yml` (`INJECT_FACTS_AS_VARS`, `CACHE_PLUGIN`) and `cli/inventory.py` (`_get_host_variables`, with and without `--export`).
- Ansible documentation: [Understanding variable precedence](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_variables.html#understanding-variable-precedence) and the [ansible-core 2.20 porting guide](https://docs.ansible.com/projects/ansible/latest/porting_guides/porting_guide_core_2.20.html) (`INJECT_FACTS_AS_VARS`).
- Every result above came from ansible-core 2.21.4 and community.docker 5.3.0 on 2026-10-03, with Docker 29.6.2 and containers from `ubuntu:24.04` and `debian:bookworm-slim`, on the local machine.
