# Let the inventory be the loop: delegate_to instead of a list of hosts

Thirteenth entry in the Ansible inventory from scratch series. [Item 12](inventory-limit-in-practice.md) showed what `--limit` does to a run. This entry is about a layout that `--limit` can't reach: a list of hosts kept in a variable, looped over by a task. The Red Hat Community of Practice's *automation good practices* have a rule against it, *Rely on your inventory to loop over hosts, don't create lists of hosts*, and illustrate it with provisioning: creating VMs through a manager, such as a hypervisor or Foreman. This entry runs that case three ways and measures the four reasons the rule gives. Everything below ran with ansible-core 2.21.4.

## The case

A fake manager, `manager1`, stands in for the hypervisor: creating a VM is a task that takes one second, then writes a file named after the VM holding its size. Five VMs: app1, app2 and app3 with 2 CPUs and 4096 MB, db1 and db2 with 4 CPUs and 8192 MB, except db1, which gets 16384 MB. Every layout also has the VMs in the inventory, in groups `app` and `db` under `vms`, because later plays configure them once they exist.

- **Bad:** `host_vars/manager1/` holds `manager_vms`, a list of five entries, each with the VM's name, CPUs and memory. A play on `managers` loops over it.
- **Not so bad:** the list holds only the names. Each VM's size lives in its own variables, `group_vars/app/`, `group_vars/db/` and `host_vars/db1/`, and the loop reads them with `hostvars[item]`. The good practices call this a fallback, *"if for some reason, you can't follow the recommendation"*.
- **Good:** no list. A play on `vms` runs once per VM, and each task carries `delegate_to: "{{ vm_manager }}"`, with `vm_manager: manager1` in `group_vars/vms/`. *Delegation* runs a task on another host, here the manager, while `inventory_hostname` and the variables stay those of the VM the play is on.

```yaml
- name: Provision each VM from its manager
  hosts: vms
  gather_facts: false  # the VMs don't exist yet
  tasks:
    - name: Record the VM on the manager
      ansible.builtin.copy:
        content: "{{ vm_cpus }} cpus, {{ vm_memory_mb }} MB\n"
        dest: "{{ playbook_dir }}/out/manager/{{ inventory_hostname }}.txt"
        mode: "0644"
      delegate_to: "{{ vm_manager }}"
```

All three created the same five files with the same sizes.

## Reason 1 and 2: one list to maintain, and the data twice

*"A list of hosts is more difficult to maintain than an inventory structure"*, and *"you avoid duplicating information"*. A search for app3 and for 4096 in each layout:

| Layout | app3 is written in | 4096 is written in |
|---|---|---|
| bad | `hosts.yml`, `host_vars/manager1/provision.yml` | `host_vars/manager1/provision.yml`, three times |
| not so bad | `hosts.yml`, `host_vars/manager1/provision.yml` | `group_vars/app/vm.yml` |
| good | `hosts.yml` | `group_vars/app/vm.yml` |

In the bad layout, adding a VM means editing two files that nothing keeps in step, and a size shared by a group is repeated per VM. The not-so-bad layout fixes the sizes, which [item 2](inventory-directory-group-vars-per-role.md)'s `group_vars/` and `host_vars/` inherit like any variable, but still names each VM twice.

## Reason 3: parallelism

*"As you loop through the hosts of an inventory, Ansible helps you with parallelization, throttling, etc."* A loop is one task on one host, the manager, so its iterations run one after another: both loops took 5 seconds or more for five one-second calls. The good play ran on five hosts at once, the number Ansible's `forks` setting allows, 5 by default and in the example, and took under 5 seconds. With real calls that take minutes, the difference is minutes times the number of VMs.

## Reason 4: --limit

*"You can very simply limit the play to certain hosts, using for example the `--limit` parameter."* To recreate db1 only:

- good, `--limit db1`: only `db1.txt` was written.
- bad, `--limit db1`: nothing was written, and the play printed *skipping: no hosts matched*, because the play runs on the manager, not on db1. The run still exits 0.
- bad, `--limit manager1`: the only limit that runs the play, and it provisioned all five VMs.

With a list, limiting to some VMs needs another variable, or an edit to the list.

## The trap of the good layout: facts from VMs that don't exist

A play on the VMs gathers facts from them first, unless told not to, and before provisioning there's nothing to connect to. In the example the VMs connect over SSH to a port where nothing listens, as a VM not yet created would. With `gather_facts: true`, all five were *UNREACHABLE* and the run exited 4; nothing reached the manager. `gather_facts: false` on the play avoids it. The delegated tasks then connect the way the manager does, locally here, and never to the VM: delegation uses the connection settings of the host it delegates to.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/13-inventory-is-the-loop), holds the three layouts and their playbooks. `run.sh` searches each layout, provisions the five VMs with each, runs the `--limit` cases and the fact-gathering pitfall; it prints durations as a range, since five sequential one-second calls can't take less than 5 seconds. Its CI runs it on every push and compares the output with the expected one.

The same rule applies on the series' PostgreSQL stack: a database role for each app host, created on db1, is a play on `app` with `delegate_to: db1`, not a loop over a list of app hosts. [Part 11 of the data-shaping series](data-from-other-hosts-extract-hostvars-pg-hba.md) reads data from other hosts with `hostvars`, and [part 15](set-fact-loop-or-one-expression-pg-hba.md) compares a `set_fact` loop with one expression.

## Sources

- Red Hat CoP, [automation good practices](https://redhat-cop.github.io/automation-good-practices/), from [redhat-cop/automation-good-practices](https://github.com/redhat-cop/automation-good-practices): `inventories/README.adoc`, *Rely on your inventory to loop over hosts, don't create lists of hosts*.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_delegation.rst` (*Delegating tasks*).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
