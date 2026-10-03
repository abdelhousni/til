# A single source of truth: inventory plugins, enable_plugins and auto

Fifteenth entry in the Ansible inventory from scratch series. The earlier items wrote every host by hand, in a hosts file with [`group_vars/` and `host_vars/`](inventory-directory-group-vars-per-role.md). In most companies, though, the list of servers already lives somewhere else. The Red Hat Community of Practice's *automation good practices* open their inventory chapter with a rule about it, *Identify your Single Source(s) of Truth and use it/them in your inventory*:

> A Single Source of Truth (SSOT) is the place where the "ultimate" truth about a certain data is generated, stored and maintained. […] As you create your inventory, you identify these SSOTs and combine them into one inventory using dynamic inventory sources […]. Only the aspects which are not already provided by other sources are kept statically in your inventory.

Their examples of such sources are cloud or virtualization managers, management systems such as Satellite, and a *Configuration Management Database* (CMDB): the database where an IT department records its servers, with their owner, location and purpose. This entry reads a mock CMDB three ways, a copy by hand, an inventory script and an inventory plugin, and shows how Ansible chooses the plugin that reads a source. Everything below ran with ansible-core 2.21.4.

## The case

The mock CMDB is Python's built-in web server on the local machine, serving one JSON file: a list of servers, each with a name, a role and an owner.

```json
{"servers": [
  {"name": "app1", "role": "app", "owner": "web-team"},
  {"name": "app2", "role": "app", "owner": "web-team"},
  {"name": "db1", "role": "db", "owner": "dba-team"}
]}
```

Each way puts each server in a group named after its role, and sets its owner as the host variable `cmdb_owner`:

- **A static inventory** copied from the CMDB by hand: a `hosts.yml` and one `host_vars/<host>/cmdb.yml` per host, as the series has done so far.
- **An inventory script**: an executable file that Ansible runs with `--list`, and that prints the inventory as JSON on standard output. It must also answer `--host <name>` with one host's variables, but when the `--list` output has a `_meta.hostvars` key holding every host's variables, Ansible doesn't call it with `--host`. The CoP's chapter calls scripts *"deprecated but still simple to use"*.
- **An inventory plugin**: Python code that ansible-core loads and runs, here 70 lines in the example's `plugins/inventory/cmdb.py`. The inventory source passed with `-i` is then a small YAML configuration file whose `plugin:` key names the plugin:

```yaml
# plugin/hosts.cmdb.yml
plugin: cmdb
url: http://127.0.0.1:18150/hosts.json
cache: true
cache_plugin: ansible.builtin.jsonfile
cache_connection: out/cache
```

Ansible finds plugins of its own in the directories of the `inventory_plugins` setting, here `inventory_plugins = plugins/inventory` in the example's `ansible.cfg`. The plugin's `verify_file()` method accepts only files whose name ends in `cmdb.yml` or `cmdb.yaml`, as the developer guide recommends, and its `parse()` reads the configuration, calls the URL, and adds groups, hosts and variables.

All three gave the same inventory: app1 and app2 in `app`, db1 in `db`, with their owners. One difference showed up in `ansible-inventory --list` (see [item 6](inventory-checking-with-ansible-inventory.md)): the script's `cmdb_owner` came out as `"dba-team"`, the plugin's as `{"__ansible_unsafe": "dba-team"}`. A plugin's values are *untrusted* unless it sets `trusted_by_default = True`, so a string such as `{{ ... }}` coming from the CMDB is never rendered as a template; the wrapper is how `--list` records it.

## When the CMDB changes

Then the CMDB changed: app2 retired, app3 added, db1 handed over to data-team.

| Source | Inventory after the change |
|---|---|
| static | app1, app2, db1 owned by dba-team: the old data |
| script | app1, app3, db1 owned by data-team |
| plugin, cache on | app1, app2, db1 owned by dba-team: the cache |
| plugin, `--flush-cache` | app1, app3, db1 owned by data-team |

The static copy drifts the moment the CMDB moves, and nothing warns: a play on `app` would still configure app2 and miss app3. That's the rationale the CoP gives, avoiding *"potentially conflicting information with the rest of your IT"*. The plugin drifted too, for another reason, covered below: the inventory cache.

## How Ansible picks the plugin: enable_plugins and auto

Every source passed with `-i`, or each file of an inventory directory, is offered to the *enabled* inventory plugins in turn, and the first one that accepts it and parses it wins. The list is the `enable_plugins` setting in the `[inventory]` section of `ansible.cfg`, or the `ANSIBLE_INVENTORY_ENABLED` environment variable. Its default, from `ansible-config dump`:

```
INVENTORY_ENABLED(default) = ['host_list', 'script', 'auto', 'yaml', 'ini', 'toml']
```

`host_list` reads a comma-separated list given on the command line, `script` runs executable files, `yaml`, `ini` and `toml` read static files ([item 3](inventory-ini-or-yaml-hosts-file.md)). `auto` is the one that makes plugins work without enabling each of them: it accepts any `.yml` or `.yaml` file, reads its `plugin:` key, and hands the file to the plugin of that name. With `-vvv`, the configuration file's journey:

```
host_list declined parsing plugin/hosts.cmdb.yml as it did not pass its verify_file() method
script declined parsing plugin/hosts.cmdb.yml as it did not pass its verify_file() method
Using inventory plugin 'cmdb' to process inventory source 'plugin/hosts.cmdb.yml'
Parsed plugin/hosts.cmdb.yml inventory source with auto plugin
```

Setting `enable_plugins` replaces the whole list, it doesn't add to it:

- **Without `auto`** (`host_list, script, yaml, ini, toml`): nothing read the configuration file. The `yaml` plugin said *Plugin configuration YAML file, not YAML inventory*, the `ini` plugin failed on `---`, then *Unable to parse plugin/hosts.cmdb.yml as an inventory source* and *No inventory was parsed, only implicit localhost is available*. `ansible-inventory` still exited 0, with no hosts.
- **`cmdb, yaml`**: the plugin, named directly, read its file without `auto`.
- **A typo, `cmbd, auto, yaml`**: only a warning, *Failed to load inventory plugin, skipping cmbd*; `auto` then read the file anyway.

The order matters when two plugins accept the same source: the first one that parses it wins, and the failures of the others are shown only when none succeeds. A plugin with no YAML configuration file, or a configuration file named without `.yml`/`.yaml`, can't go through `auto` and has to be listed in `enable_plugins`, by its fully qualified name when it comes from a collection.

## Where Ansible finds a plugin

The plugin is a file named after it in a plugin directory: the `inventory_plugins` setting, whose default is `~/.ansible/plugins/inventory` and `/usr/share/ansible/plugins/inventory`, or a collection. Ansible also reads an `inventory_plugins/` directory beside the playbook, which looks simpler than a setting. The example has the plugin only there, with no `inventory_plugins` setting:

- `ansible-playbook` found it, and the play printed each host's owner.
- `ansible-inventory` failed: *inventory config 'hosts.cmdb.yml' specifies unknown plugin 'cmdb'*, then an empty inventory, exit 0.
- `ansible-inventory --playbook-dir .` found it again.

So the tool you check the inventory with doesn't see the plugin the playbook uses, unless given `--playbook-dir`. The `inventory_plugins` setting, or a collection, works for both.

## The inventory cache

An inventory plugin can keep what it read in a cache, so that it doesn't call the source on every run, and keeps working when the source is down. The plugin declares the `inventory_cache` documentation fragment and the `Cacheable` base class; its configuration sets `cache: true` and a *cache plugin*, the backend that stores the data, here `ansible.builtin.jsonfile`, one JSON file in `out/cache`. `cache_timeout`, 3600 seconds by default, sets how long the cache stays valid. The example's `parse()` follows the developer guide's pattern: read the cache unless it's being refreshed, and write it back when the source was called.

This explains the stale result above: within the hour, the plugin answered from its cache, not from the CMDB. `--flush-cache` refreshed it, and the next run without it returned the new hosts.

With the CMDB stopped:

| Source | Result |
|---|---|
| plugin, cache on | app1, app3, db1, from the cache |
| script | no hosts: *Inventory script returned non-zero exit code 1*, exit 0 |
| plugin, `--flush-cache` | no hosts: *cannot read the CMDB …*, exit 0 |
| script, `ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED=true` | *Completely failed to parse inventory source*, exit 1 |

An unreachable source gives warnings and an empty inventory, and a playbook then runs on no hosts. `any_unparsed_is_failed` in `[inventory]`, or its environment variable, turns that into a failure, which is what a scheduled job wants.

## A real plugin

The mock plugin is an illustration, not a product. Real sources come with real plugins in collections, such as `theforeman.foreman.foreman` for Foreman and Satellite, the subject of [an earlier entry](foreman-dynamic-inventory-plugin.md) that the next item revisits. They follow the same rules: a configuration file named as the plugin documents, `auto` or `enable_plugins` to load it, and the same cache options.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/15-single-source-of-truth), holds the CMDB data, the three sources and the plugin. `run.sh` starts the mock CMDB on port 18150, reads it three ways, changes its data, runs the `enable_plugins` cases, the `inventory_plugins/` pitfall, then stops the CMDB and reads the cache. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Red Hat CoP, [automation good practices](https://redhat-cop.github.io/automation-good-practices/), from [redhat-cop/automation-good-practices](https://github.com/redhat-cop/automation-good-practices): `inventories/README.adoc`, *Identify your Single Source(s) of Truth and use it/them in your inventory* and *Define your inventory as structured directory instead of single file*.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `plugins/inventory.rst` (enabling plugins, caching) and `dev_guide/developing_inventory.rst` (`verify_file`, `parse`, the inventory cache pattern, inventory scripts and `_meta`).
- ansible-core 2.21.4 source: `config/base.yml` (`INVENTORY_ENABLED`, `DEFAULT_INVENTORY_PLUGIN_PATH`), `inventory/manager.py` (how sources are offered to plugins), `plugins/inventory/auto.py`, `plugins/inventory/__init__.py` (`trusted_by_default`), `plugins/doc_fragments/inventory_cache.py`.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
