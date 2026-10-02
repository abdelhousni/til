# Writing data out: a Caddy JSON configuration with to_nice_json, sort_keys and indent

Tenth entry in the Shaping data in Ansible series. The earlier parts shaped data inside Ansible. This one writes it out to a file another program reads: part 3's Caddy site, as Caddy's own JSON configuration. Ansible has two filters for each format:
- **`to_json`** and **`to_nice_json`** turn a variable into JSON text;
- **`to_yaml`** and **`to_nice_yaml`** turn it into YAML.

The question is not only whether the file is valid, but whether it stays the same from one run to the next. Ansible compares the new file with the one already there and reports the task as *changed* when they differ ([part 6](set-operations-union-difference-proxmox-drift.md) shows why a needless change costs something). Everything below ran with ansible-core 2.21.4, and every JSON file was checked with `caddy validate` from Caddy 2.10.2.

## The site, as Caddy's JSON

Caddy is a web server that gets HTTPS certificates by itself ([this entry](../podman/caddy-php-fpm-automatic-https.md) sets it up with PHP-FPM in Podman). It's usually configured with a *Caddyfile*, its short text format, but its native configuration is JSON, and a Caddyfile is converted to JSON before Caddy uses it. Writing the JSON directly means Ansible can build it from variables like any other data.

Part 3's stack serves `example.com` from `/srv`, with PHP files handed to the `php` container. In the example, the server is two layers, merged with `combine` ([part 3](combine-recursive-list-merge-postgresql-quadlets.md) explains it): what every server has, and what this site adds:

```yaml
caddy_server_base:
  listen: [":443"]

caddy_server_site:
  logs:
    default_logger_name: app
  routes:
    - match: [{host: [example.com]}]
      handle:
        - handler: headers
          response:
            set:
              Content-Security-Policy: ["{{ caddy_csp }}"]
              X-Served-By: [Café server]
        - handler: encode
          encodings: {gzip: {}}
        - handler: subroute
          # PHP files to php:9000 over FastCGI, everything else from /srv
```

`caddy_csp` is a *Content-Security-Policy*, a response header that tells browsers where a page may load scripts, styles and images from. It's long, and it's full of single quotes: `default-src 'self'; script-src 'self'; …`. `X-Served-By` has an accented letter. Both matter below.

The whole configuration is `{'apps': {'http': {'servers': {'app': caddy_server}}}}`, and the template that writes it is one line:

```jinja
{{ caddy_config | to_nice_json }}
```

## Without a filter, it isn't JSON

A template with just `{{ caddy_config }}` wrote:

```
{'apps': {'http': {'servers': {'app': {'
```

That's how Python prints a dict, with single quotes, and not JSON. `caddy validate` refused it: *"config is not valid JSON: invalid character '\'' looking for beginning of object key string"*. The same dict given to `ansible.builtin.copy` as `content:` did come out as JSON, because `copy` turns a dict into JSON itself, but on one line. Don't rely on either: name the format with a filter.

## Every filter on the same data

| Output | Valid JSON | Lines |
|---|---|---|
| `to_json` | yes | 1 |
| `to_nice_json` | yes | 87 |
| `tojson` | yes | 1 |
| `to_nice_yaml` | no, it's YAML | 42 |
| no filter, `template` | no | 1 |

- **`to_json`** is correct but one line. A one-line file makes every change a change to the whole file, so the diff says nothing useful.
- **`to_nice_json`** puts each key on its own line, indented by 4 spaces, **with the keys sorted**. Its source, `plugins/filter/core.py`, passes `sort_keys=True` to Python's `json.dumps`; `to_json` doesn't sort.
- **`tojson`**, without the underscore, is Jinja's own filter, not Ansible's. It also sorts, but it escapes characters that matter in HTML, for safe use inside a web page: every `'` in the policy became `'`, as in `"default-src 'self';`. Caddy reads that back correctly, but nobody reading the file will. Use Ansible's `to_json` or `to_nice_json`.

### ensure_ascii and the accented letter

`to_nice_json` wrote `X-Served-By` as `"Café server"`. JSON allows any character to be written as `\u` and its code in hexadecimal, and `ensure_ascii`, which defaults to true, does that for every character outside ASCII, the basic English set. The value is the same; only the file is harder to read. `to_nice_json(ensure_ascii=false)` wrote `"Café server"`, and Caddy accepted both.

## What sort_keys does to the diff

`--diff` makes Ansible print, for each file it changes, the lines removed and added, the way `diff` does. `run.sh` in the example writes `caddy.json` seven times in a row, changing one setting at a time:

| Run | Caddy JSON | Diff lines |
|---|---|---|
| first run | changed | 87 |
| again, nothing changed | ok | 0 |
| layers merged the other way, `sort_keys=true` | ok | 0 |
| back to the first order, `sort_keys=false` | changed | 36 |
| layers merged the other way, `sort_keys=false` | changed | 6 |
| back to `sort_keys=true` | changed | 42 |
| `indent=2` | changed | 156 |

"The other way" is `caddy_server_site | combine(caddy_server_base)` instead of `caddy_server_base | combine(caddy_server_site)`. With no key in both layers, the merged dict holds the same keys and values either way, only in a different order. A Python dict remembers the order in which its keys were added, and `json.dumps` follows it unless told to sort. Without sorting, the swap moved `listen` from the top of the server to the bottom:

```diff
                 "app": {
-                    "listen": [
-                        ":443"
-                    ],
                     "logs": {
…
+                    ],
+                    "listen": [
+                        ":443"
                     ]
```

Caddy reads the same configuration from both files, since the order of keys in a JSON object carries no meaning. But the file changed, so Ansible reported *changed*, and a handler that reloads Caddy would have run. With `to_nice_json`'s default `sort_keys=true`, the same swap changed nothing. Key order depends on how the dict was built: the order of a `combine`, of a loop that adds keys, of variable files. Sorting takes all of that out of the file.

Two limits:
- **Sorting only applies to keys, never to lists.** A list keeps its order, and in Caddy's configuration that's what matters: routes and handlers run in list order.
- **Sorted isn't always the reading order.** Each route's `handle` now comes before its `match`, the opposite of how one would explain it. That's the price of a stable file.

`indent` has no effect on the configuration either, but changing it rewrites every indented line: 156 lines of diff for one setting. Pick a value once and leave it. The default, 4, is fine.

## to_nice_yaml and long lines

For a program that reads YAML, `to_nice_yaml` is the equivalent, with 4-space indentation and sorted keys too (PyYAML, the library behind it, sorts by default). One difference: **PyYAML breaks lines longer than 80 characters** at a space. The policy came out on three lines:

```yaml
Content-Security-Policy:
- default-src 'self'; script-src 'self'; style-src
    'self' 'unsafe-inline'; img-src 'self' data:;
    frame-ancestors 'none'
```

It's still the same string: a YAML plain value continued on the next lines is joined back with single spaces, and reading the file back with `from_yaml` gave data equal to the original. But when the value changes, its line breaks can move, and the diff shows every line they touch. The docs, *Formatting data: YAML and JSON*, give the fix: `to_nice_yaml(width=1000)`, a fixed number, since the filter can't take Python's `float("inf")`. With it, the policy stayed on one line.

What neither format keeps is comments. A file written from data has only what the data has. Where a configuration needs comments for the people who edit it by hand, a template that writes each line itself, with a loop, is the better tool. Where nobody edits the file, a single filter is shorter and can't produce broken syntax.

## Which one

- **A JSON configuration file:** `to_nice_json`, keeping its default `sort_keys=true` and indent.
- **Non-ASCII text that people read:** add `ensure_ascii=false`.
- **A YAML file with long values:** `to_nice_yaml(width=1000)`.
- **Never** a bare `{{ dict }}`, and never Jinja's `tojson` for a file.
- **Comments, or an order chosen for readers:** a template that writes the lines.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/10-writing-data-out), runs all of the above on the local machine, changing nothing outside its `out/` directory. `write.yml` merges the two layers and writes `out/caddy.json`, and `run.sh` runs it with each setting in the table above and reports whether the file changed and how many lines the diff had. `variants.yml` writes the same configuration with every filter, and `run.sh` checks which outputs are JSON. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`to_json`, `to_nice_json` with `indent=4` and `sort_keys=True`, `to_yaml`, `to_nice_yaml` with `indent=4`) and `plugins/filter/to_nice_json.yml` (`ensure_ascii` and `sort_keys` default to true).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Formatting data: YAML and JSON*.
- Jinja 3.1.6: the built-in `tojson` filter. PyYAML 6.0.3: `yaml.dump`, its 80-character default width and sorted keys.
- Python documentation: [`json.dumps`](https://docs.python.org/3/library/json.html#json.dumps).
- Caddy documentation: [JSON config structure](https://caddyserver.com/docs/json/). Files checked with `caddy validate` from Caddy 2.10.2.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine. No Caddy server was started.
