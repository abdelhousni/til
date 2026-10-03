# Inventory in AAP: sources from a project, smart and constructed inventories

Twenty-fourth entry in the Ansible inventory from scratch series. The earlier items ran everything with ansible-core on the command line. Many teams run their playbooks from *Ansible Automation Platform* (AAP) instead, Red Hat's product whose web interface and API, the *automation controller*, launch jobs; its open-source upstream is *AWX*. The controller keeps inventories in its database, and adds kinds of its own. This entry maps each of them to what the series showed in ansible-core, from the AWX source and documentation, and runs the ansible-core side.

No AWX or AAP ran for this entry. What AWX does is read from its repository, [ansible/awx](https://github.com/ansible/awx) at commit `33a9eb7` (2026-10-02), and marked as such: "according to the AWX docs" for `docs/`, "in the AWX source" for the code. Everything run below ran with ansible-core 2.21.4.

## What the controller runs: ansible-inventory

In the AWX source, an *inventory update*, the job that fills an inventory from an *inventory source*, runs one command (`build_args` in `awx/main/tasks/jobs.py`):

```sh
ansible-inventory --list --export -i <source> [--limit <limit>] --output <file>
```

`ansible-inventory --list` prints the whole inventory as JSON ([item 6](inventory-checking-with-ansible-inventory.md)). AWX then reads that JSON into its database. It runs the command with four environment variables (`STANDARD_INVENTORY_UPDATE_ENV` in `awx/main/constants.py`):

- `ANSIBLE_INVENTORY_EXPORT=True`, the same as `--export`;
- `ANSIBLE_INVENTORY_UNPARSED_FAILED=True`;
- `ANSIBLE_VERBOSE_TO_STDERR=True`, which keeps the JSON clean;
- `ANSIBLE_HOST_PATTERN_MISMATCH=error`, so a `--limit` that matches nothing fails.

So every controller inventory, whatever its kind, is something ansible-core can build. The example runs these commands, with that environment.

## An inventory source from a project

A *project* in AAP is a Git repository the controller checks out. According to the AWX docs (`docs/inventory/scm_inventory.md`), an inventory source of type *Sourced from a project* (`source: scm`) names a project and a `source_path` inside it, a file or a directory, and the update passes that path to `ansible-inventory -i`. Anything ansible-core accepts works: a hosts file with [`group_vars/` and `host_vars/`](inventory-directory-group-vars-per-role.md), a directory of several sources ([item 14](inventory-several-sources-load-order.md)), or an inventory plugin configuration file ([item 15](inventory-plugins-single-source-of-truth.md)). The same file serves on the command line and in the controller.

The example's `project/inventory/` is a hosts file with `app1`, `app2` and `db1`, `ntp_server` in `group_vars/all/`, `db_port: 5432` in `group_vars/db/` and `db_port: 5433` in `host_vars/db1/`. What `--export` printed:

```text
all: vars {"ansible_connection":"local","ntp_server":"ntp.example.com"}
db: hosts db1, vars {"db_port":5432}
db1: {"db_port":5433}
```

`--export` keeps each variable on the group or host that sets it; without it, `ansible-inventory` copied every group variable into each host. That is the shape AWX stores. In the AWX source (`awx/main/management/commands/inventory_import.py`), the variables of `all` become the inventory's *variables* field, each group's become the group's, and each host's the host's.

## Sync, overwrite and overwrite_vars

The controller reads a source only when it syncs it: by hand, on a schedule, or before each job with *update on launch*; according to the AWX docs, a source from a project can instead follow the project's own updates, and then can't update on launch. Between syncs, jobs use what the database holds, unlike `-i` on the command line, which reads the source on every run.

Two options of the source decide what a sync does with what's already there. In the AWX source (`awx/main/models/inventory.py` and `inventory_import.py`):

- **`overwrite`**, *"Overwrite local groups and hosts from remote inventory source"*: with it, the hosts and groups this source added earlier and no longer returns are deleted. Without it, they stay, so a server removed from the repository stays in the inventory.
- **`overwrite_vars`**, *"Overwrite local variables from remote inventory source"*: with it, the variables of each host and group are replaced by what the source returns. Without it, they're merged with `dict.update`: keys the source returns win, keys it no longer returns stay, including variables typed into the controller by hand.

Both are off by default in the AWX source. With a repository as the single source of truth ([item 15](inventory-plugins-single-source-of-truth.md)), both on keeps the controller in step with it.

## Variables: the same levels as files

Once stored, an inventory goes back to ansible-core when a job runs. In the AWX source (`get_script_data` in `awx/main/models/inventory.py`), the controller writes it as inventory script JSON ([item 15](inventory-plugins-single-source-of-truth.md#the-case)): the inventory's variables under `all`, each group's under the group, each host's in `_meta.hostvars`. So the precedence between them is ansible-core's, the one [item 9](inventory-precedence-depth-and-group-priority.md) measured: host over child group over parent group over `all`. In the example, db1 keeps 5433 from its host variables over its group's 5432, on the command line as it would in a job.

## Smart inventories and host_filter

A *smart inventory* is a kind of inventory with no source of its own: a `host_filter` selects hosts from the other inventories. In the AWX source and API docs (`awx/api/templates/api/host_list.md`, `awx/main/managers.py`):

- the filter queries the controller's host records, by name, by group (`groups__name="db"`), or by gathered facts (`ansible_facts__ansible_processor_vcpus=8`), with `and`, `or` and parentheses;
- it searches every inventory of the smart inventory's organization, and keeps one host per name;
- the smart inventory's JSON has only `all` and its hosts (`get_script_data`): no groups, so no group variables reach the job.

Its ansible-core counterpart is a [pattern](targeting-hosts-static-and-dynamic-inventory.md#the-patterns), or `--limit` ([item 12](inventory-limit-in-practice.md)). In the example, `groups__name=db` became `--limit db`, which gave db1 alone. A filter on variables has no pattern counterpart; it takes a `constructed` group, below.

According to the AWX docs (`docs/inventory/constructed_inventory.md`), constructed inventories overlap with smart ones, *"and it is intended that smart inventory is sunsetted and will be eventually removed"*. The AWX source still has the `smart` kind.

## Constructed inventories

A *constructed inventory* takes other inventories of the controller as *input inventories*, and runs the `ansible.builtin.constructed` plugin over them. [Item 11](targeting-hosts-static-and-dynamic-inventory.md#groups-built-from-a-variable) introduced that plugin and its `keyed_groups`; [item 18](inventory-constructed-keyed-groups-compose.md) covered its `groups` conditions and `compose` variables. In the controller, its configuration goes in the inventory's `source_vars`, and a `limit` keeps only the hosts it matches.

In the AWX source (`build_args`), the update passes each input inventory as a `-i` source, in their order, then the `source_vars` as a last `-i`, then `--limit`. So a constructed inventory can be rebuilt locally. The AWX docs' demo has two inputs, East and West:

```ini
# east.ini
host1 account_alias=product_dev
host2 account_alias=product_dev state=shutdown
host3 account_alias=sustaining
# west.ini
host4 account_alias=product_dev
host6 account_alias=product_dev state=shutdown
host5 account_alias=sustaining state=shutdown
```

with these `source_vars`, to act on the shut-down hosts of `product_dev`:

```yaml
plugin: ansible.builtin.constructed  # "constructed" in the docs
strict: true
use_vars_plugins: true
groups:
  shutdown: resolved_state == "shutdown"
  shutdown_in_product_dev: resolved_state == "shutdown" and account_alias == "product_dev"
compose:
  resolved_state: state | default("running")
```

and `limit: shutdown_in_product_dev`. The docs expect host2 and host6. The local command, with AWX's environment:

```sh
ansible-inventory -i east.ini -i west.ini -i constructed.yml --list --export --limit shutdown_in_product_dev
```

gave host2 and host6, in `shutdown` and `shutdown_in_product_dev`, with `resolved_state: shutdown`. host5 is shut down too, but in `sustaining`.

According to the AWX docs, a constructed inventory always updates before a job, and can also filter on facts the controller gathered, and on variables it adds such as `awx_inventory_name`. Neither was reproduced here.

### The inputs' inventory variables apply to every host

The example added `[all:vars] site=east` to East and `site=west` to West, as inventory variables of each input would be: AWX writes each input's variables under `all`. Merged into one inventory, there is one `all` group, and the last source loaded wins ([item 14](inventory-several-sources-load-order.md#two-sources-one-host-the-last-loaded-wins)): every host got `site: west`, East's hosts included; with the inputs in the other order, every host got `east`. In a constructed inventory, a variable that differs per input belongs on the hosts or groups, not on the input inventory.

### strict and a typo

The AWX docs insist on `strict: true`, so that a template that fails gives an error in the update. With a typo, `acount_alias`, and AWX's environment:

- `strict: true`: the `constructed` source failed on `'acount_alias' is undefined`, but `ANSIBLE_INVENTORY_UNPARSED_FAILED` only fails when *every* source fails to parse, and East and West parsed. Without a limit, the run exited 0 with the six hosts and no constructed group.
- `strict: false`: no error at all, and no host in the group.
- With the demo's limit, both exited 1, from `ANSIBLE_HOST_PATTERN_MISMATCH=error`: the group the limit names didn't exist.

So, in the commands AWX runs, the limit is what turns a broken template into a failed update. Whether AWX catches the warning some other way wasn't checked. To fail on any broken source locally or in CI, `ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED=True` made the same command exit 1, as item 15 showed. And without AWX's environment, a limit that matches nothing only warned and exited 0 with no hosts.

## In short

| AAP | ansible-core |
|---|---|
| Inventory source from a project | `-i <path in the repository>`: a directory, a file or a plugin configuration |
| Inventory, group and host variables | `all`, group and host variables, same precedence |
| Sync, `overwrite`, `overwrite_vars` | none: `-i` reads the source on each run |
| Smart inventory, `host_filter` | a pattern or `--limit`; a `constructed` group for variables |
| Constructed inventory, `source_vars`, `limit` | `-i` each input, `-i` a `constructed` file, `--limit` |

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/24-inventory-in-aap), holds the project inventory, the demo's inputs and `source_vars`, and the typo variants. `run.sh` runs the commands above with AWX's environment: the export of the project inventory, the smart filter as a pattern, the constructed inventory in both input orders, the typo with `strict` on and off, and a limit that matches nothing. Its CI runs it on every push and compares the output with the expected one.

## Sources

- AWX, [ansible/awx](https://github.com/ansible/awx) at commit `33a9eb7`: `docs/inventory/scm_inventory.md`, `docs/inventory/constructed_inventory.md`, `awx/api/templates/api/host_list.md`; `awx/main/tasks/jobs.py` (`build_args`), `awx/main/constants.py` (`STANDARD_INVENTORY_UPDATE_ENV`), `awx/main/models/inventory.py` (inventory kinds, `get_script_data`, `overwrite`, `overwrite_vars`), `awx/main/managers.py` (smart inventory hosts), `awx/main/management/commands/inventory_import.py` (what a sync stores, overwrites and merges).
- ansible-core 2.21.4: `lib/ansible/config/base.yml` (`INVENTORY_UNPARSED_IS_FAILED`, `INVENTORY_ANY_UNPARSED_IS_FAILED`).
- Every run result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine. Nothing above was run on AWX or AAP.
