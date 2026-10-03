# The Proxmox inventory plugin: guests as hosts, filtered by tag and status

Seventeenth entry in the Ansible inventory from scratch series. [Item 13](inventory-is-the-loop-delegate-to.md) made the VMs hosts of the inventory instead of a list in a variable, but wrote them by hand. When the VMs already exist on a hypervisor, the hypervisor is the place that knows them, and a *dynamic inventory plugin* asks it each time Ansible runs instead. [Item 11](targeting-hosts-static-and-dynamic-inventory.md) used one such plugin, `constructed`, which builds groups from hosts other sources added; this entry uses one that adds hosts itself, from Proxmox VE. Everything below ran with ansible-core 2.21.4, community.proxmox 2.0.0 and community.general 13.4.0.

## Proxmox VE and its guests

Proxmox VE is a virtualization platform. A *node* is one physical server running it; nodes join into a cluster. A *guest* is what runs on a node, of two types: a QEMU virtual machine (`qemu`) or an LXC container (`lxc`). Each guest has a numeric ID, the *VMID*, a name, a status (`running`, `stopped`), optional *tags* (free labels, stored as one string such as `infra;pxe`), and may belong to a *pool*, a named set of guests. A guest can also be a *template*, a frozen VM that others are cloned from. Everything is reachable through a REST API under `/api2/json`.

The example doesn't need a cluster: a small Python server answers the API calls the plugin makes, which its source lists, with recorded responses. The guests are the ones of [part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md) and [part 12](groupby-lists-mergeby-proxmox-guests.md) of the data-shaping series, with tags added:

| VMID | Type | Name | Node | Status | Tags | Pool |
|---|---|---|---|---|---|---|
| 100 | qemu | pxe.home.arpa | pve | running | infra;pxe | |
| 101 | qemu | test1 | pve2 | stopped | test | pool1 |
| 102 | lxc | test-lxc.home.arpa | pve | running | test;web | |
| 103 | lxc | test1-lxc.home.arpa | pve2 | stopped | test | pool1 |
| 104 | lxc | test-lxc.home.arpa | pve2 | stopped | web | pool1 |
| 105 | lxc | (empty) | pve2 | stopped | | pool1 |
| 9000 | qemu | debian-13-tmpl | pve | template | template | |

Two guests share a name, and one has none. Both are allowed by Proxmox, and both matter below.

## The plugin and its configuration file

An inventory plugin is configured by a YAML file passed to `-i` like any inventory. The Proxmox one is `community.proxmox.proxmox`, from the community.proxmox collection, and it needs the Python library `requests` in Ansible's own Python. The file name must end in `proxmox.yml` or `proxmox.yaml`, or the plugin skips it:

```yaml
# inventory/guests.proxmox.yml
plugin: community.proxmox.proxmox
url: http://127.0.0.1:18170
user: ansible@pve
filters:
  - proxmox_name != ''
```

The password isn't in the file: the plugin reads `PROXMOX_PASSWORD` from the environment when the file has none, and the same goes for `PROXMOX_URL`, `PROXMOX_USER`, and `PROXMOX_TOKEN_ID` with `PROXMOX_TOKEN_SECRET` for an API token. [Item 10](inventory-secrets-vault-yml-aliases.md) covers keeping secrets out of an inventory. Nothing has to be enabled: Ansible's default `auto` plugin reads the `plugin:` key and loads the plugin it names.

## Guests and nodes as hosts, in the plugin's groups

`ansible-inventory --graph`, from [item 6](inventory-checking-with-ansible-inventory.md), on that file:

- Each guest is a host named after the guest, and each node is a host too, in `proxmox_nodes`. `exclude_nodes: true` leaves the nodes out.
- The plugin makes its own groups, all prefixed `proxmox_` (the `group_prefix` option): `proxmox_all_qemu` and `proxmox_all_lxc`, `proxmox_all_running` and `proxmox_all_stopped`, one per node and type such as `proxmox_pve2_lxc`, one per pool, `proxmox_pool_pool1`, and `proxmox_all_templates`.
- The template is a host, in `proxmox_all_templates` only: not in `proxmox_all_qemu`, not in `proxmox_all_stopped`. A play on `all` includes it; `not proxmox_template` in the filters drops it.
- Each host gets a few variables from the guest list alone: `proxmox_vmid`, `proxmox_name`, `proxmox_node`, `proxmox_status`, `proxmox_vmtype`, `proxmox_template`, and `proxmox_tags` when the guest has tags, as the raw string.

Those groups combine with the [host patterns of item 11](targeting-hosts-static-and-dynamic-inventory.md), as the `want_facts` section shows.

## Two guests, one name: one host

Inventory hosts are keyed by name, and the plugin names hosts after guests. VMIDs 102 and 104 both became the single host `test-lxc.home.arpa`. Its variables are those of the last guest read, 104, *stopped on pve2*, while its groups are those of both: it's in `proxmox_all_running` and `proxmox_all_stopped`, `proxmox_pve_lxc` and `proxmox_pve2_lxc`. Nothing warns. A play on `proxmox_all_running` would reach it with the address of the stopped container, as the next sections show. The plugin has no option to name hosts by VMID; unique guest names in Proxmox are the fix.

## Filters: by status and by tag

`filters:` is a list of Jinja expressions; a guest becomes a host only if all are true. Without `want_facts`, they can only use the variables above:

```yaml
filters:
  - proxmox_name != ''
  - proxmox_status == 'running'
  - "'test' in (proxmox_tags | default('')).split(';')"
```

That kept only `test-lxc.home.arpa`. `proxmox_tags` is a string, so the expression splits it at `;` before testing membership: `'test' in proxmox_tags` alone would also match a tag such as `latest`, since `in` on a string looks for a substring. `default('')` covers guests with no tags, where the variable is absent.

The trap is a filter on a variable that doesn't exist yet. `proxmox_tags_parsed`, the tags as a list, comes only with `want_facts` (next section). Without it, `'test' in proxmox_tags_parsed` printed five warnings, *Could not evaluate host filter … 'proxmox_tags_parsed' is undefined*, and kept **every** guest: the plugin's source ignores a filter that errors, unless `strict: true`, which turns the error into a failure.

## want_facts: the configuration as variables, and ansible_host

With `want_facts: true`, the plugin also fetches each guest's status, configuration and snapshots, and adds them as `proxmox_*` variables: `proxmox_cores`, `proxmox_memory`, `proxmox_net0` split into a dictionary, `proxmox_tags_parsed`, and, for a VM with the QEMU guest agent enabled, `proxmox_agent_interfaces`, the addresses the agent reports from inside the guest. For running containers it adds `proxmox_lxc_interfaces`.

The plugin doesn't set `ansible_host` for guests, so Ansible connects to the guest's name. `compose:`, an option inventory plugins share with `constructed`, sets variables from expressions; `keyed_groups:` makes a group per value:

```yaml
want_facts: true
exclude_nodes: true
filters:
  - proxmox_name != ''
  - not proxmox_template
compose:
  # The guest agent's first address if it reports one, else the static IP in
  # the configuration: cloud-init's ipconfig0 for a VM, net0 for a container.
  ansible_host: >-
    (proxmox_agent_interfaces | default([]) | rejectattr('name', 'eq', 'lo')
     | map(attribute='ip-addresses') | flatten | first
     | default(proxmox_ipconfig0.ip | default(proxmox_net0.ip)))
    | split('/') | first
keyed_groups:
  - key: proxmox_tags_parsed | default([])
    prefix: tag
```

*cloud-init* is the tool that configures a VM's network at first boot; Proxmox stores its settings as `ipconfig0`. The result: pxe.home.arpa at 192.168.1.100 from its agent, test1 at .101 from cloud-init, the containers from `net0`. The groups `tag_infra`, `tag_pxe`, `tag_test` and `tag_web` appeared. The duplicate name showed up again: `test-lxc.home.arpa` had `ansible_host` 192.168.1.104 and status stopped, yet `tag_test:&proxmox_all_running` matched it, from guest 102's tag and status. Its variables were a mix, too: the plugin sets them one by one, so 104 overwrote the ones both guests have, and `proxmox_lxc_interfaces`, which only the running 102 has, stayed from 102.

The facts cost requests. The mock counts them: 8 without facts, 31 with `want_facts`, because the plugin fetches the facts of every guest before filtering, the template and the unnamed one included. `want_post_filter_facts: true` instead of `want_facts` fetches them only for the guests the filters keep: 25 requests, and the same inventory, as long as the filters use only the basic variables.

## Three empty inventories that exit 0

- **A guest with no name.** Without the `proxmox_name != ''` filter, the plugin tried to add a host named `""`, Ansible refused it with *Invalid empty host name provided*, and the whole source failed: not one host, only warnings, and `ansible-inventory` exited 0. A playbook would run on nothing. The filter runs before the host is added, which is why it fixes it. Setting `ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED=true` (or `any_unparsed_is_failed = true` under `[inventory]` in `ansible.cfg`) made the same run exit 1, which a CI job notices.
- **The old name.** The plugin lived in community.general as `community.general.proxmox` until it moved to community.proxmox. community.general 13.4.0 still redirects the name, in its `meta/runtime.yml`, with a deprecation: removal in 15.0.0. So `plugin: community.general.proxmox` printed *community.general.proxmox has been deprecated. The proxmox content has been moved to community.proxmox.*, loaded the new plugin, and then failed: *Invalid value 'community.general.proxmox' for config 'plugin'*, because the new plugin's `plugin` option accepts only `community.proxmox.proxmox`. The redirect doesn't keep an old configuration file working; change the name.
- **A filter on a missing fact** isn't empty but the opposite, every guest kept, as shown above.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/17-proxmox-inventory), holds the mock (`mock/server.py` and its recorded responses in `mock/api.json`), the four plugin configurations and the three pitfalls. `run.sh` starts the mock on port 18170, prints each result above, including the request counts from the mock's log, and stops it. Its CI runs it on every push and compares the output with the expected one.

## Sources

- community.proxmox 2.0.0: the plugin's documentation and source, `plugins/inventory/proxmox.py` (the API paths it calls, `filters`, `want_facts`, `want_post_filter_facts`, `exclude_nodes`, the groups, `_can_add_host` ignoring a failing filter unless `strict`).
- community.general 13.4.0: `meta/runtime.yml`, `plugin_routing.inventory.proxmox` (the redirect and its deprecation).
- ansible-core 2.21.4: `lib/ansible/config/base.yml`, `INVENTORY_ANY_UNPARSED_IS_FAILED`.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, against the example's mock of the Proxmox VE API, not a real cluster.
