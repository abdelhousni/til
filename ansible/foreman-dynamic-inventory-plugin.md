# The Foreman/Satellite dynamic inventory plugin

Sixteenth entry in the Ansible inventory from scratch series. [Inventory plugins as a single source of truth](inventory-plugins-single-source-of-truth.md) explained inventory plugins, the `auto` plugin and the inventory cache in general. This entry applies them to one source: Foreman. [Foreman](https://theforeman.org/) is an open-source server that provisions and tracks machines; Red Hat Satellite is built on it. `theforeman.foreman.foreman`, the inventory plugin in the `theforeman.foreman` collection, asks Foreman's API for its hosts and turns them into Ansible hosts, groups and variables, so the inventory is whatever Foreman has registered, not a list kept by hand. Everything below ran with ansible-core 2.21.4 and theforeman.foreman 5.13.0, against a fake Foreman (see [The example](#the-example)).

A few Foreman terms first:

- A **host group** is a template for hosts: hosts in it share settings. Host groups nest, and Foreman names a nested one by its path, its *title*, such as `Base/Web`.
- **Locations** and **organizations** split Foreman's hosts by place and by owner.
- A **host parameter** is a name and a value attached to a host, a host group, a location or other levels; a host's *all parameters* merge them all.
- A **host collection** is a named set of hosts, added by Katello, the content-management plugin that Satellite includes.

## Install and point it at Foreman

```sh
ansible-galaxy collection install theforeman.foreman
```

The plugin imports the Python `requests` library, and refuses to load without it (`requires: requests >= 1.1` in its documentation). It runs on the controller, so `requests` must be in the Python that runs Ansible, such as the virtualenv ansible-core is installed in. ansible-core doesn't install it.

The source is a YAML file whose name ends in `foreman.yml` or `foreman.yaml`:

```yaml
# inventory/hosts-api.foreman.yml
plugin: theforeman.foreman.foreman
url: https://foreman.example.com
use_reports_api: false
```

Two corrections to what this entry used to say:

- **No `enable_plugins` is needed.** ansible-core's default `enable_plugins` includes `auto`, which reads the `plugin:` key and loads that plugin. The example's `ansible.cfg` has no `[inventory]` section, and every source in it works.
- **The name check comes from the plugin, not the directory.** A file named `foreman-inventory.yml` with the same content gives no hosts: `auto` hands it to the plugin, whose `verify_file` refuses names not ending in `foreman.yml` or `foreman.yaml`, and Ansible only warns, *could not be verified by inventory plugin 'theforeman.foreman.foreman'*, then *No inventory was parsed*.

The user and password are required, but don't have to be in the file: the plugin reads `FOREMAN_USER` and `FOREMAN_PASSWORD` from the environment, and `FOREMAN_URL` for the URL. The example sets the first two in `run.sh` and keeps them out of the source. [Item 10](inventory-secrets-vault-yml-aliases.md) covers vault for values that must be in a file.

## Two APIs underneath

The plugin talks to Foreman in one of two ways:

- **The Reports API**, the default (`use_reports_api: true`). The plugin asks for `/api/v2/status`, and if Foreman is 1.24 or newer, it POSTs to `/ansible/api/v2/ansible_inventories/schedule` to schedule a report of all hosts, then polls the URL Foreman answers with until the report is ready (every `poll_interval` seconds, 10 by default). One report holds every host. It needs the **`foreman_ansible` plugin on the Foreman server**, which provides the `/ansible/` URLs.
- **The Hosts API** (`use_reports_api: false`), which every Foreman has: `/api/v2/hosts` for the list, then more requests per host for what the `want_*` options ask for.

Against a Foreman without `foreman_ansible`, the default doesn't fall back to the Hosts API. The schedule request gets a 404, the plugin raises *Error scheduling inventory report on foreman. Please check foreman logs!*, and Ansible turns it into warnings: `ansible-inventory --graph` exits 0 and shows only `@all` and `@ungrouped`. A playbook would run on no hosts. So when the graph comes back empty, set `use_reports_api: false` and try again before reading Foreman's logs. (The `max_timeout` option's documentation speaks of *falling back to old host API* when the report takes too long, but in 5.13.0's code a timeout raises *Timeout receiving inventory report from foreman* instead.)

What the plugin requested, logged by the fake Foreman, for three hosts:

| Source | Requests |
|---|---|
| Reports API, default options | 3: status, schedule, the report |
| Hosts API, `want_params` | 4: the list, then `/api/v2/hosts/<id>` per host |
| Hosts API, `want_params`, `want_facts`, `want_hostcollections` | 13: the list, then per host `/api/v2/hosts/<id>` twice and `/api/v2/hosts/<id>/facts` twice |

`/api/v2/hosts/<id>` comes twice because parameters and host collections each fetch it; the facts come in pages until an empty one. On a few thousand hosts, that's thousands of requests per run, which is the reason the Reports API exists, and the reason for the cache below. `--limit` doesn't reduce them: `ansible-playbook --limit db1` made the same four requests as a full run, since the inventory is built before the limit applies ([item 12](inventory-limit-in-practice.md) covers `--limit`).

## Hosts, groups and variables

The example's Foreman has three hosts: web1 and web2 in host group `Base/Web`, db1 in `Base/DB`, in two locations (Brussels, Paris) and one organization (Acme). With the Hosts API:

```yaml
plugin: theforeman.foreman.foreman
url: http://127.0.0.1:18160
use_reports_api: false
want_params: true
want_facts: true
want_hostcollections: true
hostnames:
  - name.split('.')[0]
compose:
  ansible_host: foreman_ip
keyed_groups:
  - key: foreman_location_name | lower
    prefix: location
  - key: tier
    prefix: tier
groups:
  postgresql: db_engine is defined and db_engine == 'postgresql'
```

```
@all:
  |--@ungrouped:
  |--@foreman_base:
  |  |--@foreman_base_web:
  |  |  |--web1
  |  |  |--web2
  |  |--@foreman_base_db:
  |  |  |--db1
  |--@foreman_hostcollection_webservers:
  |  |--web1
  |  |--web2
  |--@foreman_hostcollection_patchtuesday:
  |  |--web1
  |  |--db1
  |--@location_brussels:
  ...
  |--@postgresql:
  |  |--db1
```

- **Groups from host groups.** Each level of a host group's title gives a group, nested the same way: `foreman_base` holds `foreman_base_web`. The name is `group_prefix` (default `foreman_`) plus the title in lower case, spaces removed, and the `/` turned into `_` because it isn't valid in a group name.
- **No location or organization groups from the Hosts API.** Only the Reports API makes `foreman_location_brussels` or `foreman_organization_acme`. With the Hosts API, the example builds them with `keyed_groups` from the `foreman_location_name` variable.
- **`hostnames`** is a list of expressions for the host's name, the first non-empty one wins; `name.split('.')[0]` turns `web1.example.com` into `web1`. The default is the FQDN.
- **`compose`, `keyed_groups` and `groups`** work as in `ansible.builtin.constructed`, which [item 11](targeting-hosts-static-and-dynamic-inventory.md) introduced: `compose` sets a variable from an expression, `keyed_groups` makes a group per value, `groups` puts a host in a group when a condition holds. They see the variables the plugin just set, host parameters included.

web1's variables (`ansible-inventory --host web1`):

```json
{
    "ansible_host": "192.0.2.11",
    "app_port": 8080,
    "foreman_facts": {
        "os::family": "RedHat",
        "os::release::full": "9.6",
        "processorcount": "2"
    },
    "foreman_hostgroup_id": 2,
    "foreman_id": 1,
    "foreman_ip": "192.0.2.11",
    "foreman_location_name": "Brussels",
    "foreman_organization_name": "Acme",
    "ntp_server": "ntp.brussels.example.com",
    "tier": "frontend",
    ...
}
```

- **Foreman's fields** become variables prefixed with `vars_prefix` (default `foreman_`), except the name and host group fields, which became the host's name and groups.
- **Host parameters** (`want_params: true`) become variables under their own names, unprefixed: `ntp_server`, `app_port`, `tier`.
- **Facts** (`want_facts: true`) are the facts Foreman stored for the host, in one dict, `foreman_facts`, with Foreman's names (`os::family`), not Ansible's `ansible_facts`.

### legacy_hostvars: the old script's layout

Before the plugin, Foreman shipped an inventory script, `foreman.py`. `legacy_hostvars: true` gives its layout: Foreman's fields in one dict, `foreman`, the parameters in another, `foreman_params`, and the facts in `foreman_facts` when asked for. db1's top-level variables are then just `foreman` and `foreman_params`. That keeps the parameters from colliding with other variables, and a playbook reads them as a dict. To loop over one, turn it into a list of key/value pairs with `dict2items`, which [part 2 of the data-shaping series](lists-and-dicts-dict2items-items2dict-zip.md) explains:

```yaml
- name: Show the parameters, a dict with legacy_hostvars, as a list
  ansible.builtin.debug:
    msg: "{{ item.key }}={{ item.value }}"
  loop: "{{ foreman_params | dict2items }}"
```

```
ntp_server=ntp.brussels.example.com
db_engine=postgresql
tier=backend
```

The same source sets `group_prefix: fm_`, and the groups become `fm_base`, `fm_base_web` and `fm_base_db`. The older option layout, `foreman:` and `report:` dicts holding `use_reports_api` and the Reports API options, still works, and its documentation marks it deprecated.

### The Reports API's groups

With the Reports API and `want_hostcollections`, the same three hosts give the host group groups again, plus `foreman_location_brussels`, `foreman_location_paris`, `foreman_organization_acme`, and, from Katello's content details, `foreman_lifecycle_environment_production` and `foreman_content_view_rhel9`. The host collection *Web servers* becomes `foreman_hostcollection_web_servers` there, against `foreman_hostcollection_webservers` with the Hosts API: the two code paths in the plugin don't clean names the same way. Switching APIs renames those groups, so a playbook targeting them breaks.

## The cache

The plugin supports the inventory cache: Foreman's answers are kept between runs, and a run within the timeout makes no request at all.

```yaml
cache: true
cache_plugin: ansible.builtin.jsonfile
cache_connection: out/cache
cache_timeout: 3600
```

The first `ansible-inventory --graph` made four requests and wrote one file in `out/cache/`, holding Foreman's answers keyed by URL (`/api/v2/hosts`, `/api/v2/hosts/1`, ...), not the finished inventory. The second made none and printed the same graph. `--flush-cache` ignored the cache and made the four requests again. The cost is freshness: a host added in Foreman appears only when the cache expires or is flushed.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/16-foreman-inventory), holds the sources and a fake Foreman: a small Python server that answers with JSON files and logs each request. The answers are shaped after the plugin's source (the fields it reads) and Foreman's API v2, not recorded from a live server, so field lists in a real Foreman are longer. `run.sh` starts the server, prints the graphs, web1's variables and the requests of each source, runs the cache twice and flushes it, then the two pitfalls. Its CI runs it on every push and compares the output with the expected one.

## Sources

- theforeman.foreman 5.13.0, `plugins/inventory/foreman.py`: its `DOCUMENTATION` (options, defaults, environment variables, `requests` requirement) and its code (the URLs requested, group and variable names, `verify_file`, the error on a failed schedule request).
- ansible-core 2.21.4, `lib/ansible/inventory/manager.py` (`update_cache_if_changed` after each source, `--flush-cache`), and the default `enable_plugins` in `lib/ansible/config/base.yml`.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `inventory_guide/intro_dynamic_inventory.rst` and `plugins/inventory.rst` (inventory plugins, `auto`, cache options).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine, against the example's fake Foreman.
