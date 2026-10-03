# Text on lists: building a systemd ExecStart line with regex_replace, join and replace

Sixteenth entry in the Shaping data in Ansible series. [Part 7](strings-into-structures-df-findmnt-from-json.md) turned text into data. This one goes the other way: it turns a list of options into one line of text, the command a systemd service runs. *systemd* starts and supervises services on most Linux systems; each service is described by a *unit file*, and its `ExecStart=` line is the command to run. Building that line from variables takes three things: string filters applied to every item of a list, `join` to glue them, and escaping, because systemd reads `ExecStart=` with rules of its own. Everything below ran with ansible-core 2.21.4, and every systemd result came from GitHub's Ubuntu 24.04 runners, which ship systemd 255, in the example's CI.

## The unit and its options

The unit backs up a PostgreSQL database with `pg_dump`. It's a *template unit*, `pg-backup@.service`: starting `pg-backup@app.service` runs it with `app` as its *instance*, which the unit reads as `%i`. `%i` is a *specifier*, one of the `%` sequences systemd replaces when it loads the unit.

The options, in `vars/backup.yml`:

```yaml
pg_backup_options:          # options that take a value
  format: custom
  compress: 6
pg_backup_flags:            # options without one
  - no_owner
pg_backup_exclude_tables:   # tables left out of the dump
  - audit log
  - tmp$work
  - cache_50%
  - report_%n
  - tmp_${work}
```

The table names are all legal in PostgreSQL when quoted, and each has a character systemd treats specially: a space, a `$`, a `%`.

## A filter on every item: map('regex_replace')

`map` applies a filter to each item of a list ([part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md)). With `regex_replace`, which replaces what a regular expression matches, it turns names into options:

```yaml
option_args: "{{ pg_backup_options | items | map('join', '=') | map('regex_replace', '^', '--') | list }}"
flag_args: "{{ pg_backup_flags | map('regex_replace', '_', '-') | map('regex_replace', '^', '--') | list }}"
table_args: "{{ pg_backup_exclude_tables | map('regex_replace', '^', '--exclude-table=') | list }}"
```

- `items` turns the dict into `[key, value]` pairs, and `map('join', '=')` makes each one `format=custom`.
- `regex_replace('^', '--')` adds a prefix: `^` matches the start of the string, an empty match, so the replacement is inserted there.
- `regex_replace('_', '-')` turns `no_owner` into `no-owner`, `pg_dump`'s spelling.

That gave `['--format=custom', '--compress=6']`, `['--no-owner']`, and one `--exclude-table=…` per table.

### format can't be mapped

`format` looks like the natural way to add a prefix: `'--exclude-table=%s' | format('audit log')` gave `--exclude-table=audit log`, and `'--exclude-table=' ~ 'audit log'` the same with `~`, Jinja's concatenation operator. But neither can be applied to every item with `map`. `map` passes each item as the filter's *input*, and for `format` the input is the format string. `pg_backup_exclude_tables | map('format')` treated each table name as a format, and failed on the third: *"incomplete format"*, from the `%` in `cache_50%`. `regex_replace('^', prefix)` is the way to add a prefix to every item.

## join, and what systemd does with the line

`join(' ')` glues the list into one string:

```
ExecStart=/usr/bin/pg_dump --format=custom --compress=6 --no-owner --exclude-table=audit log
  --exclude-table=tmp$work --exclude-table=cache_50% --exclude-table=report_%n
  --exclude-table=tmp_${work} --file=/srv/backups/%i.dump %i
```

(one line in the unit file). `systemd-analyze verify`, which checks unit files, accepted it. To see what the program actually receives, the example's CI starts the unit with `ExecStart=` pointing at a small script that prints its arguments. For `pg-backup-naive@app.service`:

| Table name | Argument the program received |
|---|---|
| `audit log` | `--exclude-table=audit`, then `log`, as a separate argument |
| `tmp$work` | `--exclude-table=tmp$work` |
| `cache_50%` | `--exclude-table=cache_50%` |
| `report_%n` | `--exclude-table=report_pg-backup-naive@app.service` |
| `tmp_${work}` | `--exclude-table=tmp_` |

And `--file=/srv/backups/%i.dump %i` arrived as `--file=/srv/backups/app.dump` and `app`, as intended. The `systemd.service` manual, *Command lines*, explains each row:
- **Whitespace separates arguments**, unless quoted (the rules are in `systemd.syntax`). `pg_dump` would have excluded a table named `audit`, which doesn't exist, and received `log` as an extra argument.
- **`$FOO` is replaced only *"as a separate word"***, so `tmp$work` passed through. **`${FOO}` is replaced *"as part of a word, or as a word of its own"***, and *"variables whose value is not known at expansion time are treated as empty strings"*: `tmp_${work}` lost its end.
- **Specifiers are replaced anywhere:** `%n` is the *"full unit name"*. `% ` followed by a space isn't a specifier, and systemd 255 left `cache_50%` alone, although `systemd.unit` says specifiers *"must be known and resolvable for the setting to be valid"*. Don't count on it.

## Escaping the data for systemd

The same manuals give the escapes: *"to pass a literal dollar sign, use `$$`"*, and `%%` for *"a single percent sign"*. Double quotes keep a space inside one argument. Applied to the table arguments only:

```yaml
table_args_escaped: >-
  {{ table_args | map('replace', '%', '%%') | map('replace', '$', '$$')
  | map('regex_replace', '^(.*)$', '"\1"') | list }}
```

`replace` replaces a fixed string, with no regular expression. `regex_replace('^(.*)$', '"\1"')` wraps each argument in quotes: `(.*)` captures the whole argument, and `\1` puts it back. The escaped line, `… "--exclude-table=audit log" "--exclude-table=tmp$$work" "--exclude-table=cache_50%%" "--exclude-table=report_%%n" "--exclude-table=tmp_$${work}" --file=/srv/backups/%i.dump %i`, delivered all five names exactly as written.

**Escape the data, not the line.** `--file=/srv/backups/%i.dump %i` is written by hand and must keep its `%i`; escaping the whole line would turn it into `%%i`, a literal `%i`. That's why the example escapes `table_args` before joining, not the result of `join`. These escapes cover the five names here; a name containing a `"` or a `\` would need those escaped too.

## How many backslashes: count for YAML, not for Jinja

The `\1` above has one backslash, because the expression sits in a YAML block scalar (`>-`), where YAML changes nothing. Ansible then passes the Jinja string through with its backslashes unchanged; plain Jinja would have turned `'\\1'` into `\1`, but in Ansible it reaches the regular expression as `\\1`, a literal backslash followed by `1`. Tested on `'x y' | regex_replace('(x)', '[…1]')`, with ansible-core 2.21.4 and 2.18.19 alike:

| YAML style | Written | Result |
|---|---|---|
| block scalar (`>-`) or single quotes | `\1` | `[x] y` |
| double quotes | `\\1` | `[x] y` |
| block scalar or single quotes | `\\1` | `[\1] y`, a literal `\1` |
| double quotes | `\1` | a YAML error: `\1` isn't a valid escape, and the file doesn't load |

Only YAML's quoting counts: in double quotes, write each backslash twice; anywhere else, once. The Ansible docs' examples, *Searching strings with regular expressions*, are in double quotes, which is why they show `\\1`.

## Which one

- **A filter on every item of a list:** `map('regex_replace', …)` or `map('replace', …)`; to add a prefix, `regex_replace('^', prefix)`.
- **One string from one value:** `format` or `~`, but never `map('format')`: the item becomes the format string.
- **Many arguments into one line:** `join(' ')`, after escaping each argument for whatever reads the line.
- **An ExecStart= line from data:** quote each argument, double `%` and `$` in the data, and leave hand-written specifiers like `%i` alone. Check the result by running the unit, not with `systemd-analyze verify`.
- **Backslashes in a regex:** one in a block scalar or single quotes, two in double quotes.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/16-text-on-lists), builds both lines on the local machine, writing the two units to its `out/` directory, and its CI compares the output with the expected one. A separate CI job, `ci/systemd-check.sh`, installs both units on a runner with systemd, starts them for the instance `app`, and compares the arguments the program received with `ci/expected-systemd.txt`.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`regex_replace` is Python's `re.subn`), and Jinja 3.1.6's `items`, `join`, `replace` and `format` filters.
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Manipulating strings* and *Searching strings with regular expressions*.
- systemd 255 manuals, from [systemd/systemd](https://github.com/systemd/systemd/tree/v255/man): `systemd.service.xml` (*Command lines*: variables, `$$`), `systemd.unit.xml` and `standard-specifiers.xml` (*Specifiers*: `%i`, `%n`, `%%`).
- The systemd results came from GitHub's `ubuntu-24.04` runners (Ubuntu 24.04 ships systemd 255), on 2026-10-03; the Ansible results from ansible-core 2.21.4 on the local machine, the backslash table also from ansible-core 2.18.19. No PostgreSQL server was backed up.
