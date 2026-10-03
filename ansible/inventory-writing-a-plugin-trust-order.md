# Writing an inventory plugin, after the trust order

Twenty-third entry in the Ansible inventory from scratch series. [Item 15](inventory-plugins-single-source-of-truth.md) read a mock CMDB (a *Configuration Management Database*, where an IT department records its servers) with a static copy, an inventory script and a 70-line inventory plugin, and called that plugin *an illustration, not a product*. This entry asks the question that comes before writing one: does something already exist? Then it writes the plugin properly, in a collection, with documentation, the cache, the `constructed` options, clear errors and unit tests. Everything below ran with ansible-core 2.21.4.

## The trust order

The `write-content` skill of the Lola Ansible modules, which the series' examples are written with, has a rule for any new piece of automation, after the Red Hat Community of Practice's *automation good practices*:

> Prefer existing Ansible content before creating custom automation. Selection order: `ansible.builtin` -> vendor-supported content -> content from verified authors -> general Galaxy content -> custom collections/modules/plugins/roles only as a last resort.

And: *when using anything below `ansible.builtin` or creating custom content, explain why higher-trust options were not suitable.* The tiers:

- **`ansible.builtin`**: what ships with ansible-core itself, maintained and tested by the Ansible project.
- **Vendor-supported content**: collections a vendor maintains for its own product, such as `theforeman.foreman` for Foreman ([item 16](foreman-dynamic-inventory-plugin.md)). A *collection* is Ansible's unit of distribution: a directory `ansible_collections/<namespace>/<name>/` with a `galaxy.yml` and plugins, modules or roles, installed with `ansible-galaxy collection install`.
- **Verified authors**: Red Hat's certified and validated collections, on Automation Hub, Red Hat's subscription-only collection server.
- **General Galaxy content**: anything published on [Galaxy](https://galaxy.ansible.com/), the public collection server, by anyone.
- **Custom content**: your own code, which you then maintain.

The CMDB is the same as in item 15, with two more fields per server, `env` and `address`, and now behind a bearer token: an `Authorization: Bearer <token>` HTTP header that the server checks, as most internal APIs require.

## Searching, tier by tier

**What's installed.** `ansible-doc -t inventory -l` lists every inventory plugin Ansible can load. With only ansible-core:

```
ansible.builtin.advanced_host_list Parses a 'host list' with ranges
ansible.builtin.auto               Loads and executes an inventory plugin specified in a YAML config
ansible.builtin.constructed        Uses Jinja2 to construct vars and groups based on existing inventory
ansible.builtin.generator          Uses Jinja2 to construct hosts and groups from patterns
ansible.builtin.host_list          Parses a 'host list' string
ansible.builtin.ini                Uses an Ansible INI file as inventory source
ansible.builtin.script             Executes an inventory script that returns JSON
ansible.builtin.toml               Uses a specific TOML file as an inventory source
ansible.builtin.yaml               Uses a specific YAML file as an inventory source
```

None calls an HTTP API. The series' other collections, `community.docker` and `theforeman.foreman`, read Docker and Foreman, not a home-made CMDB.

**Vendor-supported.** A home-made CMDB has no vendor. A product would: NetBox and Nautobot, for example, publish inventory plugins in their own collections (`netbox.netbox.nb_inventory`, `networktocode.nautobot.inventory`), and that's where to stop looking.

**Galaxy.** Galaxy's search API (`/api/v3/plugin/ansible/search/collection-versions/`, queried on 2026-10-03 for the latest version of each collection) returned 207 collections for the keyword *inventory*. For the keyword *json*, eight held inventory plugins, and one looked generic: `nleiva.inventory.json`, reading an inventory from a URL. Its documentation describes it as *My Ansible inventory plugin demo*, its `validate_certs` option defaults to `false`, and the version published in May 2023 carries no signature. `community.general` 13.4.0, the largest community collection, has thirteen inventory plugins (cobbler, gitlab_runners, icinga2, incus, iocage, linode, lxd, nmap, online, opennebula, scaleway, virtualbox, xen_orchestra), none of them a generic HTTP or JSON reader.

**Verified authors.** Automation Hub needs a Red Hat subscription, which this lab doesn't have; this entry didn't search it.

So no installed or published plugin reads this CMDB as is. Before writing one, the top tier still has two tools that do it without a plugin.

## No plugin at all: a script and constructed

`ansible.builtin.script` runs an inventory script ([item 15](inventory-plugins-single-source-of-truth.md) explains the `--list` protocol), and `ansible.builtin.constructed` builds groups and variables from what earlier sources added ([item 11](targeting-hosts-static-and-dynamic-inventory.md) introduced its `keyed_groups`). In one inventory directory, whose files load in name order:

- `01-cmdb.py`, a 36-line script: it reads `CMDB_URL` and `CMDB_TOKEN` from the environment, puts each server in a group named after its role, and sets its other fields as `cmdb_*` variables;
- `02-constructed.yml`:

```yaml
plugin: ansible.builtin.constructed
strict: true
compose:
  ansible_host: cmdb_address
keyed_groups:
  - key: cmdb_env
    prefix: env
```

`compose` sets a variable from a Jinja2 expression, here `ansible_host` from the CMDB's address. The result:

```
script + constructed: exit 0, app[app1,app2] db[db1] env_prod[app1,db1] env_test[app2]
```

with db1's `ansible_host: 10.0.1.21`. For this CMDB, ansible-core alone does the job, and by the trust order this is the answer as long as nothing more is needed. What it lacks, by the developer guide's own list: *"If you choose to write a script, however, you will need to implement some features yourself such as caching, configuration management, dynamic variable and group composition."* Item 15 showed the script returning nothing, without a cache, when the CMDB was down. A plugin is worth its maintenance when you need that cache, documented options, or to hand the source to other teams as an installable collection.

## The plugin, done properly

`example.cmdb.cmdb` lives in a local collection inside the example, `collections/ansible_collections/example/cmdb/`, with a `galaxy.yml`, a `meta/runtime.yml` (the ansible-core versions it supports) and `plugins/inventory/cmdb.py`. The example's `ansible.cfg` sets `collections_path = collections`, so `ansible-inventory` and playbooks both find it, unlike the `inventory_plugins/` directory beside a playbook in item 15. What the 175 lines add to item 15's 70:

| | Item 15 | This plugin |
|---|---|---|
| Where | `plugins/inventory/`, via `inventory_plugins` | a collection, name `example.cmdb.cmdb` |
| `DOCUMENTATION` | `plugin`, `url` | plus `token`, `validate_certs`, `timeout`, `EXAMPLES`, author, version |
| Options from the environment | none | `CMDB_URL`, `CMDB_TOKEN`, `CMDB_VALIDATE_CERTS` |
| Base classes | `Cacheable` | `Constructable` and `Cacheable` |
| HTTP | `urllib.request.urlopen` | `ansible.module_utils.urls.open_url`, with the token and certificate checking |
| Errors | network errors | network and HTTP errors, non-JSON answer, missing fields, empty token |
| Tests | none | 14 pytest unit tests, `ansible-test sanity` |

**Documentation.** `DOCUMENTATION` is a YAML string that Ansible reads for `ansible-doc`, and also for the options themselves: an option exists because it's documented there. `extends_documentation_fragment` pulls in shared option sets, *documentation fragments*: `ansible.builtin.constructed` adds `strict`, `compose`, `groups`, `keyed_groups` and two more, `ansible.builtin.inventory_cache` adds the `cache_*` options. An `env:` entry under an option lets an environment variable set it. `ansible-doc` shows them merged:

```
token             required, CMDB_TOKEN
url               required, CMDB_URL
validate_certs    default True, CMDB_VALIDATE_CERTS
```

A configuration file with nothing but `plugin: example.cmdb.cmdb` then works, the URL and token coming from the environment: the token stays out of any file.

**`verify_file()`** accepts only file names ending in `cmdb.yml` or `cmdb.yaml`. The same content in `cmdb-hosts.yml` was declined: *inventory source 'pitfalls/cmdb-hosts.yml' could not be verified by inventory plugin 'example.cmdb.cmdb'*, and an empty inventory.

**Constructable.** For each host, `parse()` calls the three methods the developer guide names, `_set_composite_vars()` first so that groups can use the composed variables, then `_add_host_to_composed_groups()` and `_add_host_to_keyed_groups()`, each with the `strict` option. The configuration from the script's case moves into the plugin's own file, `inventory/hosts.cmdb.yml`, and gives the same groups and `ansible_host`.

**Errors.** The developer guide: *"if you get an inventory source error or any other issue, you should `raise AnsibleParserError` to let Ansible know that the source was invalid or the process failed."* Each failure gave a message saying what went wrong:

| Case | Message |
|---|---|
| `CMDB_TOKEN` unset | *Required config 'token' for '…cmdb' inventory plugin not provided.* (from Ansible) |
| `CMDB_TOKEN` empty | *no token for the CMDB: set CMDB_TOKEN, or token in the configuration file* |
| wrong token | *cannot read the CMDB at http://127.0.0.1:18230/api/servers: HTTP Error 401: Unauthorized* |
| an HTML page | *the CMDB at …/html did not answer with JSON: Expecting value: line 1 column 1 (char 0)* |
| a server without a name | *server #0 from …/api/servers has no name* |
| CMDB down | *cannot read the CMDB at …: <urlopen error [Errno 111] Connection refused>* |

The empty token is a pitfall: `required: true` only means *set*, and an empty string passed, sending `Authorization: Bearer ` and getting a 401. The plugin checks it itself, before any request. As in item 15, each failure is only a warning and `ansible-inventory` exits 0 with no hosts, unless `ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED=true`, which gave exit 1.

`strict` matters too: `keyed_groups` on `cmdb_rack`, a field the CMDB doesn't have, silently made no group without it; with `strict: true`, *Could not generate group for host app1 from cmdb_rack entry: 'cmdb_rack' is undefined*.

**The cache** works as in item 15: after the CMDB changed, the plugin answered from its cache, without a request, until `--flush-cache`; with the CMDB stopped, it still answered from the cache.

## Testing the plugin

The CoP's plugin chapter: *"The use of unittest is discouraged, use pytest instead."* The collection's `tests/unit/plugins/inventory/test_cmdb.py` loads the plugin with `inventory_loader.get("example.cmdb.cmdb")`, as Ansible does, and replaces `open_url` with `unittest.mock.patch`, so no server runs. Fourteen tests cover `verify_file()`, hosts, groups and variables, the token header, the constructed options, each error above, and the cache: one request for two runs, a second one with `--flush-cache`. Two details from writing them:

- Plain pytest doesn't know where `ansible_collections` is: a `conftest.py` calls `init_plugin_loader()` with the collection's root, unless a collection loader is already set up, as `ansible-test units` does.
- The cache is written by `update_cache_if_changed()`, which ansible-core's inventory manager calls after `parse()`; a test that calls `parse()` directly has to call it too, or the second run finds no cache.

`ansible-test`, ansible-core's test tool for collections, ran both suites on a copy of the collection: `ansible-test units --python 3.12` passed the same 14 tests, and `ansible-test sanity --python 3.12 --requirements` passed its 24 tests, `validate-modules` (which checks `DOCUMENTATION` against the code), `pylint`, `pep8` and `yamllint` among them. It isn't offline: `--requirements` installs each test's tools from PyPI. The example's `run.sh` runs the pytest suite; the sanity run isn't in it.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/23-writing-an-inventory-plugin), holds the fake CMDB, the script with `constructed`, the collection and its tests. `run.sh` lists ansible-core's inventory plugins, runs the no-code inventory, prints the plugin's options, runs it with each error case and the cache, and runs the unit tests. Its CI runs it on every push and compares the output with the expected one.

## Sources

- The `write-content` skill of the Lola `ansible-content-development` module: the selection order and *explain why higher-trust options were not suitable*.
- Red Hat CoP, [automation good practices](https://redhat-cop.github.io/automation-good-practices/), from [redhat-cop/automation-good-practices](https://github.com/redhat-cop/automation-good-practices): `plugins/README.adoc` (documentation, docstrings, type hints, pytest, clear error messages) and `inventories/README.adoc`.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `dev_guide/developing_inventory.rst` (scripts against plugins, `AnsibleParserError`, `Constructable`, the cache pattern).
- ansible-core 2.21.4 source: `plugins/inventory/__init__.py` (`Constructable`, `Cacheable`), `inventory/manager.py` (`update_cache_if_changed()`), `plugins/doc_fragments/constructed.py` and `inventory_cache.py`, `module_utils/urls.py` (`open_url`).
- Galaxy's search API on 2026-10-03, for the keywords *inventory* and *json*, and the documentation of `nleiva.inventory` 1.0.5 and `community.general` 13.4.0 from the same API.
- Every other result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
