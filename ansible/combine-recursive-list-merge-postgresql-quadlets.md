# Merging dicts with combine: PostgreSQL settings in layers, Quadlet units from a base

Third entry in the Shaping data in Ansible series. [Part 1](readable-sudoers-with-dict-kv.md) explains dicts (key–value mappings), filters and `combine`, which merges dicts. There the keys never overlapped. This entry is about what happens when they do:
- a key in both dicts;
- a dict inside a dict;
- a list in both.

The examples are PostgreSQL settings with defaults overridden per group and per host, and Podman Quadlet units built from a shared base. Everything below ran with ansible-core 2.21.4.

## How combine merges

`a | combine(b, c)` merges from left to right: on a key that several dicts have, the rightmost one wins. `[a, b, c] | combine` does the same with the dicts in a list. Two keyword arguments change what "wins" means:
- **`recursive`** (default `False`): when both values are dicts, merge them key by key instead of replacing the left one;
- **`list_merge`** (default `replace`): when both values are lists, `replace` keeps the right one, `keep` the left one, `append` and `prepend` join them, and `append_rp` and `prepend_rp` join them after dropping the left list's items that the right list also has. Lists nested in dicts are only reached with `recursive=True`.

Any other pair of values, a string against a list for example, is replaced by the right one.

## PostgreSQL settings in layers

The PostgreSQL system role, one of the Linux System Roles that part 1 introduces, takes `postgresql_server_conf`, a dict of `postgresql.conf` settings. Its template, `templates/postgresql.conf.j2` in version 1.9.0, writes one `key = value` line per key.

Settings like these are usually layered through the *inventory*, Ansible's list of hosts and of the groups they belong to. Variables can sit next to it:
- in `group_vars/all.yml` for every host;
- in `group_vars/<group>.yml` for one group;
- in `host_vars/<host>.yml` for one host.

When the same variable is defined in several of those files, Ansible's *variable precedence* picks one, here host over group over `all`. It picks the whole value: dicts aren't merged.

The test inventory had two hosts, `pg-test-1` and `pg-prod-1`, the second in a group `pg_prod`. With the variable redefined at each level:

```yaml
# group_vars/all.yml
postgresql_server_conf:
  ssl: "on"
  shared_buffers: 128MB
  huge_pages: try

# group_vars/pg_prod.yml
postgresql_server_conf:
  shared_buffers: 4GB
  huge_pages: "on"

# host_vars/pg-prod-1.yml
postgresql_server_conf:
  max_connections: 200
```

The role's template wrote, after its header:

| Host | `postgresql.conf` |
|---|---|
| `pg-test-1` | `ssl = on`, `shared_buffers = 128MB`, `huge_pages = try` |
| `pg-prod-1` | `max_connections = 200` |

The production host lost `ssl`, `shared_buffers` and `huge_pages`, and the group's values never applied. `"on"` is quoted because YAML reads a bare `on` as true: unquoted, the file said `ssl = True`.

**The fix is to give each layer its own name** and merge them in one place:

```yaml
# group_vars/all.yml
postgresql_server_conf_all:
  ssl: "on"
  shared_buffers: 128MB
  huge_pages: try

postgresql_server_conf: "{{ postgresql_server_conf_all
  | combine(postgresql_server_conf_group | default({}),
            postgresql_server_conf_host | default({})) }}"

# group_vars/pg_prod.yml
postgresql_server_conf_group:
  shared_buffers: 4GB
  huge_pages: "on"

# host_vars/pg-prod-1.yml
postgresql_server_conf_host:
  max_connections: 200
```

`default({})` stands in for a layer a host doesn't have. Ansible evaluates `postgresql_server_conf` when the role uses it, for each host, so each host gets its own layers. `pg-prod-1` then got `ssl = on`, `shared_buffers = 4GB`, `huge_pages = on`, `max_connections = 200`, and `pg-test-1` was unchanged. A key that's overridden keeps its place in the file: `shared_buffers` stayed second.

These settings are flat, so `recursive` makes no difference here.

**`hash_behaviour = merge`** in `ansible.cfg`, or `ANSIBLE_HASH_BEHAVIOUR=merge`, makes Ansible merge dicts across all variable sources instead. With the first inventory, it gave `pg-prod-1` the same four settings. Its description in ansible-core's `config/base.yml` advises against it: *"The Ansible project recommends you **avoid `merge` for new projects.**"* It changes how every variable source behaves, for every role in the run, while roles are written for the default, and the developers intend to eventually deprecate and remove it. The same description recommends `combine` instead.

## Quadlet units from a base

*Quadlet* describes Podman containers as systemd unit files. The podman role takes each unit as a dict whose keys are the unit's sections, `Container` and `Install`, plus the role's own keys such as `name` and `type`. A list value becomes one line per item, which is how a key like `Environment` repeats ([this entry](podman-quadlet-caddy-adminer-php-linux-system-roles.md) covers the role and this Caddy + Adminer + PHP stack).

Every container in that stack repeated the same `Install` section and the same network. Moved into a base, with a time zone added:

```yaml
quadlet_container_base:
  type: container
  Install:
    WantedBy: default.target
  Container:
    Network: appnet.network
    Environment:
      - TZ=UTC

quadlet_containers:
  - name: adminer
    Container:
      Image: docker.io/library/adminer:latest
      ContainerName: adminer
      Environment: ADMINER_DEFAULT_SERVER=postgres     # one value, as a string
  - name: caddy
    Container:
      Image: docker.io/library/caddy:2-alpine
      ContainerName: caddy
      PublishPort: "80:80"
      Volume: [/srv/Caddyfile:/etc/caddy/Caddyfile:ro, /srv/app:/srv:ro]
      Environment: [TZ=Europe/Brussels]                # meant to replace TZ=UTC
  - name: php
    Container:
      Image: docker.io/library/php:8.3-fpm-alpine
      ContainerName: php
      Volume: /srv/app:/srv:ro
      Environment: [TZ=UTC]                            # copied from before the base
```

Each container's dict has to go on the right of the base, so that its values win. Part 1's `map('combine', base)` puts the base on the right instead. That was harmless there, with no shared keys. Here the base's `Container` replaced each container's whole `Container`, and all three units came out without an `Image`.

`product` pairs every item of one list with every item of another. With the base alone in the first list, it gives one `[base, container]` pair per container, and `map('combine')` merges each pair in that order:

```yaml
podman_quadlet_specs: "{{ [quadlet_container_base] | product(quadlet_containers)
  | map('combine', recursive=True, list_merge='append_rp') | list }}"
```

Each result went through the podman role's own key filter and template, `templates/systemd.j2` in version 1.14.3. The `Environment` lines of each unit, for each way of merging. From `recursive=True` on, all three also had `Network=appnet.network`:

| Merge | adminer | caddy | php |
|---|---|---|---|
| `combine`, no `Network` | `ADMINER_DEFAULT_SERVER=postgres` | `TZ=Europe/Brussels` | `TZ=UTC` |
| `recursive=True` | `ADMINER_DEFAULT_SERVER=postgres` | `TZ=Europe/Brussels` | `TZ=UTC` |
| `recursive=True, list_merge='append'` | `ADMINER_DEFAULT_SERVER=postgres` | `TZ=UTC`, `TZ=Europe/Brussels` | `TZ=UTC` twice |
| `recursive=True, list_merge='append_rp'` | `ADMINER_DEFAULT_SERVER=postgres` | `TZ=UTC`, `TZ=Europe/Brussels` | `TZ=UTC` |

- **Without `recursive`**, each container's `Container` replaced the base's, so `Network=appnet.network` disappeared from all three. `Install` came through, since no container had one.
- **With `recursive=True`**, `Network` came through, and with the default `list_merge='replace'` each container's `Environment` replaced the base's. That was right for caddy, but adminer lost `TZ=UTC`.
- **`append`** kept both lists, so php wrote `Environment=TZ=UTC` twice. **`append_rp`** dropped the copy.
- **adminer never got `TZ=UTC`.** Its `Environment` was a string, and a string against a list is replaced, whatever `list_merge` says. Write a key as a list in every dict that may be merged, even when it holds one value.
- **caddy kept both time zones** with `append` and `append_rp`. `append_rp` drops identical items only, and `TZ=UTC` isn't identical to `TZ=Europe/Brussels`. The unit file then had both lines.

No `list_merge` mode merges `NAME=value` strings by name. Keeping the environment as a dict does. At the end, the `items` filter turns the dict into `[name, value]` pairs, and `map('join', '=')` joins each pair into the `NAME=value` string the role expects:

```yaml
quadlet_environment_base:
  TZ: UTC

caddy_environment: "{{ quadlet_environment_base | combine({'TZ': 'Europe/Brussels'})
  | items | map('join', '=') | list }}"
```

That gave `['TZ=Europe/Brussels']` for caddy and `['TZ=UTC', 'ADMINER_DEFAULT_SERVER=postgres']` for adminer.

## Which one

- **Variables that several inventory levels set:** one name per layer, merged with `combine`, rightmost layer winning.
- **Nested dicts:** `recursive=True`, or the inner dicts are replaced whole.
- **Lists:** pick `list_merge` per merge. `replace` for lists that override, `append_rp` for lists that add up, and a dict when the items are really `NAME=value` pairs.
- **Defaults in a base:** put the base on the left, `[base] | product(items) | map('combine', …)`.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/03-combine-layers-and-quadlets), runs all of the above on the local machine, changing nothing outside its `out/` directory:
- `render-postgresql.yml` renders the postgresql role's template for both hosts, with each inventory and with `ANSIBLE_HASH_BEHAVIOUR=merge`;
- `render-quadlets.yml` builds the three units in each way above, plus `map('combine', base)`, and renders them with the podman role's template. It also merges the environment as dicts.

Its CI runs both on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`combine`), `utils/vars.py` (`merge_hash`, for `recursive` and each `list_merge` mode) and `config/base.yml` (`DEFAULT_HASH_BEHAVIOUR`).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Combining hashes/dictionaries*.
- Linux System Roles, cloned at their release tags from [github.com/linux-system-roles](https://github.com/linux-system-roles): postgresql 1.9.0 (`README.md`, `templates/postgresql.conf.j2`) and podman 1.14.3 (`templates/systemd.j2`, `tasks/handle_quadlet_spec.yml`).
- Every rendered file above came from ansible-core 2.21.4 on 2026-10-01, on the local machine. Nothing was installed on a PostgreSQL server or run with Podman.
