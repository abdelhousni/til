# subelements versus product: Quadlet volume directories and PostgreSQL pg_hba rules

Fifth entry in the Shaping data in Ansible series. Two filters pair items so that a single loop or template can go over every combination:
- **`subelements`** pairs each item of a list with each value of a list *inside that item*: each container with each of its own volumes;
- **`product`** pairs every item of one list with every item of another: every database with every client subnet.

[Part 3](combine-recursive-list-merge-postgresql-quadlets.md) introduced `product` to put a base on the left of each Quadlet unit. This entry compares the two on part 3's Podman containers and on PostgreSQL's client authentication rules. Everything below ran with ansible-core 2.21.4 and community.general 13.4.0.

## subelements: each container × its own volumes

Part 3's Caddy + Adminer + PHP stack, from [this entry](podman-quadlet-caddy-adminer-php-linux-system-roles.md), describes each container as a dict whose `Container` section becomes the Quadlet unit. `Volume` lists the container's *bind mounts*, directories or files of the host made visible inside the container, as `host_path:container_path:options`:

```yaml
quadlet_containers:
  - name: adminer
    Container:
      Image: docker.io/library/adminer:latest
  - name: caddy
    Container:
      Image: docker.io/library/caddy:2-alpine
      Volume:
        - /srv/Caddyfile:/etc/caddy/Caddyfile:ro
        - /srv/app:/srv:ro
  - name: php
    Container:
      Image: docker.io/library/php:8.3-fpm-alpine
      Volume: /srv/app:/srv:ro
```

Podman doesn't create a missing host path. Its `--volume` documentation, which Quadlet's `Volume=` follows: *"If the source does not exist, Podman returns an error. Users must pre-create the source files or directories."* So the playbook has to, before the units start. That's a loop over every container × each of its volumes. `subelements(path)` builds it: for each item, it takes the list at `path` and returns one `[item, value]` pair per value. The path can be dotted, so `Container.Volume` reaches into each container's `Container` section:

```yaml
"{{ quadlet_containers | subelements('Container.Volume') }}"
```

On this data it fails twice, in two different ways:

| Expression | Result |
|---|---|
| `subelements('Container.Volume')` | *"could not find 'Volume' key in iterated item"*, on adminer |
| `subelements('Container.Volume', skip_missing=True)` | *"the key 'Volume' should point to a list, got '/srv/app:/srv:ro'"*, on php |

- **`skip_missing=True`** skips items that don't have the key at all. adminer has no volume, so it's skipped.
- **It doesn't skip a key that holds a string.** php's `Volume` is one value, written as a string, and `subelements` requires a list. The fix is the one part 3 came to: write a key as a list in every dict that may hold several values, `Volume: [/srv/app:/srv:ro]`.

With php's `Volume` as a list, the pairs are caddy with `/srv/Caddyfile:…`, caddy with `/srv/app:…` and php with `/srv/app:…`. Two more steps before creating anything:

```yaml
host_sources: "{{ quadlet_containers | subelements('Container.Volume', skip_missing=True)
  | map(attribute='1') | map('split', ':') | map('first') | unique | list }}"
```

1. `map(attribute='1')` keeps the second item of each pair, the volume ([part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md) explains `map` and numeric attributes). `split(':')` and `first` keep its host path.
2. `unique` drops the second `/srv/app`, which caddy and php share.

That gave `['/srv/Caddyfile', '/srv/app']`. `/srv/Caddyfile` is a file, and nothing in the `Volume` line says so: a task creating every host path as a directory would create a directory called `Caddyfile`. The playbook has to be told which ones are files, `host_sources | difference(['/srv/Caddyfile'])`, leaving `/srv/app` to create.

### The podman role already does this, with a bug in 1.14.3

The podman system role creates host directories itself when `podman_create_host_directories` is true (it's false by default). For a unit given as a dict, as here, version 1.14.3 finds the host paths with `map('regex_search', '^([^:]+):.+$')` in `tasks/handle_quadlet_spec.yml`. Run on the same three containers:

| Container | Paths 1.14.3 creates as directories | Upstream `main` |
|---|---|---|
| adminer | none | none |
| caddy | `/srv/Caddyfile:/etc/caddy/Caddyfile:ro`, `/srv/app:/srv:ro` | `/srv/Caddyfile`, `/srv/app` |
| php | none | `/srv/app` |

- `regex_search` without a group argument returns the whole match, so the "paths" are the full `Volume` strings.
- php's string is iterated character by character, and no single character matches, so php gets nothing.

The role's maintainers fixed both on 2026-09-30 ([linux-system-roles/podman#336](https://github.com/linux-system-roles/podman/issues/336)): the new code wraps a string in a list and keeps only the captured path. On 2026-10-02 the fix wasn't in a release yet; the latest tag was still 1.14.3. Even fixed, the role creates `/srv/Caddyfile` as a directory unless `podman_host_directories` sets that path's options, so the same "which ones are files" question applies.

## product: every database × every client subnet

PostgreSQL decides who may connect with `pg_hba.conf`, one rule per line: connection type, database, user, client address and authentication method. It uses the **first** line that matches a connection, so the order of the lines matters. The PostgreSQL system role, from part 3, writes the file from `postgresql_pg_hba_conf`, a list of dicts with those keys; its template, `templates/pg_hba.conf.j2` in version 1.9.0, writes one line per dict.

Two databases, `app` and `reporting`, both reachable from two client *subnets*, ranges of addresses written as `10.10.0.0/24`. Every database × every subnet is a `product`:

```yaml
pg_hba_base:
  type: hostssl
  user: all
  auth_method: scram-sha-256

postgresql_pg_hba_conf: "{{ [pg_hba_base]
  | product(pg_databases | map('community.general.dict_kv', 'database'),
            pg_client_subnets | map('community.general.dict_kv', 'address'))
  | map('combine') | list }}"
```

- **`dict_kv`** turns each name into a one-key dict, `{'database': 'app'}` ([part 1](readable-sudoers-with-dict-kv.md) explains it).
- **`product` takes more than two lists.** With three, each result is a `[base, database, address]` triple, and `map('combine')` merges each triple into one rule. The base is on the left, as part 3 recommends, so per-rule keys would win.

With `pg_databases: [app, reporting]` and `pg_client_subnets: [10.10.0.0/24, 10.20.0.0/24]`, the role's template wrote, after a `local all all peer` line for the server's own socket:

```
hostssl app all 10.10.0.0/24 scram-sha-256
hostssl app all 10.20.0.0/24 scram-sha-256
hostssl reporting all 10.10.0.0/24 scram-sha-256
hostssl reporting all 10.20.0.0/24 scram-sha-256
```

The order follows the lists: all subnets for the first database, then for the second. Loaded into PostgreSQL 16.14 and read back from its `pg_hba_file_rules` view, every line parsed. With SSL off, each `hostssl` line carried the error *"hostssl record cannot match because SSL is disabled"*. With `ssl = on` and a certificate, as part 3's settings have, the errors were gone.

**An empty list gives no rules, without an error.** With `pg_client_subnets: []`, `product` returned nothing, and the file kept only the `local` line: no remote client could connect. An `ansible.builtin.assert` task on the generated rules, `that: pg_hba_rules | length > 0`, stops the play before the role writes that file.

## Which one

When each database has its own clients, the data is nested, and `subelements` is the one:

```yaml
pg_databases_own_clients:
  - name: app
    clients: [10.10.0.0/24, 10.20.0.0/24]
  - name: reporting
    clients: [10.30.0.0/24]
  - name: scratch    # local connections only
```

`subelements('clients', skip_missing=True)` gave three pairs: `app` with each of its two subnets, and `reporting` with its own. `scratch` has no `clients` and was skipped. Turned into rules with `map(attribute='0.name')`, `map(attribute='1')` and part 2's [`zip`](lists-and-dicts-dict2items-items2dict-zip.md), the role wrote three `hostssl` lines where `product` wrote four.

- **Each item has its own list inside it:** `subelements(path)`. `skip_missing=True` for items without the key, but write the key as a list everywhere.
- **Independent lists, every combination:** `product(other, …)`, with any number of lists. Check that none of them is empty.
- **Before acting on the pairs:** drop duplicates with `unique`, and don't assume every path is a directory.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/05-subelements-and-product), runs all of the above on the local machine, changing nothing outside its `out/` directory:
- `volumes.yml` runs `subelements` on part 3's container data, with both errors, creates the bind source directories under `out/`, and computes the podman role's host paths with the 1.14.3 and the fixed expression;
- `pg_hba.yml` builds the rules with `product` and with `subelements`, renders both with the postgresql role's template, and checks the empty-subnet case.

Its CI runs both on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`subelements`, including the dotted path and what `skip_missing` catches), `plugins/filter/mathstuff.py` (`product` is Python's `itertools.product`), `plugins/lookup/subelements.py`.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Combining objects and subelements* and *products*.
- Linux System Roles, from [github.com/linux-system-roles](https://github.com/linux-system-roles): podman 1.14.3 (`tasks/handle_quadlet_spec.yml`, `tasks/create_update_quadlet_spec.yml`, `defaults/main.yml`) and its `main` branch at commit f48fc8e, "fix: create host directories from quadlet Volume host paths"; postgresql 1.9.0 (`README.md`, `templates/pg_hba.conf.j2`).
- Podman documentation, from [containers/podman](https://github.com/containers/podman): `docs/source/markdown/options/volume.md` (missing bind sources) and `podman-systemd.unit.5.md` (`Volume=`).
- PostgreSQL 16 documentation, [The pg_hba.conf File](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html), and its `pg_hba_file_rules` view; checked on PostgreSQL 16.14 from Ubuntu's packages.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine. Nothing was installed with Podman, and no PostgreSQL server was configured by the role.
