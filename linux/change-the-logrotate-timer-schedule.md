# Changing when logrotate runs: the systemd timer, from the command line and with Ansible

On current distributions logrotate isn't started by cron any more. It's started by a **systemd timer**, a unit that starts another unit on a schedule. Here `logrotate.timer` starts `logrotate.service`, which runs `logrotate /etc/logrotate.conf`. A **unit** is any object systemd manages, such as a service, a timer or a mount, and it's described by a unit file.

Ubuntu 24.04 still ships `/etc/cron.daily/logrotate`, but its first lines skip the run when systemd is the init system:

```sh
# skip in favour of systemd timer
if [ -d /run/systemd/system ]; then
    exit 0
fi
```

That means editing crontab or `/etc/cron.daily` doesn't change anything. The schedule to change is the timer's.

## What the package ships

```console
$ systemctl cat logrotate.timer
# /usr/lib/systemd/system/logrotate.timer
[Unit]
Description=Daily rotation of log files
Documentation=man:logrotate(8) man:logrotate.conf(5)

[Timer]
OnCalendar=daily
AccuracySec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

The `[Timer]` settings:

- `OnCalendar=` is when the timer fires, written as a calendar expression. `daily` is short for `*-*-* 00:00:00`, midnight every day.
- `AccuracySec=1h` lets systemd start the job up to an hour late, so it can group wake-ups with other timers.
- `Persistent=true` runs a missed job at the next boot if the machine was off when it was due.

Don't edit this file. It's under `/usr/lib`, which belongs to the package, so the next logrotate update overwrites it. Add a **drop-in** instead: a `.conf` file in `/etc/systemd/system/logrotate.timer.d/` whose settings systemd applies on top of the packaged unit.

## Check the new schedule first

`systemd-analyze calendar` shows how systemd reads an expression and when it fires next:

```console
$ systemd-analyze calendar '*-*-* 03:30:00' 'Mon..Fri 03:30'
  Original form: *-*-* 03:30:00
Normalized form: *-*-* 03:30:00
    Next elapse: Fri 2026-10-16 03:30:00 UTC
       From now: 19h left

  Original form: Mon..Fri 03:30
Normalized form: Mon..Fri *-*-* 03:30:00
    Next elapse: Fri 2026-10-16 03:30:00 UTC
```

The format is `weekday year-month-day hour:minute:second`, and `*` matches any value. `man systemd.time` lists the whole syntax.

## From the command line

Interactively, `sudo systemctl edit logrotate.timer` opens an editor on a new drop-in (`override.conf`) and reloads systemd when you save. In a script, write the file yourself and reload:

```sh
sudo mkdir -p /etc/systemd/system/logrotate.timer.d
sudo tee /etc/systemd/system/logrotate.timer.d/schedule.conf <<'EOF'
[Timer]
OnCalendar=
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=15m
EOF
sudo systemctl daemon-reload
```

`systemctl daemon-reload` makes systemd read unit files again. Until you run it, systemd keeps using the schedule it already loaded. `systemctl edit --stdin` would also do this without an editor, but it needs systemd 256 or later. Ubuntu 24.04 has systemd 255, which rejects the option.

`RandomizedDelaySec=15m` adds a random delay of up to 15 minutes, so many servers with the same drop-in don't all rotate at the same moment. Leave it out if the time must be exact.

### The empty `OnCalendar=` line is required

`OnCalendar=` is a list. A drop-in adds to it, so without the empty line the timer keeps `daily` and also fires at 03:30:

```console
$ systemctl show logrotate.timer -p TimersCalendar      # drop-in without the empty line
TimersCalendar={ OnCalendar=*-*-* 03:30:00 ; next_elapse=... }
TimersCalendar={ OnCalendar=*-*-* 00:00:00 ; next_elapse=... }
```

The empty assignment clears the list, and the next line sets the only schedule.

### Check the result

```console
$ systemctl show logrotate.timer -p TimersCalendar -p RandomizedDelayUSec
TimersCalendar={ OnCalendar=*-*-* 03:30:00 ; next_elapse=Fri 2026-10-16 03:30:00 UTC }
RandomizedDelayUSec=15min

$ systemctl list-timers logrotate.timer
NEXT                        LEFT LAST PASSED UNIT            ACTIVATES
Fri 2026-10-16 03:38:22 UTC  19h -         - logrotate.timer logrotate.service
```

`NEXT` is 03:38 here because of the random delay. To go back to the packaged schedule, delete the drop-in directory and reload:

```sh
sudo rm -r /etc/systemd/system/logrotate.timer.d
sudo systemctl daemon-reload
```

## With Ansible

No module or system role in the standard collections changes a timer's schedule, so the playbook writes the same drop-in with `ansible.builtin` modules. Reloading and restarting happen in a **handler**: a task that runs once at the end of the play, and only if a task that notifies it reported a change.

```yaml
---
- name: Change the logrotate timer schedule
  hosts: all
  become: true
  vars:
    logrotate_on_calendar: "*-*-* 03:30:00"
    logrotate_randomized_delay: 15m

  tasks:
    - name: Create the drop-in directory
      ansible.builtin.file:
        path: /etc/systemd/system/logrotate.timer.d
        state: directory
        owner: root
        group: root
        mode: "0755"

    - name: Write the schedule drop-in
      ansible.builtin.copy:
        dest: /etc/systemd/system/logrotate.timer.d/schedule.conf
        owner: root
        group: root
        mode: "0644"
        content: |
          # Managed by Ansible
          [Timer]
          OnCalendar=
          OnCalendar={{ logrotate_on_calendar }}
          RandomizedDelaySec={{ logrotate_randomized_delay }}
      notify: Restart logrotate timer

    - name: Make sure the timer is enabled and running
      ansible.builtin.systemd_service:
        name: logrotate.timer
        enabled: true
        state: started

  handlers:
    - name: Restart logrotate timer
      ansible.builtin.systemd_service:
        name: logrotate.timer
        state: restarted
        daemon_reload: true
```

- `ansible.builtin.systemd_service` is the current name of the module. `ansible.builtin.systemd` is an alias for the same module.
- `daemon_reload: true` runs `systemctl daemon-reload` before the restart, and the restart makes the timer calculate its next run from the new schedule.
- To check an expression before it reaches the hosts, run `systemd-analyze calendar` with the value of `logrotate_on_calendar`.

The first run reports three changes and runs the handler. A second run changes nothing:

```console
$ ansible-playbook -i inventory.ini playbook.yml
...
RUNNING HANDLER [Restart logrotate timer] **************************************
changed: [sd]
sd   : ok=5    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0

$ ansible-playbook -i inventory.ini playbook.yml
sd   : ok=4    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

`ansible-lint` passes the playbook with its `production` profile.

## Sources

- What was run: Ubuntu 24.04 with systemd 255 and logrotate 3.21.0, in a privileged Docker container booted with systemd as PID 1. The playbook ran with ansible-core 2.21.5 over the `community.docker.docker` connection (community.docker 5.4.0), as root without `become`, because the container has no `sudo`. Other distributions and real servers weren't tested.
- `man systemd.timer`, `man systemd.time` and `man systemd.unit` (the drop-in section).
- [`ansible.builtin.systemd_service`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/systemd_service_module.html).
