# Inventory precedence: all, parent, child, host, and what ansible_group_priority really does

Ninth entry in the Ansible inventory from scratch series. [Item 8](inventory-where-a-variable-should-live.md) ranked the places a variable can live, with the inventory's `group_vars/` and `host_vars/` as the home of desired state. Inside the inventory, the same name can still be set for `all`, for several groups a host belongs to, and for the host itself. This entry peels one value back level by level to show which wins, then debugs a real conflict where the obvious fix, `ansible_group_priority`, does nothing. Everything below ran with ansible-core 2.21.4.

## The inventory

db1 and db2 are in `db`, a *child* of `postgresql`, and in `backup`, a group next to `postgresql`: [item 1](inventory-hosts-groups-all-ungrouped.md) explains parent and child groups. Each group has a *depth*, its distance from `all`: `all` is 0, `postgresql` and `backup` are 1, `db` is 2. A group with several parents takes the longest path; ansible-core's `inventory/group.py` sets a child's depth to its parent's plus one, keeping the maximum.

## One value, removed level by level

`postgresql_max_connections` was set in five places: `all` 10, `postgresql` 20, `backup` 40, `db` 30, `host_vars/db1` 50. The example read db1's value with `ansible-inventory --host db1`, removed the winning level, and read again:

| Set in | db1 got | Removed next |
|---|---|---|
| all five | 50 | `host_vars/db1` |
| `all`, `postgresql`, `backup`, `db` | 30 | `group_vars/db` |
| `all`, `postgresql`, `backup` | 20 | `group_vars/postgresql` |
| `all`, `backup` | 40 | `group_vars/backup` |
| `all` | 10 | |

- **The host wins** over every group.
- **Then the deepest group:** `db`, depth 2, beat both depth-1 groups, whatever their names.
- **Between groups at the same depth, the name decides:** `postgresql` beat `backup` because it sorts after it, as [item 5](inventory-environments-directories-or-groups.md) found with environment groups. The docs: *"Ansible merges groups at the same parent/child level in alphabetical order. Variables from the last group that Ansible loads overwrite variables from the previous groups."*
- **`all` comes last**, as the default for everyone.

The order comes from one line in `inventory/helpers.py`: groups are sorted by `(g.depth, g.priority, g.name)`, merged in that order, and the last one sets the value; host variables are applied after all groups.

### Dicts are replaced, not merged

`postgresql_conf`, a dict, was `{max_connections: 100, shared_buffers: 128MB}` in `all` and `{max_connections: 200}` in `postgresql`. db2 got `{"max_connections": 200}`: `shared_buffers` was gone. Each level replaces the whole value. [Part 3 of the data-shaping series](combine-recursive-list-merge-postgresql-quadlets.md) shows the alternative: one variable per layer, merged explicitly with `combine`.

## ansible_group_priority breaks ties, not depth

`ansible_group_priority` is a number on a group, 1 by default; a higher number merges later and wins. The docs say what it applies to: it *"overrides the alphabetical sorting for the merge order for groups of the same level (after Ansible resolves the parent/child order)"*, and it can be set *"only in an inventory source, not in `group_vars/`"*. With `ansible_group_priority: 10` on `backup`, in the hosts file:
- **against `postgresql`, at the same depth, `backup` won:** 40;
- **against `db`, one level deeper, `backup` still lost:** 30.

Priority is the second item of the sort key, after depth: it reorders groups of one depth, and nothing else.

## A real conflict, and the fix that doesn't work

db1 is backed up, so it's in `backup`, whose `group_vars` set `postgresql_wal_level: replica`, the level WAL archiving needs. `db` sets `postgresql_wal_level: minimal` as the default for database servers. db1 got **`minimal`**, and backups would fail.

`ansible-inventory --graph --vars`, from [item 6](inventory-checking-with-ansible-inventory.md), shows where it comes from:

```
|--@postgresql:
|  |--@db:
|  |  |--db1
|  |  |  |--{postgresql_wal_level = minimal}
|  |  |--{postgresql_wal_level = minimal}
|--@backup:
|  |--db1
|  |  |--{postgresql_wal_level = minimal}
|  |--{postgresql_wal_level = replica}
```

Each group's own value is listed after its hosts, at the same indentation: `backup` says `replica`. The value nested under db1 is the host's merged value, the same under every group that lists it: `minimal`, from `db`, the deeper group.

- **Adding `ansible_group_priority: 10` to `backup`** left db1 at `minimal`: `backup` is at depth 1, `db` at 2, and priority doesn't cross depths.
- **Moving `backup` under `postgresql`**, as the database role it is, put it at depth 2 next to `db`. With the same priority, db1 got **`replica`** and db2, not backed up, kept `minimal`.

Setting the value in `host_vars/db1` would also have worked, for one host; the group structure fixes it for every backed-up server.

## In short

- **Order:** `all`, then groups by depth, shallowest first; at the same depth by `ansible_group_priority`, then by name; then the host. The last one sets the value.
- **A deeper group wins** over a shallower one, whatever its priority.
- **`ansible_group_priority`** goes in the hosts file and only reorders groups of the same depth.
- **Dicts don't merge** across levels; each level replaces the whole value.
- **To debug:** `ansible-inventory --graph --vars` lists each group's own value after its hosts, and nests the host's merged value under the host.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/09-inventory-precedence), holds these inventories. `run.sh` removes the winning level one at a time from a copy in its `out/` directory, compares priority at the same depth and across depths, and prints the conflict before and after each fix, with the `--graph --vars` view. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_inventory.rst` (*How variables are merged*, `ansible_group_priority`).
- ansible-core 2.21.4: `inventory/helpers.py` (`sort_groups`, the `(depth, priority, name)` key) and `inventory/group.py` (how depth is computed).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
