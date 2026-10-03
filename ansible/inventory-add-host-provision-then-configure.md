# add_host: provision then configure in one run

Twenty-first entry in the Ansible inventory from scratch series. [Item 13](inventory-is-the-loop-delegate-to.md) provisioned VMs through a fake manager, with the VMs already listed in the inventory. This entry takes the case where they aren't: the VMs get their names and addresses only when the manager creates them, and the same run must then configure them. The tool for that is `ansible.builtin.add_host`, a module that adds a host to the *in-memory inventory*: the copy of the inventory that `ansible-playbook` builds when it starts and works from until it ends. Everything below ran with ansible-core 2.21.4.

## The case

The inventory holds only the manager, `manager1`, in group `managers`. Its `host_vars/` say what to order, not which hosts: a prefix, a count and a size.

```yaml
vm_order:
  prefix: web
  count: 3
  cpus: 2
  memory_mb: 4096
```

A *playbook* is a list of *plays*, and each play runs its tasks on the hosts its `hosts:` line names. The example's `site.yml` imports two:

- `provision.yml`, a play on `managers`. Its first task creates web01, web02 and web03 on the manager, a fake API call that writes a file per VM with its size and an address from 192.0.2.0/24, a range reserved for documentation. Its second task adds each VM to the inventory:

  ```yaml
  - name: Add each VM to the groups web and new_vms, with its variables
    ansible.builtin.add_host:
      name: "{{ item }}"
      groups:
        - web
        - new_vms
      ansible_host: "192.0.2.{{ 10 + index }}"
      vm_cpus: "{{ vm_order.cpus }}"
      vm_manager: "{{ inventory_hostname }}"
    loop: "{{ vm_names }}"
    loop_control:
      index_var: index
  ```

- `configure.yml`, a play on `web`, a group that doesn't exist when the run starts. It writes what each VM received to a file.

Here the loop is over names that only the manager knows, which is what `add_host` is for. Item 13's rule against lists of hosts applies once the hosts are in the inventory: the configure play runs on them as hosts, not in a loop.

## What an added host receives

The configure play ran on the three VMs. web01 received:

```text
groups: new_vms,web
ansible_host: 192.0.2.10, vm_cpus: 2, vm_manager: manager1
web_port (group_vars/web/): 8080
ansible_connection (group_vars/all/): local
```

- `groups:` puts the host in each group listed, creating the group when it doesn't exist.
- Every other key becomes a host variable, here `ansible_host`, the address Ansible connects to (see [item 4](inventory-connection-variables-ssh-docker-local.md)), and two variables of the example's own.
- The inventory's `group_vars/` apply to the added hosts, as [item 2](inventory-directory-group-vars-per-role.md) describes for any host: `group_vars/all/` gave them the local connection, and `group_vars/web/` gave them `web_port`, although `web` is created only by `add_host`.

## Nothing remains after the run

`ansible-inventory --graph`, which prints the inventory as Ansible reads it ([item 6](inventory-checking-with-ansible-inventory.md)), showed only `manager1` before the run and again after it. Running `configure.yml` on its own afterwards warned *Could not match supplied host pattern, ignoring: web*, printed *skipping: no hosts matched* and exited 0. The module's documentation says so in its description, *"in-memory inventory"* and *"for use in later plays of the same playbook"*: the hosts live as long as the `ansible-playbook` process. A second run that must reach them has to create them again, or find them somewhere that lasts.

## --limit applies to the added hosts too

`--limit` restricts a run to the hosts that match its pattern ([item 12](inventory-limit-in-practice.md)). The module's notes say added hosts *"will not bypass the `--limit` from the command line"*. Three runs of `site.yml`:

- `--limit manager1`: the three VMs were created and added, then the configure play printed *skipping: no hosts matched*. The run exits 0, with nothing configured.
- `--limit manager1,web02`: Ansible warned *Could not match supplied host pattern, ignoring: web02* when the run started, yet the configure play ran on web02, and only on web02. The limit is checked again for each play, and by then web02 exists.
- `--limit 'web*'`: no host matched when the run started, and it failed with *Specified inventory, host pattern and/or --limit leaves us with no hosts to target*, exit 1. Nothing was created.

To configure only some of the new VMs, the limit has to include the manager as well.

## Once per play, not once per host

Most tasks run once for each host of the play. `add_host` doesn't: its action plugin, the controller-side code of a module, sets `BYPASS_HOST_LOOP = True` (`lib/ansible/plugins/action/add_host.py`), and the module's documentation lists `bypass_host_loop` as fully supported. The linear strategy, the default order in which Ansible runs tasks across hosts, treats such a task like `run_once`: it runs once, on the first host (`lib/ansible/plugins/strategy/linear.py`).

The example's pitfall has two managers, each meant to add the VM it created:

- `add_host` with `name: "vm-of-{{ inventory_hostname }}"` and no loop added one host, `vm-of-manager1`, not two.
- The same task with `loop: "{{ groups['managers'] }}"` and `name: "vm-of-{{ item }}"` added both: with a loop, each item is one call.

The module's own example loops over `ansible_play_hosts`, the play's hosts that haven't failed. In ansible-core 2.21.4, a host that `add_host` creates is appended to that list for the rest of the play (`lib/ansible/_internal/_worker/_inventory_rpc.py`): after the first task, `ansible_play_hosts` was `manager1, manager2, vm-of-manager1`, though the play's later tasks still ran on the two managers only. A loop over `ansible_play_hosts` after an earlier `add_host` in the same play would therefore add a host for the added host too; `groups['managers']` doesn't change.

## When an inventory source is the better tool

`add_host` suits hosts that exist only from the middle of the run, created by it. Hosts that already exist in a system, a hypervisor, a cloud, a CMDB, are better read from it by an *inventory plugin*, which runs each time any command loads the inventory ([item 15](inventory-plugins-single-source-of-truth.md)): `ansible-inventory`, `--limit` and the next run then see them, which nothing above did. A group that depends on host variables is better built by the `constructed` inventory plugin ([item 11](targeting-hosts-static-and-dynamic-inventory.md)), for the same reason. After provisioning, the next run can find the new VMs through the plugin of the manager that created them.

The next entry covers `group_by`, another module that changes the in-memory inventory: it puts the play's hosts into groups by a variable or a fact.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/21-add-host), holds the inventory, the playbooks and the pitfall. `run.sh` prints the inventory before and after the run, runs `site.yml`, then `configure.yml` alone, the three `--limit` cases and the once-per-play pitfall, listing the files each play wrote. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, `ansible.builtin.add_host` module: `lib/ansible/modules/add_host.py` in ansible-core 2.21.4 (description, `bypass_host_loop` attribute, notes on `--limit`, examples).
- ansible-core 2.21.4 source: `lib/ansible/plugins/action/add_host.py` (`BYPASS_HOST_LOOP = True`), `lib/ansible/plugins/strategy/linear.py`, `lib/ansible/_internal/_worker/_inventory_rpc.py`.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_delegation.rst` (`add_host` runs on the control node and can't be delegated).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
