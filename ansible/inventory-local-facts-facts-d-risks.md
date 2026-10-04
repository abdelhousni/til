# Local facts in facts.d: declared data that looks measured

Twenty-sixth entry in the Ansible inventory from scratch series, a follow-up to [item 7](inventory-facts-or-variables-as-is-to-be.md). Item 7 split what a host is (*as-is*, discovered as facts) from what it should be (*to-be*, declared in the inventory), and compared the two to find drift. Ansible has a way to hand a host extra facts of your own, and it blurs that split. This entry shows how, on two PostgreSQL hosts, with ansible-core 2.21.4.

## What local facts are

*Facts* are the values Ansible gathers from a host at the start of a play: its OS, its packages, its addresses. *Local facts* add your own. A file ending in `.fact` in `/etc/ansible/facts.d/` on the host is read during fact gathering, and its content lands under the variable `ansible_local`, keyed by the file name. The Ansible docs, *Discovering variables: facts and magic variables*, list the forms: a JSON file, an INI file, or an executable that prints JSON. The `fact_path` play keyword changes the directory.

Both hosts in the example run the PostgreSQL 15 client, and the inventory's `group_vars/postgresql/` declares `postgresql_version: 16`. Each host gets `/etc/ansible/facts.d/postgresql.fact`:

- **db-typed** has a file someone wrote by hand, with the version they expected:
  ```ini
  [server]
  Version=16
  ```
- **db-measured** has a script that asks the host:
  ```sh
  #!/bin/sh
  version=$(psql --version | sed -E 's/^[^0-9]* ([0-9]+)\..*/\1/')
  printf '{"server": {"version": "%s"}}\n' "$version"
  ```

## The drift check trusts the typed file

A playbook compares the declared version with `ansible_local.postgresql.server.version`, as item 7 compared it with the installed packages:

```text
db-measured: declared 16, local fact 15: drift
db-typed: declared 16, local fact 16: ok
```

db-typed runs 15 too, and passes. The hand-written file is declared data, a to-be value, but it arrives through fact gathering, next to the measured facts, and nothing tells a play which is which. It's item 7's *don't write the discovered value back* the other way round: a chosen value written where measured ones go. Item 7's advice holds here too: an exception belongs in `host_vars/`, with a comment and a Git history, not in a file on the host that no review sees. A local fact is only worth comparing against when it's a script that measures, like db-measured's.

The file said `Version`, and the play read `version`: INI keys come back lowercased. The docs explain why: Ansible reads INI files with Python's `ConfigParser`, which lowercases option names.

## ansible_local ignores the switch that hides other facts

Item 7 recommended reading facts as `ansible_facts.<name>` and turning off `INJECT_FACTS_AS_VARS`, the setting that also copies each fact into a top-level variable such as `ansible_distribution`. With `ANSIBLE_INJECT_FACT_VARS=false`, `ansible_distribution` was undefined, as expected, but `ansible_local` was still there. ansible-core's `vars/manager.py` makes the exception on purpose: *"always 'promote' ansible_local, even if empty"*. Inside `ansible_facts`, the key is `ansible_local` too, not `local`.

## Gathered facts beat the inventory

A second inventory source gave db-typed an `ansible_local` in its `host_vars/`, with a version of 99:

- the play that gathered facts saw 16, the local fact's value;
- with `gather_facts: false` and an empty fact cache, it saw 99.

In the precedence list of the Ansible docs, *host facts* rank 11th of 22, above inventory `host_vars/*` at 9th; [item 8](inventory-where-a-variable-should-live.md) walks through that list. ansible-lint rejects the file anyway: *"This special variable is read-only. (ansible_local)"*. The example keeps it, with a `noqa` comment, to show what happens.

## The fact cache keeps a deleted local fact

Item 7 turned on a *fact cache*, which keeps gathered facts between runs, a JSON file per host. After one run, the example deleted db-typed's `postgresql.fact`:

| Reader | What it showed for `ansible_local` |
|---|---|
| `ansible-inventory --host db-typed` | `{'postgresql': {'server': {'version': '16'}}}`, from the cache |
| `ansible-inventory --host db-typed --export` | nothing: `--export` shows inventory variables only |
| a play with `gather_facts: false` | 16, from the cache |
| a play that gathers facts | undefined |

A typed value that was never true can keep showing up in the inventory's output, looking as official as `postgresql_version`, until a play gathers facts again.

## In short

- **Declared values go in `group_vars/` and `host_vars/`**, where they're reviewed. A local fact holding a chosen value is a to-be value disguised as an as-is one.
- **A local fact should measure something:** an executable that asks the host, not a file someone types.
- **`ansible_local` is always a top-level variable**, whatever `INJECT_FACTS_AS_VARS` says, and gathered facts override an inventory variable of that name.
- **With a fact cache, a local fact outlives its file** in `ansible-inventory --host` and in plays that don't gather facts.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/26-local-facts), holds the image behind both hosts, pinned by digest, the inventory, both local facts and the playbooks. `run.sh` starts the hosts with Docker, Podman or a kind cluster, copies each local fact in, runs the drift check, then the four checks above. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible documentation, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_vars_facts.rst` (*facts.d or local facts*, `fact_path`, keys lowercased by `ConfigParser`) and `playbook_guide/playbooks_variables.rst` (*Understanding variable precedence*).
- ansible-core 2.21.4: `vars/manager.py` (`ansible_local` always promoted, and exempt from the top-level fact deprecation) and `module_utils/facts/system/local.py`.
- Every result above came from ansible-core 2.21.4 and community.docker 5.3.0 on 2026-10-04, with containers from `debian:bookworm-slim`, on the local machine, and with Podman 4.9.3 for the same output.
