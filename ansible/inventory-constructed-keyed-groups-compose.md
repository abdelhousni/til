# ansible.builtin.constructed: keyed_groups, groups and compose on top of another source

Eighteenth entry in the Ansible inventory from scratch series. [The previous entry](inventory-proxmox-plugin-guests-as-hosts.md) turned the guests of a Proxmox VE cluster into hosts with the `community.proxmox.proxmox` inventory plugin. Its groups follow Proxmox's own layout: one per node, per guest type, per status and per pool. This entry builds the groups a playbook wants from what the plugin returns, with the `ansible.builtin.constructed` plugin, and compares that with setting the same options on the proxmox plugin itself. Everything below ran with ansible-core 2.21.4 and community.proxmox 2.0.0.

## The setup

[Item 11](targeting-hosts-static-and-dynamic-inventory.md#groups-built-from-a-variable) introduced `constructed`: an inventory plugin that reads the hosts the earlier sources of the same inventory added, and creates groups and variables from their variables. Its `keyed_groups` option makes one group per value of an expression, and item 11 showed it on an `env` variable, with the `strict: true` pitfall. This entry covers the rest of its options.

The other source here is the proxmox plugin. *Proxmox VE* is a hypervisor that runs *guests*, QEMU virtual machines and LXC containers, on cluster members called *nodes*; each guest can carry *tags*, free-form labels, which Proxmox stores as one string separated by `;`. The example points the plugin at a small mock of the Proxmox API, with five guests modelled on those of [part 12 of the data-shaping series](groupby-lists-mergeby-proxmox-guests.md), each given tags and a static IP:

| Guest | Type | Status | Tags | OS type | Pool |
|---|---|---|---|---|---|
| pxe.home.arpa | qemu | running | infra, dhcp | l26 | |
| test1 | qemu | stopped | web, staging | (none) | pool1 |
| test-lxc.home.arpa | lxc | running | web, prod | debian | |
| test1-lxc.home.arpa | lxc | stopped | db, prod | debian | pool1 |
| test2-lxc.home.arpa | lxc | stopped | (none) | alpine | |

The inventory is a directory with two sources, read in name order, and a `group_vars/` directory:

- `10-pve.proxmox.yml`: the proxmox plugin, with `want_facts: true`, which reads each guest's configuration too, and `exclude_nodes: true`, which keeps the nodes themselves out.
- `20-constructed.yml`: the `constructed` source. It runs second, so it sees the guests.
- `group_vars/proxmox_pool_pool1/owner.yml`: `owner: team-a` for the guests in pool1.

Alone, the proxmox source builds `proxmox_all_lxc`, `proxmox_all_qemu`, `proxmox_all_running`, `proxmox_all_stopped`, `proxmox_pool_pool1` and one group per node and type, such as `proxmox_pve2_lxc`. Each guest gets variables prefixed `proxmox_`; for test1:

```text
proxmox_ipconfig0 = {"gw":"10.0.10.1","ip":"10.0.10.101/24"}
proxmox_status = "stopped"
proxmox_tags = "web;staging"
proxmox_tags_parsed = ["web","staging"]
```

`proxmox_tags_parsed`, the tags as a list, and the IP settings come from the guest's configuration, so only with `want_facts: true`.

## keyed_groups

```yaml
plugin: ansible.builtin.constructed
strict: false
use_vars_plugins: true
leading_separator: false
keyed_groups:
  - key: proxmox_tags_parsed | default([''])
    prefix: tag
    default_value: untagged
  - key: proxmox_status
    prefix: status
  - key: "{'os': proxmox_ostype | default('')}"
    trailing_separator: false
  - key: owner
    prefix: owner
```

A group's name is the prefix, the separator (`_` by default) and the value; the result is cleaned into a valid group name, which is how `team-a` became `owner_team_a`. What each entry gave:

- **A list makes one group per item.** The tags gave `tag_web`, `tag_prod`, `tag_db`, `tag_staging`, `tag_infra` and `tag_dhcp`; test-lxc is in both `tag_web` and `tag_prod`.
- **`default_value` names the group for an empty value.** test2-lxc has no tags, so no `proxmox_tags_parsed` at all; `default([''])` turns that into a list with one empty item, and `default_value` turns the empty item into `tag_untagged`. Without `default_value`, the empty item gave a group named `tag_`. Without the `default([''])`, the key failed on test2-lxc, and with `strict: false` the entry was skipped for that host without a warning: test2-lxc was in no tag group.
- **A string makes one group.** The status gave `status_running` and `status_stopped`.
- **A dict makes `<key><separator><value>` per item, and `trailing_separator` handles an empty value.** test1's configuration has no OS type. With the default, `trailing_separator: true`, test1 went to `os_`; with `false`, to `os`. The documentation lists `default_value` and `trailing_separator` as mutually exclusive, and ansible-core's code applies `trailing_separator` to dict keys only.
- **`leading_separator: false` drops the `_` in front when the prefix is empty.** The dict entry has no prefix, and with the default, `true`, its groups were `_os_debian`, `_os_l26`, `_os_alpine` and `_os_`. It's an option of the whole source, not of one entry.

## groups: conditions

`groups` maps a group name to a condition, a Jinja2 expression that is true or false; the host joins the group when it's true. A Jinja2 *test*, written `value is test(argument)`, is a check that returns true or false:

```yaml
groups:
  web_prod: "['web', 'prod'] is subset(guest_tags)"
  prod_down: "'prod' in guest_tags and proxmox_status is eq('stopped')"
  local_domain: inventory_hostname is search('\\.home\\.arpa$')
```

`web_prod` got test-lxc, `prod_down` got test1-lxc, the prod guest that is stopped, and `local_domain` got the four guests whose name ends in `.home.arpa`. `guest_tags` is a variable the same source sets with `compose`, below.

## compose: variables

`compose` sets a host variable to the result of an expression, here `ansible_host`, the address Ansible connects to, which [item 4](inventory-connection-variables-ssh-docker-local.md) introduced:

```yaml
compose:
  guest_tags: proxmox_tags_parsed | default([])
  ansible_host: (proxmox_ipconfig0 | default(proxmox_net0)).ip | split('/') | first
```

A QEMU guest keeps its IP in `ipconfig0` (cloud-init settings), an LXC container in `net0`; the plugin splits both into dicts. Each guest got its address, test1 `10.0.10.101`. In `constructed.py`, `compose` runs before `groups` and `keyed_groups` for each host, which is why `groups` can use `guest_tags`: it names an expression once instead of repeating `proxmox_tags_parsed | default([])` in each condition.

One display detail: the proxmox plugin marks the values it reads from the API as *unsafe*, strings Ansible will never render as a template, in case they contain `{{`. `ansible-inventory --list` prints such values, and values composed from them, as `{"__ansible_unsafe": "10.0.10.101"}`, where `--host test1` prints `"10.0.10.101"`. A script reading `--list` has to unwrap them.

## The same options on the proxmox plugin

The proxmox plugin is *Constructable*: it accepts `keyed_groups`, `groups`, `compose`, `strict` and `leading_separator` itself, from the same documentation fragment. `direct/` sets the options above on it, with no `constructed` source and the same `group_vars/`. Every group came out the same, but one: `owner_team_a` was missing, although `ansible-inventory --host test1` showed `owner: team-a`.

The proxmox plugin evaluates the options as it adds each guest, from the guest's own variables. `group_vars/` are read by vars plugins, and the `constructed` documentation says those normally run only after every source is parsed; `constructed` runs them early when `use_vars_plugins: true`, for the groups its host is already in, `proxmox_pool_pool1` here. With `strict: false`, the missing variable dropped the group silently.

So the options on the dynamic plugin are enough while the groups depend only on what it returns. A separate `constructed` source is needed when they depend on:

- **inventory variables**, from `group_vars/` or `host_vars/`, as `owner` here;
- **several sources**: `constructed` sees the hosts and variables of every source read before it, as item 11's second file showed, where a plugin only sees its own;
- **one rule for several plugins**: a `constructed` source can name groups the same way whatever source the hosts came from.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/18-constructed), holds the mock Proxmox API, the inventory, the variant with the defaults and the `direct/` inventory. `run.sh` starts the mock, prints the groups and variables of the proxmox source alone, the groups and `ansible_host` values `constructed` adds, the keyed groups with the defaults, and the groups of `direct/`. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `lib/ansible/plugins/inventory/constructed.py` (`use_vars_plugins`, the order of `compose`, `groups` and `keyed_groups`), `lib/ansible/plugins/doc_fragments/constructed.py` (`default_value`, `trailing_separator`, `leading_separator`), and `_add_host_to_keyed_groups` in `lib/ansible/plugins/inventory/__init__.py`.
- community.proxmox 2.0.0: `plugins/inventory/proxmox.py` (its options, `proxmox_tags_parsed`, `_add_host`, the values marked unsafe).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine, against the example's mock API.
