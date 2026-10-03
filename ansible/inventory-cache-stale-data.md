# When the inventory cache lies: stale hosts, cache_timeout and --flush-cache

Nineteenth entry in the Ansible inventory from scratch series. [Item 15](inventory-plugins-single-source-of-truth.md) read hosts from a mock CMDB (Configuration Management Database, where an IT department records its servers) with a small inventory plugin of the example's own, and turned on its *inventory cache*: the plugin keeps what it read from the CMDB and answers from that copy on later runs, instead of calling the CMDB again. That entry covers what a plugin is, how `auto` loads it and the basic cache options, so they aren't repeated here. This one is about the cost of the cache: data that is out of date, or *stale*, and a play that runs against what the cache says rather than what the CMDB says. The performance side, what the cache saves, is the subject of the next entry, *The inventory cache and performance*. Everything below ran with ansible-core 2.21.4.

## The case

The example reuses item 15's plugin unchanged and its two CMDB lists:

- **v1**: app1 and app2 in group `app`, db1 in group `db`.
- **v2**: app2 decommissioned (switched off and removed from the CMDB), app3 added.

Each run of `ansible-inventory --list` (see [item 6](inventory-checking-with-ansible-inventory.md)) prints the hosts it got. The cache is set in the plugin's configuration file with the options of ansible-core's `inventory_cache` documentation fragment:

- `cache: true` turns it on;
- `cache_plugin` names the *cache plugin*, the backend that stores the data;
- `cache_connection` tells that backend where to store it, a directory for file-based plugins;
- `cache_timeout` is how long, in seconds, the stored data stays valid: 3600 by default;
- `cache_prefix` is put at the start of each stored key or file name: `ansible_inventory_` by default.

## memory or jsonfile

The default `cache_plugin` is `ansible.builtin.memory`, which keeps the data in the memory of the running `ansible-inventory` or `ansible-playbook` process, and loses it when the process ends. `ansible.builtin.jsonfile` writes one JSON file per key in the `cache_connection` directory. Two sources, one with `cache: true` alone, one with `jsonfile` in `out/cache`; both read CMDB v1, then the CMDB moved to v2:

| Source | CMDB v1 | CMDB v2, next run |
|---|---|---|
| `memory` | app1 app2 db1 | app1 app3 db1 |
| `jsonfile` | app1 app2 db1 | app1 app2 db1 |

The memory cache followed the CMDB: every run is a new process, so every run asked the CMDB again. Across runs, it caches nothing. Only a persistent backend such as `jsonfile` keeps the inventory between runs, and only that one can go stale. Its file was `out/cache/ansible_inventory_s1_cmdb_k<hash>`: the prefix, `s1_` (a schema identifier ansible-core adds so that incompatible cache formats can live side by side, `_internal/_plugins/_cache.py`), then the cache key, covered below.

## cache_timeout

With `cache_timeout: 5`, a run filled the cache from v1, the CMDB moved to v2, and:

| Run | Hosts |
|---|---|
| at once | app1 app2 db1, from the cache |
| 6 seconds later | app1 app3 db1, from the CMDB |
| 6 seconds later again, CMDB down | no hosts, exit 0 |

`jsonfile` compares the age of the cache file, from its modification time, with the timeout. Past it, the entry counts as missing: the plugin calls the CMDB and rewrites the file. The last line is the trap: the cache file was still on disk, but expired, so the plugin didn't use it, the CMDB call failed, and `ansible-inventory` warned *cannot read the CMDB at …* and exited 0 with an empty inventory. An expired cache is no fallback for a source that is down; that takes item 15's `any_unparsed_is_failed` setting, which turns an unreadable source into a failure.

So `cache_timeout` is the longest a cached inventory can be stale: an hour by default. Within it, nothing tells you the data is old.

## Two sources, one cache directory

Two configuration files, `dc1.cmdb.yml` and `dc2.cmdb.yml`, read two different CMDB lists (one per datacenter) with the same plugin, the same `cache_connection` and the same `cache_prefix: cmdb_`. Does one read the other's cache? No: the directory held two files, `cmdb_s1_cmdb_k<hash>` twice with different hashes, and with the CMDB stopped each source still returned its own hosts. The key comes from the `Cacheable` base class in `plugins/inventory/__init__.py`: the plugin's name, then `k` and the first six hex digits of a SHA-256 hash of the plugin's name and the configuration file's path. The path Ansible hands the plugin is absolute:

| Source, CMDB down | Hosts |
|---|---|
| `sources/dc1.cmdb.yml` | app1 app2 db1, from the cache |
| `./sources/dc1.cmdb.yml` | app1 app2 db1 |
| the same file by its absolute path | app1 app2 db1 |
| a copy of the file at another path | no hosts |

Sharing a directory and a prefix between sources is safe, then. The other side: moving or renaming a configuration file, or checking a project out in another directory, starts from an empty cache, and the old file stays behind, never read again.

## A play on a decommissioned host

This is the dangerous case. The `jsonfile` cache was filled from v1, the CMDB moved to v2, and a playbook ran on `hosts: app`, its one task standing for a deployment:

| Command | Ran on |
|---|---|
| `ansible-playbook deploy.yml` | app1, app2 |
| `ansible-playbook deploy.yml --flush-cache` | app1, app3 |

From the cache, the play deployed to app2, a host the CMDB no longer has, and missed app3. Here the task only prints; a real one would try to connect to app2, fail on an unreachable host if it's gone, or, worse, reach whatever machine now answers at that name or address. `--flush-cache` makes the plugin skip the cache and refresh it: `ansible-playbook` creates its inventory with `cache=False` when the option is given (`cli/__init__.py`), which the plugin's `parse()` receives.

## The fact cache is a separate setting, with shared fallbacks

Ansible has a second cache: the *fact cache*, which keeps the facts gathered from hosts between runs, set with `fact_caching` (and `fact_caching_connection`, `fact_caching_timeout`, `fact_caching_prefix`) in the `[defaults]` section of `ansible.cfg`, or the `ANSIBLE_CACHE_PLUGIN*` environment variables. [Item 12](inventory-limit-in-practice.md) used it so that a run with `--limit` could read the facts of hosts outside the limit, and part 11 of the data-shaping series, [Data from other hosts](data-from-other-hosts-extract-hostvars-pg-hba.md), for facts of hosts not in the play. The inventory cache has its own settings: the plugin options above, or `cache`, `cache_plugin`, `cache_connection`, `cache_timeout` and `cache_prefix` in the `[inventory]` section.

They are separate settings, but not independent ones. In the `inventory_cache` fragment, each inventory cache option also reads the fact cache's setting: `cache_plugin` from `fact_caching` and `ANSIBLE_CACHE_PLUGIN`, `cache_connection` from `fact_caching_connection`, and so on. The cache plugins page of the docs says it too: inventory caching without an inventory-specific cache plugin uses the fact cache plugin. The example set only the fact cache, `ANSIBLE_CACHE_PLUGIN=ansible.builtin.jsonfile` and `ANSIBLE_CACHE_PLUGIN_CONNECTION=out/facts`, and ran the `memory.cmdb.yml` source, the one that followed the CMDB in the first section:

- `out/facts` then held the facts, `s1_app1`, `s1_app2`, `s1_db1`, and the inventory cache, `ansible_inventory_s1_cmdb_k<hash>`;
- after the CMDB moved to v2, that source returned app1 app2 db1: stale.

A plugin configuration that says `cache: true` and nothing else is in memory on one machine and persistent on another, depending on whether a fact cache is set there. Naming `cache_plugin` in the configuration file removes the doubt.

`--flush-cache` reaches both caches, but not evenly. Its help says *clear the fact cache for every host in inventory*, and that is what it does: it refreshes the inventory first, then clears the facts of the hosts in the refreshed inventory. After `ansible-playbook --flush-cache` on v2, app1's and db1's facts were cleared, but `s1_app2` was still there with its old values: app2 is no longer in the inventory, so nothing clears it. The fact cache of a decommissioned host stays until `fact_caching_timeout` expires (24 hours by default) or someone deletes the file.

## A policy

- **Interactive runs on a slow or rate-limited source**: cache with `jsonfile`, and a `cache_timeout` as short as the source allows, minutes rather than the default hour. The timeout is how stale the data may be.
- **Name the backend.** Set `cache_plugin` and `cache_connection` in the configuration file, so that a fact cache doesn't decide for you.
- **CI and scheduled jobs**: run with `--flush-cache`, or `cache: false`. A pipeline that deploys must target what the source of truth says now, not what it said an hour ago, and it shouldn't depend on a cache left on the runner by an earlier job.
- **After decommissioning a host**, flush the inventory cache, and delete that host's fact cache file yourself.
- **Fail on an unreadable source** with `any_unparsed_is_failed`: an expired cache won't save the run.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/19-inventory-cache-stale-data), holds the plugin, the CMDB lists, one configuration file per case and the two playbooks. `run.sh` starts the mock CMDB on port 18190, swaps its data, sleeps past a 5-second `cache_timeout`, and prints which hosts each run got, never the times. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `plugins/cache.rst` (inventory and fact cache plugins, the fallback to the fact cache plugin) and `plugins/inventory.rst` (inventory caching).
- ansible-core 2.21.4 source: `plugins/doc_fragments/inventory_cache.py` (options, defaults, the `fact_caching` fallbacks), `plugins/inventory/__init__.py` (`Cacheable`, the cache key), `plugins/cache/__init__.py` (`BaseFileCacheModule.has_expired`, file names), `plugins/cache/memory.py`, `_internal/_plugins/_cache.py` (the `s1_` schema prefix), `cli/__init__.py` and `cli/arguments/option_helpers.py` (`--flush-cache`), `config/base.yml` (`fact_caching_timeout`).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
