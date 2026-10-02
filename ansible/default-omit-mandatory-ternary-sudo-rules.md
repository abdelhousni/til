# default, default(omit), mandatory and ternary: sudo rules that don't set every field

Eighth entry in the Shaping data in Ansible series. Data from people is incomplete: a field left out, left blank, or set to "not decided". In YAML these are three different values:
- **undefined**: the key isn't there at all;
- **empty**: the key is there with `''` or `[]`;
- **null**: the key is there with nothing after the colon, which YAML reads as null (`None` in Ansible).

Four filters deal with them: `default`, `default(omit)`, `mandatory` and `ternary`. The example is part 1's sudo rules for the PostgreSQL service, rendered by the `linux-system-roles.sudo` role, where not every rule sets every option. Everything below ran with ansible-core 2.21.4 and the sudo role 1.5.0, with each file checked by `visudo`.

## The rules and the role

[Part 1](readable-sudoers-with-dict-kv.md) explains sudoers rules and the sudo system role. The role takes `user_specifications`, one dict per rule, and its template, `templates/sudoers.j2`, writes one line per dict:
- **`users`, `hosts` and `commands`** are required. A rule missing one of them, or with an empty list, is **skipped without an error**.
- **The other keys**, `operators` (the user to run as) and `tags` (such as `NOPASSWD`), are optional. The template writes each one only if it's defined *and* has a length above zero.

The rules, as they might come from a form:

```yaml
postgres_sudo_rules:
  - name: restart
    commands: [/usr/bin/systemctl restart postgresql.service]
    nopasswd: true
    runas: root
  - name: status
    commands: [/usr/bin/systemctl status postgresql.service]
    nopasswd: false
  - name: journal
    commands: [/usr/bin/journalctl -u postgresql.service]
    runas:              # left empty: null
  - name: reload
    commands: [/usr/bin/systemctl reload postgresql.service]
    group: ""           # left blank
    nopasswd:           # null: not decided
```

`status` has no `runas`, `journal`'s is null, `reload` has a blank group and an undecided `nopasswd`, and only `restart` sets everything.

## default(omit) only works on module arguments

`omit` is a special value that makes Ansible leave an argument out of a task, as if it had never been written. A natural first try is to use it for `status`'s missing `runas`:

```yaml
user_specifications:
  - "{{ base | combine({'commands': rule.commands, 'operators': rule.runas | default(omit)}) }}"
```

The role's template failed: *"object of type '_OmitType' has no len()"*. Inside a dict that a template reads, the omit value isn't removed; it stays there as a special object. The docs, *Making variables optional*, describe `omit` for module variables only, and that's all it does. With `journal`'s null `runas` the result was the same kind of error: *"object of type 'NoneType' has no len()"*. `is defined` is true for null, so the template goes on to measure it.

Where `omit` does work is on a task's own arguments. The same broken rule, a command without its full path, which sudo refuses, rendered twice with `validate: "{{ item.validate | default(omit) }}"`:
- **with `validate: visudo -cf %s`**, the task failed and no file was written;
- **without it**, `validate` was left out, and the broken file was written.

For this role, the answer to an optional key is an **empty list**, which its template skips: `'operators': [rule.runas] if rule.runas | default(none) else []`. `default(none)` turns a missing `runas` into null first, so both cases end up as `[]`.

## mandatory: a forgotten field that would vanish silently

A rule whose `commands` were forgotten didn't fail anywhere. The role's template skipped it, `visudo` accepted the empty file, and the file had no rules at all. Nobody would notice until the service account couldn't restart PostgreSQL.

`mandatory` fails the task when a value is undefined, with a message of your choice:

```yaml
'commands': rule.commands | mandatory('rule ' ~ rule.name ~ ' has no commands')
```

That gave *"rule stop has no commands"*. It only checks that the value is defined: `[] | mandatory('empty')` returned `[]` without complaint. Where an empty list matters too, add an `assert` task on its length.

## default and its second argument

`default(value)` replaces an undefined value. **It leaves `''` and null alone.** `default(value, true)` also replaces anything *falsy*, any value that counts as false: `''`, null, `[]`, `0` and `false` itself.

| Expression | Result |
|---|---|
| `'' \| default('%postgres')` | `''` |
| `'' \| default('%postgres', true)` | `'%postgres'` |
| `null \| default('%postgres')` | null |
| `null \| default('%postgres', true)` | `'%postgres'` |
| `false \| default(true, true)` | `true` |
| `0 \| default(5, true)` | `5` |

`reload`'s blank group needs the second argument: `users: [rule.group | default('%postgres', true)]`. **Never use it on a boolean or a number.** `nopasswd: false | default(true, true)` turns an explicit "no" into "yes".

## ternary and its third value

`ternary(a, b)` returns `a` when its input is true and `b` otherwise. A third value, `ternary(a, b, c)`, is used when the input is null:

| Expression | Result |
|---|---|
| `[true, false, null] \| map('ternary', ['NOPASSWD'], [], ['PASSWD'])` | `[['NOPASSWD'], [], ['PASSWD']]` |
| `[true, false, null] \| map('ternary', ['NOPASSWD'], [])` | `[['NOPASSWD'], [], []]` |

Without the third value, "not decided" is treated as false. With it, the rule can say so: `PASSWD` is sudo's explicit "ask for a password", which is also its default. `nopasswd | default(none) | ternary(['NOPASSWD'], [], ['PASSWD'])` gives a missing `nopasswd` the same treatment as a null one.

## The result

Built with all four, the role's template wrote, and `visudo` accepted:

```
%postgres ALL=(root) NOPASSWD: /usr/bin/systemctl restart postgresql.service
%postgres ALL= /usr/bin/systemctl status postgresql.service
%postgres ALL= PASSWD: /usr/bin/journalctl -u postgresql.service
%postgres ALL= PASSWD: /usr/bin/systemctl reload postgresql.service
```

## Which one

- **A module argument you sometimes don't want:** `default(omit)`.
- **An optional key in data a template reads:** an empty value the template skips, here `[]`, not `omit` and not null.
- **A field whose absence would silently drop something:** `mandatory('a message naming the item')`.
- **A blank string that should fall back:** `default(value, true)`, never on booleans or numbers.
- **true, false and "not decided" all mean something:** `ternary(a, b, c)`.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/08-default-omit-mandatory-ternary), runs all of the above on the local machine, changing nothing outside its `out/` directory. `render.yml` builds the rules from `vars/rules.yml`, renders them with the sudo role's template, validated by `visudo`, and records each failure and result in `out/render.txt`. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`mandatory`, `ternary`), and Jinja 3.1's `default` filter, whose second argument tests the value's truth rather than whether it's defined.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Providing default values*, *Making variables optional*, *Defining mandatory values* and *Defining different values for true/false/null (ternary)*.
- [linux-system-roles.sudo](https://github.com/linux-system-roles/sudo) 1.5.0: `README.md` (`user_specifications`) and `templates/sudoers.j2`.
- `sudoers(5)`, for `PASSWD` and `NOPASSWD`; files checked with `visudo -cf` from Ubuntu 24.04's sudo.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine. Nothing was installed in `/etc/sudoers.d`.
