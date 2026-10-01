# Lists and dicts back and forth: dict2items, items2dict and zip on role, Foreman and Proxmox data

Second entry in the Shaping data in Ansible series. [Part 1](readable-sudoers-with-dict-kv.md) explains lists, dicts (key–value mappings) and filters (the functions after a `|`). Data often comes in one of those shapes when the next step needs the other:
- a role wants a list of `{name, value}` items, and you keep a dict;
- an API returns a list, and you want to look a value up by name.

Three ansible-core filters convert between them: `dict2items`, `items2dict`, and `zip` followed by `dict()`, a function of Jinja, the template language Ansible evaluates inside `{{ }}`. Everything below ran with ansible-core 2.21.4.

## dict2items: sysctl settings for the kernel_settings role

*sysctl* settings are Linux kernel parameters that can be changed while the system runs. PostgreSQL's documentation, in *Managing Kernel Resources*, describes two for a database server:
- **`vm.overcommit_memory=2`**, strict overcommit, which makes it less likely that the kernel's out-of-memory killer stops PostgreSQL;
- **`vm.nr_hugepages`**, the number of *huge pages* to reserve. Huge pages are large memory pages that reduce the overhead of PostgreSQL's shared memory. The docs' example needs 3170.

The `kernel_settings` role sets them. It's one of the Linux System Roles that part 1 introduces. It takes `kernel_settings_sysctl` as a list of dicts, each with a `name` and a `value`. A dict is shorter to write:

```yaml
postgresql_sysctl:
  vm.overcommit_memory: 2
  vm.nr_hugepages: 3170
```

`dict2items` turns a dict into a list with one item per key. By default each item has the keys `key` and `value`. Its `key_name` and `value_name` arguments rename them:

```yaml
kernel_settings_sysctl: "{{ postgresql_sysctl | dict2items(key_name='name', value_name='value') }}"
```

Version 1.6.0 of the role checks its input first, in `tasks/assert_role_vars.yml`. Running only those checks, with each shape:

| `kernel_settings_sysctl` | The role's checks |
|---|---|
| `postgresql_sysctl`, the dict as is | Failed: *"kernel_settings_sysctl must be a list of dictionaries or {"state": "empty"}, got dict"* |
| `postgresql_sysctl \| dict2items` | Failed: *"kernel_settings_sysctl[0] is invalid: {'key': 'vm.overcommit_memory', 'value': 2}"*, and the same for item 1 |
| `postgresql_sysctl \| dict2items(key_name='name', value_name='value')` | Passed |

The items keep the dict's order. On a list instead of a dict, `dict2items` fails: *"dict2items requires a dictionary"*.

The PostgreSQL system role, 1.9.0, takes its settings the other way round. `postgresql_server_conf` is a dict, and the role's template loops over `postgresql_server_conf.items()` itself. Two roles from the same project want two shapes, so check each role's README.

## There and back: dropping keys from a dict

The roles chain both filters to remove keys from a dict. The podman role, which [this entry](podman-quadlet-caddy-adminer-php-linux-system-roles.md) uses to deploy Quadlet containers, takes one dict per Quadlet unit. That dict mixes the role's own keys (`name`, `type`, `state`, `run_as_user`, …) with the sections of the unit file (`Container`, `Install`). Before it writes the file, the role (1.14.3, `tasks/handle_quadlet_spec.yml`) keeps only the sections:

```yaml
__podman_quadlet_spec: "{{ __podman_quadlet_spec_item |
  dict2items | rejectattr('key', 'match', __del_params) |
  list | items2dict }}"
```

1. `dict2items` turns the dict into a list of `{key, value}` items.
2. `rejectattr('key', 'match', __del_params)` drops the items whose `key` matches a regular expression, a text pattern. `__del_params` is the role's own keys, `^(file_src|file_content|…|name|type|state|…)$`.
3. `items2dict`, with its default `key` and `value`, turns what's left back into a dict.

On the adminer unit from that entry, only `Install` and `Container` were left.

The sudo role does the same to every sudoers file it reads from the host, removing `include_files`, before comparing them with `sudo_sudoers_files`. It uses `map`, which applies a filter to each item of a list: `map('dict2items') | map('rejectattr', 'key', 'match', '^include_files$') | map('list') | map('items2dict')`.

## items2dict: Foreman host parameters

*Foreman* manages hosts through their life: provisioning, configuration, and *parameters*. Parameters are key–value pairs that a host has itself or inherits, from global settings, its organization, location, domain, subnet, operating system or *host group*, a set of settings that several hosts share. Foreman's API returns them as lists. `parameters` holds the host's own, and `all_parameters` the ones it ends up with after inheritance. Here is `GET /api/hosts/12` as recorded in the tests of theforeman.foreman, Foreman's Ansible collection, with some fields left out:

```json
"parameters": [],
"all_parameters": [
  {"id": 2, "name": "host_registration_remote_execution", "parameter_type": "boolean", "value": true, "priority": 0},
  {"id": 1, "name": "host_registration_insights", "parameter_type": "boolean", "value": false, "priority": 0}
]
```

The collection's `host_info` module returns the same host view. To look a parameter up by name:

```yaml
foreman_params: "{{ foreman_host.all_parameters | items2dict(key_name='name', value_name='value') }}"
```

That gave `{'host_registration_remote_execution': True, 'host_registration_insights': False}`, so `foreman_params['host_registration_insights']` is `False`. The other fields (`id`, `priority`, …) are dropped. An item without one of the two keys fails the task: *"items2dict requires each dictionary in the list to contain the keys 'name' and 'value'"*.

A name can't come out twice. Foreman 5.0.0 builds `all_parameters` with the host's own parameters first and keeps the first of each name (`uniq { |param| param.name }` in `app/models/concerns/host_params.rb`).

You only need this when you call the API or `host_info` yourself. The collection's inventory plugin, which builds Ansible's list of hosts from Foreman, with `want_params: true`, does the same conversion in Python: each parameter becomes a host variable, or a key of `foreman_params` with `legacy_hostvars: true`.

## items2dict on Proxmox VMs, and duplicate names

*Proxmox VE* runs virtual machines. Each VM has a numeric *VMID*, unique in the cluster, and a name, which doesn't have to be unique. `community.proxmox.proxmox_vm_info` returns `proxmox_vms`, a list with one dict per VM. On the two-VM sample from the module's documentation:

| Expression | Result |
|---|---|
| `proxmox_vms \| items2dict(key_name='name', value_name='vmid')` | `{'pxe.home.arpa': 100, 'test1': 101}` |
| `proxmox_vms \| items2dict(key_name='vmid', value_name='name')` | `{100: 'pxe.home.arpa', 101: 'test1'}`, with integer keys |

With a third VM also named `test1`, VMID 105, the name map came out as `{'pxe.home.arpa': 100, 'test1': 105}`. VM 101 disappeared without an error: the last item with a key wins. The collection's modules don't guess: when given a name, they look the VMID up with a shared helper, `get_vmid`, which fails with *"Multiple VMs with name test1 found, provide vmid instead"*. Keying by VMID avoids the problem.

## zip and dict(): two lists into one dict

`zip` pairs two lists item by item. Jinja's `range(300, 303)` counts from 300 up to 302: the end is left out. Both come together when giving new VMs consecutive VMIDs from a reserved range:

```yaml
new_vm_names: [pg1, pg2, pg3]
vmid_by_name: "{{ dict(new_vm_names | zip(range(300, 303))) }}"
```

`new_vm_names | zip(range(300, 303))` gave a list of pairs, `[['pg1', 300], ['pg2', 301], ['pg3', 302]]`. `dict()`, a Jinja function, builds a dict from pairs: `{'pg1': 300, 'pg2': 301, 'pg3': 302}`. Ansible's *Data manipulation* guide uses the same `dict(… | zip(…))` pattern.

`zip` stops at the end of the shorter list. With `range(300, 302)`, one ID short, the result was `{'pg1': 300, 'pg2': 301}`: no warning, and pg3 was gone. `zip_longest` fills the gap with `None` instead, `{'pg1': 300, 'pg2': 301, 'pg3': None}`, which at least shows up. An `ansible.builtin.assert` task, which fails when a condition is false, can check that both lists have the same length and stop the play before anything is created.

## Which one

- **dict to list:** `dict2items`, with `key_name` and `value_name` set to what the role expects.
- **list of dicts to dict:** `items2dict`, with `key_name` and `value_name` naming the two fields to keep. On a repeated key the last item wins; a missing field fails the task.
- **two lists to dict:** `dict(keys | zip(values))`. `zip` drops what the longer list has left over.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/02-lists-and-dicts-back-and-forth), runs all of the above on the local machine, changing nothing outside its `out/` directory:
- `sysctl.yml` passes the three shapes to the kernel_settings role's input checks;
- `lists-to-dicts.yml` runs the Foreman, Proxmox, podman and `zip` examples on the recorded Foreman response and the Proxmox sample.

Its CI runs both on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst` (*Transforming dictionaries into lists*, *Transforming lists into dictionaries*) and `playbook_guide/complex_data_manipulation.rst` (`zip`, `zip_longest` and `dict()`).
- Linux System Roles, cloned at their release tags from [github.com/linux-system-roles](https://github.com/linux-system-roles): kernel_settings 1.6.0 (`README.md`, `tasks/assert_role_vars.yml`), podman 1.14.3 (`tasks/handle_quadlet_spec.yml`), sudo 1.5.0 (`tasks/main.yml`) and postgresql 1.9.0 (`README.md`, `templates/postgresql.conf.j2`).
- PostgreSQL 18 documentation, [Managing Kernel Resources](https://www.postgresql.org/docs/18/kernel-resources.html): *Linux Memory Overcommit* and *Linux Huge Pages* (`doc/src/sgml/runtime.sgml` at tag `REL_18_6`).
- Foreman 5.0.0: `app/views/api/v2/hosts/main.json.rabl` and `app/models/concerns/host_params.rb`. [theforeman.foreman](https://github.com/theforeman/foreman-ansible-modules) 5.13.0: `tests/test_playbooks/fixtures/host_info-0.yml` for the recorded response, `plugins/inventory/foreman.py` for `want_params`.
- [community.proxmox](https://github.com/ansible-collections/community.proxmox) 2.0.0: `plugins/modules/proxmox_vm_info.py` for the sample, `plugins/module_utils/proxmox.py` for the duplicate-name error.
- Every result above came from ansible-core 2.21.4 on 2026-10-01, on the local machine, with the recorded Foreman response and the Proxmox sample as data. No Foreman or Proxmox server was involved.
