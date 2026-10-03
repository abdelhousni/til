# Hosts and groups: the two groups every inventory has, all and ungrouped

First entry in the Ansible inventory from scratch series. Ansible runs tasks on remote machines, its *managed hosts*, from one machine, the *controller*, where `ansible-playbook` runs. It finds the hosts in the *inventory*: a list of host names, sorted into named *groups*, that a play targets with `hosts:`. This entry writes a small inventory in YAML and shows what Ansible builds from it, including two groups nobody wrote: `all` and `ungrouped`. Everything below ran with ansible-core 2.21.4.

## The inventory

A PostgreSQL server, three application servers, and a jump host, the machine people connect through to reach the others:

```yaml
all:
  hosts:
    jump1:              # in no group of its own
  children:
    app:
      hosts:
        app1:
        app2:
        app3:
    postgresql:         # a parent group: every host of db is in it too
      children:
        db:
          hosts:
            db1:
    backup:             # db1 again: a host can be in several groups
      hosts:
        db1:
```

The YAML format nests three keys:
- `hosts:` lists the hosts of a group. The colon after each name is there because a host can carry variables; here none does.
- `children:` lists groups inside a group. A group inside another is its *child*, the outer one its *parent*, and a host of the child is a host of the parent too.
- The top level is always `all`.

The file, `inventory/hosts.yml`, holds no variables at all. The connection settings sit in `inventory/group_vars/all/`, the files Ansible reads for every host of the group `all`; later entries cover variables.

## What Ansible builds from it

`ansible-inventory --graph` prints the groups as a tree:

```
@all:
  |--@ungrouped:
  |  |--jump1
  |--@app:
  |  |--app1
  |  |--app2
  |  |--app3
  |--@postgresql:
  |  |--@db:
  |  |  |--db1
  |--@backup:
  |  |--db1
```

A host listed directly under `all`, in no other group, went into `ungrouped`, a group the file never names. `db1` appears twice, once per group; it's still one host.

## groups and group_names

Two *magic variables*, which Ansible sets itself, give the same information to a playbook:
- **`groups`** maps every group name to the list of its hosts.
- **`group_names`** is, for one host, the list of the groups it's in, sorted.

From the example's playbook, which writes both out:

```
groups:
  all: ['jump1', 'app1', 'app2', 'app3', 'db1']
  app: ['app1', 'app2', 'app3']
  backup: ['db1']
  db: ['db1']
  postgresql: ['db1']
  ungrouped: ['jump1']
group_names, per host:
  app1: ['app']
  db1: ['backup', 'db', 'postgresql']
  jump1: ['ungrouped']
```

(app2 and app3 are like app1.) Three things show:
- **`db1` is in `postgresql`** without being listed there: it inherited the parent through `db`.
- **`jump1`'s `group_names` is `['ungrouped']`**, not empty. A test like `'ungrouped' in group_names` finds the hosts someone forgot to put in a group.
- **`all` is in nobody's `group_names`**, although every host is in `groups['all']`. The inventory guide, *How to build your inventory*, warns about this: *"Although `all` and `ungrouped` are always present, they can be implicit and might not appear in group listings like `group_names`."* Here `ungrouped` did appear and `all` didn't, so don't rely on either being listed; test `all` with `groups['all']`.

## localhost is not in all

The playbook runs on `localhost`, the controller itself, and the inventory doesn't define it. Ansible then creates an *implicit* `localhost` (the guide's *Implicit 'localhost'* page): a host that works with `hosts: localhost` and `delegate_to: localhost`, but isn't in any group. `groups['all']` above lists five hosts, not six, and `hosts: all` doesn't run on the controller. Defining `localhost` in the inventory makes it an ordinary host, in `all` and `ungrouped` like `jump1`, and drops the implicit behaviour.

## In short

- **Every inventory has `all` and `ungrouped`**: `all` holds every host, `ungrouped` the hosts in no group of their own.
- **A host can be in several groups**, and a host of a child group is in its parents.
- **`groups` lists both**; `group_names` may leave them out, and in ansible-core 2.21 left out `all`.
- **The implicit `localhost` is in no group**, `all` included.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/01-hosts-and-groups), holds this inventory, with every host connecting locally so that nothing needs a real server. `run.sh` prints the graph and runs `groups.yml`, which writes `groups` and each host's `group_names` to its `out/` directory. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*Default groups*, the YAML format, parent and child groups), `inventory_guide/implicit_localhost.rst`, and `reference_appendices/special_variables.rst` (`groups`, `group_names`).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
