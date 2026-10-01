# One sudoers line per command with community.general.dict_kv: building a list of dicts from a list of values

First entry in the Shaping data in Ansible series. Ansible variables are YAML data: strings, lists and dictionaries (*dicts*, key–value mappings). *Filters* are the functions after a `|` in a `{{ }}` expression, and they turn one shape of data into another. This entry uses one of them, `community.general.dict_kv`, to make a generated sudoers file readable without repeating the same YAML nine times.

`community.general` is a *collection*, a package of extra modules and filters ([this entry](block-rescue-always-error-handling.md) explains collections). Everything below ran with ansible-core 2.21.4, community.general 13.4.0 and the `linux-system-roles.sudo` role 1.5.0, against Rocky Linux 9.8 with sudo 1.9.17p2.

## What the sudo role writes

`linux-system-roles.sudo` is one of the Linux System Roles, the roles Red Hat and Fedora maintain for system settings; [this entry](podman-quadlet-caddy-adminer-php-linux-system-roles.md) uses two others. It writes *sudoers* files, which say who may run which commands as which user. Here it writes a *drop-in*, a separate file under `/etc/sudoers.d/` that sudo reads with the main `/etc/sudoers`.

Each item in a file's `user_specifications` becomes one sudoers line. The role's template joins that item's lists; simplified, leaving out the optional SELinux and Solaris fields:

```jinja
{{ spec.users | join(", ") }} {{ spec.hosts | join(", ") }}=({{ spec.operators | join(", ") }}) {{ spec.tags | join(":") }}: {{ spec.commands | join(", ") }}
```

So one item with nine `commands` gives one line:

```text
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl start postgresql.service, /usr/bin/systemctl stop postgresql.service, /usr/bin/systemctl restart postgresql.service, … /usr/bin/vim /var/lib/pgsql/*
```

That line was 434 characters long. Nine items with one command each give nine lines that are easy to read and to diff, but the YAML then repeats `users`, `hosts`, `operators` and `tags` nine times.

## The same nine items, with less YAML

**With a YAML anchor.** `&name` marks a value, `*name` refers back to it, and the *merge key* `<<` copies a referenced dict into the current one:

```yaml
postgres_sudo_spec_base: &postgres_sudo_spec_base
  users: ["%postgres"]
  hosts: ["ALL"]
  operators: ["root"]
  tags: ["NOPASSWD"]

sudo_sudoers_files:
  - path: /etc/sudoers.d/40-postgresql
    user_specifications:
      - <<: *postgres_sudo_spec_base
        commands: ["/usr/bin/systemctl start postgresql.service"]
      - <<: *postgres_sudo_spec_base
        commands: ["/usr/bin/systemctl stop postgresql.service"]
      # … seven more
```

**With `dict_kv`.** The commands become a plain list, and filters build the items:

```yaml
postgres_sudo_spec_base:
  users: ["%postgres"]
  hosts: ["ALL"]
  operators: ["root"]
  tags: ["NOPASSWD"]

postgres_sudo_commands:
  - ["/usr/bin/systemctl start postgresql.service"]
  - ["/usr/bin/systemctl stop postgresql.service"]
  - ["/usr/bin/systemctl restart postgresql.service"]
  - ["/usr/bin/systemctl try-restart postgresql.service"]
  - ["/usr/bin/systemctl status postgresql.service"]
  - ["/usr/bin/systemctl reload postgresql.service"]
  - ["/usr/bin/systemctl force-reload postgresql.service"]
  - ["/usr/bin/journalctl -u postgresql.service"]
  - ["/usr/bin/vim /var/lib/pgsql/*"]

sudo_sudoers_files:
  - path: /etc/sudoers.d/40-postgresql
    user_specifications: >-
      {{ postgres_sudo_commands
         | map('community.general.dict_kv', 'commands')
         | map('combine', postgres_sudo_spec_base)
         | list }}
```

Run through the role, both versions wrote byte-identical files:

```text
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl start postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl stop postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl restart postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl try-restart postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl status postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl reload postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl force-reload postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/journalctl -u postgresql.service
%postgres ALL=(root) NOPASSWD: /usr/bin/vim /var/lib/pgsql/*
```

## The data types, step by step

`type_debug` is an ansible-core filter that prints the Python type of a value. Applied at each step of the chain:

| Expression | `type_debug` | Value of the first item |
|---|---|---|
| `postgres_sudo_commands` | `list`, of `list` | `["/usr/bin/systemctl start postgresql.service"]` |
| `… \| map('community.general.dict_kv', 'commands')` | `list`, of `dict` | `{"commands": ["/usr/bin/systemctl start …"]}` |
| `… \| map('combine', postgres_sudo_spec_base)` | `list`, of `dict` | `{"commands": […], "hosts": ["ALL"], "operators": ["root"], "tags": ["NOPASSWD"], "users": ["%postgres"]}` |

- **`dict_kv(key)`** turns the value in front of it into a one-key dict: `value | dict_kv('key')` gives `{"key": value}`. Its own documentation shows exactly this pattern: `myservers | map('dict_kv', 'server') | map('combine', common_config)`.
- **`map(filter, argument)`** applies a filter to every item of a list, so each one-element list becomes its own dict.
- **`combine`**, from ansible-core, merges dicts. When both have the same key, the one on the right wins. Here the keys never overlap, so the order doesn't matter.
- **`| list`** turns `map`'s result into a list. In ansible-core 2.21, `map` already reported `list`, and the role wrote the same file without it. It costs nothing to keep.

## Why each command is a one-element list

The template runs `commands | join(", ")`. On a list, `join` joins the items. On a string, it joins the characters. With the commands as plain strings, `- "/usr/bin/systemctl start postgresql.service"`, each item's `commands` became a string, and the line rendered as:

```text
%postgres ALL=(root) NOPASSWD: /, u, s, r, /, b, i, n, /, s, y, s, t, e, m, c, t, l,  , s, t, a, r, t, …
```

The role validates every file with `visudo -cf` before installing it. visudo refused this one, *"expected a fully-qualified path name"*, and the task failed without touching the server. So keep the brackets: `["…"]` makes each `commands` a list of one string.

## Before using these commands as they are

Two of these lines give more than they appear to. The sudoers manual's section *Preventing shell escapes* warns that *"Common programs that permit shell escapes include shells (obviously), editors, paginators, mail, and terminal programs"*. A shell started from them runs as root.
- **`/usr/bin/vim /var/lib/pgsql/*`.** vim can start a shell. And per the manual's *Wildcards in command arguments*, *"a wildcard character such as `?` or `*` will match across word boundaries"*. With this rule, `sudo -l` confirmed that `vim /var/lib/pgsql/data/x /etc/shadow` is allowed. The manual's answer for editing is `sudoedit`, which edits a copy as the user and writes it back: `["sudoedit /var/lib/pgsql/data/postgresql.conf"]`.
- **`journalctl` and `systemctl status`** show their output through a pager on a terminal, which is the manual's "paginators". Listing them with `--no-pager`, for example `["/usr/bin/journalctl --no-pager -u postgresql.service"]`, avoids it. Users then have to type the command with `--no-pager`, since sudo matches the arguments as written.

With those three changes, visudo accepted the file, and `sudo -l` listed the new rules.

## Anchor or `dict_kv`?

- **Lines of YAML:** the anchor version needs two lines per command, `dict_kv` needs one.
- **Who can read it:** anchors are plain YAML. The filter chain asks the reader to know `map`, `dict_kv` and `combine`.
- **Where the base can live:** an anchor only works inside the YAML file that defines it. `postgres_sudo_spec_base` is an ordinary variable, so with `dict_kv` it can sit in `group_vars/all.yml` while each group adds its own commands.
- **What it needs:** `dict_kv` comes from community.general; anchors need nothing.

## Sources

- `linux-system-roles.sudo` 1.5.0 (commit `035e774`), cloned from [linux-system-roles/sudo](https://github.com/linux-system-roles/sudo): `templates/sudoers.j2` for the line format and the `join` calls, `tasks/main.yml` for `validate: visudo -cf %s`.
- community.general 13.4.0, `plugins/filter/dict_kv.py`: the filter's documentation and the `map('dict_kv', …) | map('combine', …)` example.
- The sudoers manual for sudo 1.9.17p2, `docs/sudoers.mdoc.in` in [sudo-project/sudo](https://github.com/sudo-project/sudo) at tag `v1.9.17p2`: *Preventing shell escapes* and *Wildcards in command arguments*.
- Every rendered line, error and `sudo -l` result above came from running the role against a Rocky Linux 9.8 container. `vim`, `systemctl` and `journalctl` were empty stand-ins there, since `sudo -l` checks only commands that exist.
