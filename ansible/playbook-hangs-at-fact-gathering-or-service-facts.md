# A playbook hangs at fact gathering or `service_facts`: find the blocking call, then bound it

The play prints `TASK [Gathering Facts]` or `TASK [ansible.builtin.service_facts]` and nothing else, for hours. Ansible has no timeout on a task by default, so one command that never returns on one host holds up the whole run.

Some terms first:

- **Facts** are the variables Ansible collects about a host (OS, disks, network) before the first task, by running the `setup` module. That step is `Gathering Facts`, and `gather_facts: true`, the default, turns it on.
- **`service_facts`** is a module that lists every service on the host and its state. On a host that doesn't run systemd, or for scripts in `/etc/init.d/`, it runs `service --status-all`, which calls each script with `status`.
- An **init.d script** is the older (SysV) way to start a service: a shell script in `/etc/init.d/` that takes `start`, `stop` and `status`.
- **AAP** (Ansible Automation Platform, earlier Ansible Tower) is Red Hat's web front end that runs playbooks as jobs.

## Why it hangs

The module waits on a child process that doesn't end. Two common cases:

- **`service_facts`**: one init.d script's `status` asks a question, or waits on something unavailable. Third-party scripts reported to do this include Oracle Trace File Analyzer (`/etc/init.d/init.tfa`, asks for an Oracle SID), Splunk Forwarder (`/etc/init.d/splunk`, license prompt), Tibco and Veritas VxVM (`/etc/init.d/vx*` when volumes are unavailable).
- **Fact gathering**: a hardware fact query blocks, for example on LVM (the Linux logical volume manager) or a stale network mount.

A prompt doesn't always hang. Ansible gives the module an empty input, so a script that reads one answer gets end-of-file and carries on. The script hangs when it asks again until it gets a non-empty answer: with no input it loops for ever, at 100% CPU. That's what I reproduced with this stand-in for such a script:

```sh
#!/bin/sh
# /etc/init.d/demo-prompt
case "$1" in
  status) sid=""
    while [ -z "$sid" ]; do printf 'Choose SID: '; read sid; done
    echo "running ($sid)";;
  *) exit 0;;
esac
```

With it in place, `service_facts` printed its task header and nothing more until I killed the run.

## Find the host and the process

On the controller (the machine running `ansible-playbook`, or the AAP execution node), list the processes of the user Ansible runs as (`awx` on Tower):

```sh
ps -fww -u awx
```

The `ssh ... hostname /bin/sh -c 'sudo ... python'` line names the stuck host. Log in there and walk down from the Ansible Python process to the command that waits:

```sh
ps -ef --forest | less    # or: pstree -ap <pid of the ansible python process>
```

In my run the leaves were `/usr/sbin/service --status-all` and, under it, `/etc/init.d/demo-prompt status`.

## Find the init.d script with a time limit

Run each script's `status` with a time limit and no input, and only report the ones that ran out of time:

```sh
for svc in /etc/init.d/*; do
  timeout 5 "$svc" status >/dev/null 2>&1 </dev/null
  [ $? -eq 124 ] && echo "HANG: $svc"
done
```

`timeout` exits with 124 when it had to stop the command. Test for that value only: a stopped service's `status` exits 3 by convention, which isn't a problem. The looser `|| echo` form flagged five stopped services alongside the real culprit on the test host.

## Fix the cause

For the script, in order of preference:

- Have its owners (the DBA team for Oracle TFA) change `status` so it doesn't prompt.
- Disable it while that happens, by moving it out of the way: `mv /etc/init.d/init.tfa /etc/init.d/init.tfa.disabled`.
- Don't call `service_facts` at all and check only the services the play needs, with `ansible.builtin.systemd_service` (or `service`) in check mode, or a `command` running `systemctl is-active <name>`.

For fact gathering, leave out the subset that blocks. `gather_subset` takes subset names, with `!` to exclude one:

```ini
# ansible.cfg
[defaults]
gather_subset = !hardware
```

Or per play, `gather_subset: ['!hardware']` next to `gather_facts`. Tasks that need hardware facts (disks, memory, LVM) then won't find them. `setup` also has `gather_timeout` (10 seconds by default), but it only limits some of the hardware collectors, mount facts among them, so it doesn't catch every hang.

## Bound the task so the run fails instead of waiting

Two ways, which don't clean up the same way. Tested with ansible-core 2.21.5:

```yaml
- name: Gather service facts, at most 60 seconds
  ansible.builtin.service_facts:
  timeout: 60

- name: Or as a background job polled every 5 seconds
  ansible.builtin.service_facts:
  async: 60
  poll: 5
```

- **`timeout:`** is a task keyword: the task fails with `Task failed: Timed out after 60 second(s).` But on the managed host `service --status-all` and the script were still running afterwards, the script spinning at full CPU. The keyword also works on a block, a role or a play, and `task_timeout` in `ansible.cfg` (`ANSIBLE_TASK_TIMEOUT`) sets it for every task; it's 0, no limit, by default.
- **`async:` with `poll:`** runs the module as a background job on the host and checks on it every `poll` seconds. After `async` seconds the task failed with `Timeout exceeded`, and the job's processes were gone.

So `async` leaves a cleaner host for a single task such as `service_facts`. Add `ignore_errors: true` only if the play can do without the result; otherwise let it fail, so the host shows up in the recap.

On AAP, a job template's **Timeout** field (also `timeout` in `/api/v2/job_templates/<id>/`) and the global **Default Job Timeout** under the Jobs settings cancel the whole job after that many seconds. That ends the run, but doesn't tell you which host or command blocked.

## Sources

- ansible-core 2.21.5: `ansible-doc setup` (`gather_subset`, `gather_timeout`), `ansible-config dump` (`TASK_TIMEOUT`), and `lib/ansible/modules/service_facts.py`, where `ServiceScanService` runs `service --status-all`.
- Ansible docs: [Playbook keywords](https://docs.ansible.com/ansible/latest/reference_appendices/playbooks_keywords.html) (`timeout`) and [Asynchronous actions and polling](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_async.html).
- A Red Hat troubleshooting note on playbooks hanging at fact gathering and in `service_facts`, which lists the third-party scripts above.

The `service_facts` hang, the diagnostic loop and both time limits ran against a stand-in init.d script on an Ubuntu container without systemd, with `connection: local`. Not run: the third-party scripts themselves, an LVM or mount hang in fact gathering, `systemd_service` checks on a systemd host, and AAP.
