# Forcing types: extra vars arrive as strings, and ansible-core 2.19 stopped guessing

Ninth entry in the Shaping data in Ansible series. *Extra vars* are variables given on the command line with `-e` (`--extra-vars`). They override every other variable, which makes them the usual way to flip a switch for one run. But `-e name=value` always gives a **string**, whatever the value looks like. A switch that reads `false` is the five-character string `"false"`, and the number `200` is `"200"`.

ansible-core 2.19 changed what happens next. A `when:` that gets a string instead of a boolean now fails instead of guessing. This entry shows the failure and the conversion filters that fix it: `bool`, `int`, `float` and `string`. Everything below ran with ansible-core 2.21.4.

## The play and its two switches

A maintenance play for the PostgreSQL server from [part 3](combine-recursive-list-merge-postgresql-quadlets.md) has two switches, with defaults in the play:

```yaml
vars:
  restart: true
  max_connections: 100
tasks:
  - name: Restart PostgreSQL, if restart
    ansible.builtin.service:
      name: postgresql
      state: restarted
    when: restart
```

Someone runs it with `-e restart=false -e max_connections=200` to apply a setting without a restart. The `type_debug` filter, which returns a value's type, showed:

| Extra vars | `restart` | `max_connections` |
|---|---|---|
| none (defaults) | `true` (bool) | `100` (int) |
| `-e restart=false -e max_connections=200` | `"false"` (str) | `"200"` (str) |
| `-e '{"restart": false, "max_connections": 200}'` | `false` (bool) | `200` (int) |

The last form is JSON, and JSON keeps its types: `false` without quotes is a boolean and `200` a number. `-e @vars.yml` reads a YAML file and keeps its types the same way.

## when: on a string is now an error

With `-e restart=false`, the task failed:

> Conditional result (True) was derived from value of type 'str' at "<CLI option '-e'>". Conditionals must have a boolean result.

The message says what happened, and where: the string `"false"`, like any non-empty string, counts as true. Before 2.19 it didn't stop there. ansible-core 2.18.19, run the same way, printed a warning, *"The result was interpreted as True. This feature will be removed in version 2.19"*, and **ran the restart task anyway**. The 2.19 porting guide calls this a *broken conditional*: *"truthy conditional evaluation often masks serious logic errors in playbooks"*, and 2.19 reports it as an error by default.

The porting guide also names the way back: the `ALLOW_BROKEN_CONDITIONALS` setting turns the error into a warning. With `ANSIBLE_ALLOW_BROKEN_CONDITIONALS=true` and the same `-e restart=false`, the play printed a deprecation warning, *"This feature will be removed from ansible-core version 2.23"*, and **the restart task ran**. That's the old behaviour, and exactly the bug the error exists to catch. Turning the setting on to silence the error brings the bug back.

The porting guide's other suggestion, the `is truthy` test, doesn't help a switch either: `'false' is truthy` was true.

## bool: the conversion a switch needs

```yaml
when: restart | bool
```

With `-e restart=false`, the task was skipped. With JSON extra vars or the play's default, it behaved the same, because `bool` passes real booleans through. ansible-core's `bool` filter, `to_bool` in `plugins/filter/core.py`, accepts these strings, in any case:

| Becomes `true` | Becomes `false` |
|---|---|
| `yes`, `on`, `true`, `1` | `no`, `off`, `false`, `0` |

`"On"` and `"OFF"` worked as well as `"on"` and `"off"`. **Anything else becomes `false`, with a warning.** A typo, `-e restart=fasle`, gave *"The `bool` filter coerced invalid value 'fasle' (str) to False. This feature will be removed from ansible-core version 2.23."* Here the typo skipped the restart, which is the safe side. For a switch where `false` is the dangerous side, check the value with an `assert` task: `that: restart in [true, false, 'true', 'false']`.

## int and float: numbers that arrive as strings

`max_connections > 150` with `-e max_connections=200` failed too: *"'>' not supported between instances of '_AnsibleTaggedStr' and 'int'"*. A string can't be compared with a number. `max_connections | int > 150` was true.

`int` doesn't fail on input it can't read; it returns 0:

| Expression | Result |
|---|---|
| `"200" \| int` | `200` |
| `" 200 " \| int` | `200` |
| `"4GB" \| int` | `0` |
| `"4GB" \| int(-1)` | `-1` |
| `"2.5" \| int` | `2` |
| `"2.5" \| float` | `2.5` |
| `"0x1F" \| int` | `0` |
| `"0x1F" \| int(0, 16)` | `31` |
| `200 \| string` | `"200"` |

- **`"4GB"` silently becomes 0.** A PostgreSQL size like `shared_buffers: 4GB` is a string that belongs in the configuration as is; it isn't a number to convert. Where a value must be a number, give `int` a default that can't be mistaken for a real value, `int(-1)`, and `assert` on it.
- **`"2.5" | int` truncates to 2.** Use `float` when fractions matter.
- **Hexadecimal needs the base**, as the second argument; the first is the default.

## Which one

- **A switch from the command line:** `when: switch | bool`, never `when: switch`, and never `ALLOW_BROKEN_CONDITIONALS` as the fix.
- **Numbers from the command line:** `| int` or `| float` before comparing, with a default like `int(-1)` when bad input must not pass as 0.
- **Keep the types:** pass extra vars as JSON, `-e '{"restart": false}'`, or from a file with `-e @vars.yml`.
- **To see what you got:** `type_debug`.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/09-forcing-types), runs all of the above on the local machine, changing nothing outside its `out/` directory. `run.sh` runs `switches.yml` with its defaults, with `key=value` extra vars, with JSON, with a typo and with `ALLOW_BROKEN_CONDITIONALS`, and records what each conditional and comparison did; `convert.yml` records the conversions in the tables above. Its CI runs both on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`to_bool` and its accepted values, `int` via Jinja), and the error and deprecation messages quoted above.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `porting_guides/porting_guide_core_2.19.rst`, *Broken Conditionals*; `playbook_guide/playbooks_filters.rst`, *Forcing the data type*; `playbook_guide/playbooks_variables.rst`, on extra vars.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine, except the 2.18 comparison, run with ansible-core 2.18.19. No PostgreSQL server was restarted: the example's task only records that it ran.
