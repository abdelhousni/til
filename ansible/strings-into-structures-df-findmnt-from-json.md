# Strings into structures: df with split and regex_findall, findmnt with from_json

Seventh entry in the Shaping data in Ansible series. When a task runs a command, `register:` keeps its output in `stdout`, one string, and `stdout_lines`, the same split into lines. Picking values out of it by position, `stdout_lines[2].split()[3]`, breaks as soon as the output changes shape. This entry turns command output into lists and dicts instead, with four filters:
- **`split`** cuts a string into a list;
- **`regex_findall`** returns every match of a regular expression, a text pattern ([part 2](lists-and-dicts-dict2items-items2dict-zip.md) introduces them);
- **`from_json`** and **`from_yaml`** parse JSON or YAML text into Ansible data.

The example is free disk space, read from `df` and from `findmnt`, and compared with the mount facts that [part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md) used. Everything below ran with ansible-core 2.21.4.

## The data

The machine had a 32 MiB ext4 file system, loop-mounted at a path with a space in it, `/srv/app data`. A *loop mount* uses a file as if it were a disk. `df -P -B1` prints one line per file system, in bytes; `-P` asks for the POSIX format, one line per file system even when a device name is long:

```
Filesystem                  1-blocks        Used   Available Capacity Mounted on
/dev/vda                270553174016 12732731392 28401344512      31% /
/dev/loop0                  27234304       24576    24866816       1% /srv/app data
```

## split, and the space in the path

`split` with no argument cuts on runs of whitespace, so the columns' padding disappears:

| Expression on the loop0 line | Result |
|---|---|
| `split \| last` | `data` |
| `(… \| split)[5]` | `/srv/app` |
| `(… \| split(none, 5))[5]` | `/srv/app data` |

The mount point is the last column, and it can contain spaces. The second argument of `split` is the maximum number of cuts: with 5, the first five columns are cut off and everything after them stays one piece. `none` as the first argument keeps the whitespace behaviour.

**The documented default is wrong.** ansible-core's own documentation for the filter, `plugins/filter/split.yml`, says the separator defaults to `' '`, a single space. The filter passes its arguments straight to Python's `str.split`, whose default splits on any whitespace. `'a  b' | split` gave `['a', 'b']`, while `'a  b' | split(' ')` gave `['a', '', 'b']`, with an empty item for the second space. On `df` output, an explicit `split(' ')` would be full of empty strings. The maximum number of cuts isn't documented either.

## regex_findall: every line at once, as strings

`regex_findall` on the whole of `stdout` returns one list per matching line, one item per group in parentheses:

```yaml
df_rows: "{{ df.stdout | regex_findall('(?m)^(\\S+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)%\\s+(.+)$') }}"
```

- `(?m)` makes `^` and `$` match at each line's start and end, not just the string's.
- The header line has no numbers, so it doesn't match: 2 rows from 3 lines, without skipping it by hand.
- `(.+)$` takes the rest of the line, so `/srv/app data` comes out whole.

The loop row was `['/dev/loop0', '27234304', '24576', '24866816', '1', '/srv/app data']`. **Every field is a string.** Compared with a string, `'24866816' > '3000000'` was false, because strings compare character by character and `'2'` comes before `'3'`. With `int` first, `'24866816' | int > 3000000` was true. [Part 6](set-operations-union-difference-proxmox-drift.md) met the same trap with VMIDs.

## from_json: let the command do the parsing

`findmnt`, from util-linux, prints mount information, and `-J` makes it JSON. `-b` gives sizes in bytes, `-l` a flat list, and `-o` picks the columns:

```yaml
- name: Read the mounts as JSON
  ansible.builtin.command: findmnt -J -b -l -o TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%
  register: findmnt
  changed_when: false
```

`findmnt.stdout | from_json` gave a dict, and the loop mount came out as:

```
{'target': '/srv/app data', 'source': '/dev/loop0', 'fstype': 'ext4',
 'size': 27234304, 'used': 24576, 'avail': 24866816, 'use%': '0%'}
```

- **Numbers are numbers:** `avail` is an `int`, so comparisons work without `int`.
- **The path is whole:** JSON quotes strings, so spaces don't matter.
- **`use%` needs brackets:** `row['use%']`, because `row.use%` isn't valid Jinja.
- **Without `-l`, it's a tree:** child mounts are nested under a `children` key, and the top level only had `/`.

`from_yaml` on the same text gave an identical dict, since JSON is valid YAML. Use `from_json` for JSON anyway: it says what the data is, and it fails on YAML-only syntax that a JSON tool would never print.

## Three sources, two meanings of "full"

The sizes agreed: `df`, `findmnt` and the mount facts all gave 27234304 bytes. The mount facts decoded the space too, although `/proc/mounts`, where Linux lists mounts, writes it as `\040`: they gave `/srv/app data`. But `df` and `findmnt` disagreed on how full the file systems were:

| | loop0 | `/` |
|---|---|---|
| `df`, Capacity | 1% | 31% |
| `findmnt`, `use%` | 0% | 5% |

They don't compute the same thing:
- **`df`:** used / (used + available), rounded up;
- **`findmnt`:** used / size.

The difference is space that is neither used nor available. On loop0 that was 2.3 MB, 572 blocks of 4 KiB. `tune2fs -l` showed 409 of them as ext4's *reserved blocks*, the 5% that `mkfs.ext4` keeps for the root user by default. ext4 holds back the other 163 itself, so that writes can still complete when the file system is nearly full. On `/`, a container disk with a quota, the gap was most of the disk. To check how close a file system is to full, `df`'s definition is the one that matches what users can still write.

## Which one

- **The command has a JSON option:** use it, with `from_json`. Numbers stay numbers, and spaces and quoting are the command's problem.
- **Columns with a free-text last column:** `split(none, N)`, with N the number of columns before it.
- **Several lines, or a format with fixed markers:** `regex_findall` on `stdout`, then `int` or `float` on the numbers.
- **The information is already a fact:** use the fact. The mount facts gave the same sizes as both commands, with no parsing.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/07-strings-into-structures), runs all of the above on the local machine, changing nothing outside its `out/` directory. Mounting a file system needs root, so `parse.yml` reads the `df`, `findmnt` and mount-fact output recorded on the machine above, from `fixtures/`, and writes every result to `out/parse.txt`. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: `plugins/filter/core.py` (`split` as a passthrough to `str.split`, `regex_findall`, `from_json`, `from_yaml`) and `plugins/filter/split.yml` (the documented default separator).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `playbook_guide/playbooks_filters.rst`, *Transforming strings into lists*, *Formatting data: YAML and JSON* and *Searching strings with regular expressions*.
- Python documentation: [`str.split`](https://docs.python.org/3/library/stdtypes.html#str.split).
- GNU coreutils 9.4 (`df`) and util-linux 2.39.3 (`findmnt`), on Ubuntu 24.04.
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on a 32 MiB ext4 image created with `mkfs.ext4` and mounted with `mount -o loop`.
