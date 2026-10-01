# Sudo rules that hand out a root shell, and a CI check that refuses them

A sudo rule names a command, and the user gets that command as root. Some commands give a lot more. *sudoers* files say who may run what through sudo ([this entry](../ansible/readable-sudoers-with-dict-kv.md) explains them and the drop-ins under `/etc/sudoers.d/`). This one started as a drop-in for PostgreSQL administrators:

```text
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl status postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/journalctl -u postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/vim /var/lib/pgsql/*
```

`visudo -cf`, which checks a file's syntax, accepted it. Below, each rule was tried in a Rocky Linux 9.8 container with sudo 1.9.17p2, vim 8.2 and systemd 252, as `dba1`, a member of the `postgres` group. Then comes a check that a CI pipeline (the jobs that run on every push to a repository) can run on sudoers files before they're installed.

## vim: a shell, and any file

A *shell escape* is a program's way of running another command, for example a shell. The sudoers manual, in *Preventing shell escapes*, warns: *"Common programs that permit shell escapes include shells (obviously), editors, paginators, mail, and terminal programs."* vim is an editor, and its `:!` command runs a shell command. As `dba1`:

```sh
sudo /usr/bin/vim /var/lib/pgsql/data/postgresql.conf -E -s -c '!id > /tmp/escape' -c 'qa!'
```

`/tmp/escape` held `uid=0(root) gid=0(root) groups=0(root)`, and the file was owned by root. `-E -s` runs vim without a screen, so the test needs no terminal. In an interactive session, `:!bash` would start a root shell the same way.

The command line matched the rule because of the `*`. The manual's *Wildcards in command arguments*: *"Command line arguments are matched as a single, concatenated string. This mean a wildcard character such as `?` or `*` will match across word boundaries"*. Everything after `/var/lib/pgsql/` counts as part of one string, extra options included. `sudo -l /usr/bin/vim /var/lib/pgsql/data/x /etc/shadow`, which asks sudo whether a command is allowed without running it, confirmed that a second file is allowed too.

## NOEXEC isn't enough for an editor

The `NOEXEC` tag stops the program sudo runs from starting other programs. On Linux, sudo does this with *seccomp*, a kernel filter on system calls. With `NOPASSWD:NOEXEC:` on the vim rule, the same `!id` didn't run, and `/tmp/escape` wasn't created.

vim still ran as root, though, and the wildcard still allowed a second file. As `dba1`:

```sh
sudo /usr/bin/vim /var/lib/pgsql/data/postgresql.conf /etc/sudoers.d/zz-dba1 -E -s \
  -c "next" -c "call setline(1, 'dba1 ALL=(ALL) NOPASSWD: ALL')" -c "wq" -c "qa!"
```

That wrote a new root-owned sudoers file, and `sudo -n id` then printed `uid=0(root)`. The manual says as much: *"Restricting shell escapes is not a panacea. Programs running as root are still capable of many potentially hazardous operations (such as changing or overwriting files) that could lead to unintended privilege escalation. In the specific case of an editor, a safer approach is to give the user permission to run sudoedit"*.

## sudoedit instead

`sudoedit` copies the file to a temporary file owned by the user, runs the user's own editor on it as the user, and copies the result back as root. The rule names the file, without a wildcard:

```text
%postgres ALL=(root) NOPASSWD: sudoedit /var/lib/pgsql/data/postgresql.conf
```

To see who the editor ran as, `SUDO_EDITOR` pointed at a script that wrote `id -un` to a file and appended a line to the file it was given:
- **As `dba1`:** the script ran as `dba1`, not root, and `postgresql.conf` got the new line, still owned by `postgres` with mode 0600.
- **As `dba1`, with `/etc/shadow` as a second file:** the rule didn't match, sudo asked for a password, and `dba1`, who has none, was refused.
- **As `postgres`:** *"editing files in a writable directory is not permitted"*. sudoedit refuses files in a directory the user can write to, and `postgres` owns `/var/lib/pgsql/data`. That user can edit the file without sudo anyway.

When a command needs a variable argument, the manual suggests a *regular expression* (a text pattern) instead of a wildcard. `^` and `$` anchor it to the whole argument string. With `/usr/bin/tail ^/var/lib/pgsql/data/log/[^[:space:]]*$`, `dba1` could read one log file, and adding `/etc/shadow` made sudo ask for a password.

## Pagers: journalctl and systemctl status

A *pager* shows long output one screen at a time. `journalctl` and `systemctl status` start `less` when they write to a terminal, and less's `!` command runs a shell command. Run directly as root, `less` ran `!id`. Under `sudo journalctl -u postgresql.service`, the same keystrokes gave *"Command not available"*.

systemd 252's documentation of `$SYSTEMD_PAGERSECURE` explains why: *"If $SYSTEMD_PAGERSECURE is not set at all, secure mode is enabled if the effective UID is not the same as the owner of the login session"*. In secure mode, less disables commands that open files or start programs. sudo resets the environment by default, and Rocky Linux's `env_keep` list doesn't include `SYSTEMD_PAGERSECURE`, so a user can't switch it off through sudo. The same documentation still adds: *"It might be reasonable to completely disable the pager using --no-pager instead."* With `--no-pager` in the rule, users have to type it too, since sudo matches the arguments as written:

```text
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl --no-pager status postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/journalctl --no-pager -u postgresql.service
```

A pager such as `less` or `more`, given directly, has no such protection.

## A CI check before the rules are installed

visudo checks syntax, and every rule above passed it. So the check reads the rules themselves. `cvtsudoers`, which ships with sudo, converts a sudoers file to JSON. With `-e`, it also expands aliases, the named lists of commands a sudoers file can define:

```sh
cvtsudoers -e -f json 40-postgresql
```

Each rule becomes an entry in `User_Specs`, and each command an object such as `{ "command": "/usr/bin/vim /var/lib/pgsql/*" }`. A `NOEXEC` tag shows up as `{ "noexec": true }` in the rule's `Options`. *jq*, a command-line JSON processor, then applies a policy to every command. Commands that a rule forbids with `!` are skipped.

The policy needs to know which programs are dangerous through sudo. [GTFOBins](https://gtfobins.org/) is a curated list of them, with examples of each technique tagged by the context it works in: unprivileged, sudo, SUID or capabilities. Its site publishes the whole list as JSON at `https://gtfobins.org/api.json`. A short jq filter turns that into the functions each program has through sudo: `shell`, `file-read`, `file-write` and so on. It resolves GTFOBins' aliases and its *inherit* entries, where a program gets another one's techniques: vim inherits vi's shell, and `systemctl` and `journalctl` inherit `less`'s, through their pager.

GTFOBins' examples need arguments, though. `systemctl`'s shell comes from `systemctl link` and `enable` on a unit file the user wrote, or from `systemctl edit`, which `systemctl start postgresql.service` doesn't allow. So the arguments decide. The manual: *"If no command line arguments are specified, the user may run the command with any arguments they choose."* The policy reports:
- **`FAIL`** for `ALL`, and for a directory such as `/usr/local/bin/`, which allows every program in it;
- **`FAIL`** for shells, editors, pagers, mail and terminal programs, the manual's categories, whatever their arguments and whether or not the rule has `NOEXEC`;
- **`FAIL`** for a rule without arguments, for a program that GTFOBins lists with sudo functions;
- **`FAIL`** for a wildcard in the arguments, unless they're a `^…$` regular expression, naming GTFOBins' functions for the program when it has some;
- **`WARN`** for `journalctl`, or `systemctl status`, `show`, `cat` or `list-…`, without `--no-pager`.

`check-sudoers.sh` downloads GTFOBins' list, or reads a saved copy named by `GTFOBINS_API`, then runs visudo, cvtsudoers and the policy on each file. It exits 1 on any `FAIL`. On the first drop-in:

```text
WARN starts a pager without --no-pager: /usr/bin/systemctl status postgresql.service
WARN starts a pager without --no-pager: /usr/bin/journalctl -u postgresql.service
FAIL vim can start a shell or write any file as root, whatever its arguments: /usr/bin/vim /var/lib/pgsql/*
FAIL a wildcard in the arguments also matches extra arguments; GTFOBins lists sudo functions for vim: bind-shell, download, file-read, file-write, library-load, reverse-shell, shell, upload: /usr/bin/vim /var/lib/pgsql/*
```

With `sudoedit` and `--no-pager`, it printed `OK`. On a test file, it failed `%admins ALL=(ALL) ALL`, `NOEXEC: /usr/bin/less /var/log/messages`, `/usr/bin/psql *` behind a command alias, `/usr/bin/tar` and `/usr/bin/systemctl` without arguments, `/usr/local/bin/`, and `/usr/bin/find /var/log -name *.gz`. It passed `/usr/bin/systemctl start nginx.service`, `/usr/bin/python3 /opt/backup/run.py`, `/usr/bin/cat ""` (no arguments allowed) and `/usr/bin/tail ^/var/log/[^[:space:]]*$`.

The pipeline renders the files the deployment would install, then runs the check before anything reaches a host. In GitHub Actions, where `ubuntu-24.04` runners already have sudo, jq and curl:

```yaml
sudoers-policy:
  runs-on: ubuntu-24.04
  steps:
    - uses: actions/checkout@v7
    # … install Ansible and render the sudoers files into out/
    - name: Refuse rules that hand out a root shell
      run: ./check-sudoers.sh out/*
```

In GitLab CI, a job can run the check on the same distribution as the hosts, with the rendered files passed on from an earlier job:

```yaml
sudoers-policy:
  image: docker.io/rockylinux/rockylinux:9
  needs: [render-sudoers]
  before_script:
    - dnf -y install sudo jq
  script:
    - ./check-sudoers.sh out/*
```

The GitHub job runs in the example repository below. The GitLab job wasn't run on GitLab, but its commands ran in a Rocky Linux 9.8 container, with sudo 1.9.17p2 and jq 1.6, downloaded GTFOBins' list there, and gave the same findings.

The check is still a denylist: a program that neither list knows passes, and so does a fixed set of arguments that a GTFOBins technique fits. A stricter policy lists the commands each team may have, and fails everything else. The download also means the result can change when GTFOBins adds a program; a pipeline that must give the same answer every time can pin a saved `api.json` with `GTFOBINS_API`.

## The example repository

[abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/sudo-shell-escapes) holds the check: `check-sudoers.sh`, `sudoers-policy.jq`, `gtfobins-sudo.jq` and `interactive-commands.txt`. It renders the first drop-in and the safer one through the `linux-system-roles.sudo` role's template, then runs the check on both and on a file with one rule per case above. Its `sudoers-policy` job runs the check as a gate on the safer rules.

## Sources

- The sudoers manual for sudo 1.9.17p2, `docs/sudoers.mdoc.in` in [sudo-project/sudo](https://github.com/sudo-project/sudo) at tag `v1.9.17p2`: *Preventing shell escapes* (including `noexec` and sudoedit), *Wildcards in command arguments*, and the `Cmnd_List` description for commands without arguments.
- systemd 252, `man/common-variables.xml` in [systemd/systemd](https://github.com/systemd/systemd) at tag `v252`: `$SYSTEMD_PAGERSECURE`.
- [GTFOBins](https://gtfobins.org/): `api.json` as published on 2026-10-01, and [GTFOBins/GTFOBins.github.io](https://github.com/GTFOBins/GTFOBins.github.io) at commit `acd5246` for its format (`_data/contexts.yml`, `_gtfobins/`).
- Every result above came from a Rocky Linux 9.8 container (sudo 1.9.17p2, vim-enhanced 8.2.2637, systemd 252, less 590) on 2026-10-01, and from Ubuntu 24.04's sudo 1.9.15p5 and jq 1.7 for the check.
