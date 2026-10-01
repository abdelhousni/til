# A collection-aware venv with ansible-dev-environment (ade): what it installs, what it edits, and how to pin it

Twelfth entry in the Ansible development environment series. **ansible-dev-environment**, whose command is `ade`, is one of the tools that come with [ADT](ansible-development-tools-adt.md). It builds a venv for Ansible work: a directory with its own Python and packages ([part 1](locking-an-ansible-dev-environment-pip-to-ee.md) compares it with the other options). Into that venv it installs:
- [ansible-core](pinning-ansible-core-pip-tools-uv-poetry.md), the engine that runs playbooks;
- *collections*, the packages that ship roles, modules and plugins;
- the Python libraries those collections declare.

It's useful before a team has an [execution environment](execution-environment-from-a-locked-requirements-file.md) (EE), and while developing a collection. Everything below ran ade 26.9.0 with uv 0.12.20 on 2026-09-30.

## Installing collections and their Python dependencies

A project's `requirements.yml` listed one collection, `amazon.aws` 11.4.0. The collection's own `requirements.txt` asks for `boto3`, `botocore` and `aiobotocore`.

```sh
ade install -r requirements.yml --venv .venv -p 3.12 --no-seed
```

```text
Note: Created virtual environment: .../.venv using python3.12
Note: Installed collections include: amazon.aws
Note: All python requirements are installed.
Note: All required system packages are installed.
```

- **The collection went into the venv**, under `.venv/lib/python3.12/site-packages/ansible_collections/`, not into `~/.ansible/collections`. Deleting `.venv` removes it.
- **Its Python libraries went into the venv too.** boto3 and botocore came in at 1.43.75, the newest releases, because the collection only sets minimums.
- **ansible-core came in at 2.21.4**, also the newest.
- **`-p` picks the Python.** Without it, ade uses the Python it runs on. Which Python you use also decides which ansible-core you can get, as [part 5](ansible-development-tools-adt.md) showed. Alex Dworjan's [2024 video](https://www.youtube.com/watch?v=ws_VsyfpGHo) switched RHEL 9's system `python3` to 3.11 with `update-alternatives` for this. `-p` makes that unnecessary, and it leaves the system Python alone.
- **ade used [uv](../python/newer-python-with-uv-without-touching-system-python-rhel.md)**, a fast Python package installer, because it was on `PATH`: `--uv` is on by default. `--no-uv` falls back to `venv` and pip.

By default ade also *seeds* the venv with ADT itself, the whole toolchain, at whatever version is newest. `--no-seed` installs ansible-core only, which is what these tests used. The seeding behaviour here comes from ade's source (`installer.py`), not from a seeded run.

## It edits `ansible.cfg`

After that install, the project had an `ansible.cfg` it didn't have before:

```ini
[defaults]
collections_path = .
```

That's the default *isolation mode*, `cfg`. It stops Ansible from also loading collections from `~/.ansible/collections`. On this machine that directory held collections left from other work. Without the file, `ansible-galaxy collection list` showed them next to the venv's. With it, only the venv's.

But ade applies the same edit to a project's existing `ansible.cfg`. In a project that had `collections_path = ./collections`, the layout [part 11](scaffolding-with-ansible-creator.md) uses, ade replaced the value with `.`. It printed a note, `ansible.cfg updated with 'collections_path = .' to isolate this workspace`, and gave no warning. Commit the file before running ade, and check the diff afterwards. In `cfg` mode, ade also stops if `ANSIBLE_CONFIG` is set, since that variable would override the project's file.

The other modes, chosen with `--im`:
- **`restrictive`** doesn't write `ansible.cfg` (ade's `cli.py`). It stops if `~/.ansible/collections` contains anything, and its hint says to run `rm -rf` on that directory. Check what's in there before following it.
- **`none`** doesn't isolate at all.

## Developing a collection: `ade install -e .`

In a collection scaffolded with `ansible-creator init collection myorg.tools`:

```sh
ade install -e . --venv .venv --no-seed
```

`-e` is an *editable* install: instead of copying the collection into the venv, ade symlinks each top-level file and directory of the working copy there. An edit to a plugin applies on the next run. Changing the sample filter's return value from `"Hello, "` to `"Hi, "` changed the next `ansible` run's output, with no reinstall. ade's own note adds the limit: after adding a new top-level file or directory, run `ade install -e .` again.

The same command also did two things beyond the symlinks:
- **It installed the collection's dependencies** from `galaxy.yml`, here `ansible.utils`, plus the Python libraries in its `requirements.txt`.
- **It edited `galaxy.yml`**, adding `.venv`, `collections` and `.tox` to `build_ignore` so that `ansible-galaxy collection build` leaves them out.

## System packages: a warning, and exit code 2

A collection can list the system packages it needs in `bindep.txt`, a format for listing packages per platform. ade checks them and doesn't install them. With `libpq-dev [platform:dpkg]` added to the test collection's file, on an Ubuntu machine without it:

```text
Warning: Required system packages are missing. Please use the system package manager to install them.
- libpq-dev
```

Everything else was installed, and ade exited with code 2. Entries tagged with a profile, such as amazon.aws's `openssl [test platform:rpm]`, weren't checked: those are for the collection's own tests.

## Nothing is pinned, unless you pass a lock

By default, every version ade installs is the newest that fits:
- ansible-core, unless you pass `--acv 2.21.4`;
- ADT when seeding, unless you pass `--adtv 26.9.0`;
- each collection's Python libraries, which only have lower bounds.

Two runs a month apart can build different venvs. ade isolates dependencies; it doesn't lock them.

It does install through `uv pip install` or `pip install`, and both read a constraints file from the environment: `UV_CONSTRAINT` and `PIP_CONSTRAINT`. A *constraints file* limits the version of any package that gets installed, without asking for it to be installed. A lock from [part 2](pinning-ansible-core-pip-tools-uv-poetry.md) works as one. Here, the lock was compiled with uv's `--exclude-newer 2026-06-01T00:00:00Z`, which ignores anything uploaded to PyPI, the Python package index, after that date. So it held older versions than the newest ones:

```sh
UV_CONSTRAINT=$PWD/constraints.txt ade install -r requirements.yml --venv .venv -p 3.12 --no-seed
```

The venv then had exactly the lock's versions: ansible-core 2.21.0, boto3 and botocore 1.43.0, and aiobotocore 3.7.0, instead of 2.21.4, 1.43.75 and 3.9.1. `PIP_CONSTRAINT` with `--no-uv` gave the same result.

Collections are another matter. `requirements.yml` pins the ones it lists with `==`, but a collection's own collection dependencies float, as part 2 found for `ansible-galaxy`.

## The other subcommands

- **`ade list`** lists the venv's collections, with the source directory for editable ones.
- **`ade check`** re-checks collection, Python and system dependencies.
- **`ade tree`** prints the collection dependency tree.
- **`ade uninstall amazon.aws`** removed the collection but left boto3 and botocore in the venv.

## In the editor

Dworjan's video then points the Ansible extension's `ansible.python.interpreterPath` at the venv's `bin/python`, so that completion and highlighting see the venv's collections. That step wasn't tested here. [Part 6](vscode-ansible-settings-per-repository.md) covers the setting: each machine is expected to set its own, so commit it only where the path is the same for everyone.

## The example repository

The series' companion repository repeats these steps, in [abdelhousni/ansible-development-environment-series](https://github.com/abdelhousni/ansible-development-environment-series/tree/main/12-collection-venv-with-ansible-dev-environment). It holds:
- the `requirements.yml` with amazon.aws 11.4.0, and the constraints lock above;
- an `ansible.cfg` with `collections_path = ./collections`;
- a minimal collection under development, whose `bindep.txt` names a package that doesn't exist.

A script runs ade in a scratch copy and prints what each step did:
- the venv's versions match the lock;
- `ansible.cfg` is rewritten;
- the editable install exits with code 2 and names the missing package;
- the editable install adds `.venv`, `collections` and `.tox` to `build_ignore`;
- a filter's output changes after an edit to the plugin, without a reinstall.

Its CI runs the script on every push and compares the output with the expected one.

## Sources

- `ade --help` and `ade install --help` (26.9.0), and its source: `subcommands/installer.py` for seeding, the ansible-core install and the Python requirements command, `config.py` for `uv pip`, and `cli.py` for the isolation modes.
- [ansible/ansible-dev-environment](https://github.com/ansible/ansible-dev-environment).
- uv and pip's constraint variables: [uv environment variables](https://docs.astral.sh/uv/reference/environment/) (`UV_CONSTRAINT`) and [pip's configuration docs](https://pip.pypa.io/en/stable/topics/configuration/) (any option as `PIP_<NAME>`).
- amazon.aws 11.4.0 from Galaxy: its `requirements.txt` and `bindep.txt`.
- Alex Dworjan, [Ansible Developer Environment Tips](https://www.youtube.com/watch?v=ws_VsyfpGHo) (2024-06).
- Every output above came from ade 26.9.0, uv 0.12.20, ansible-creator 26.9.0 and Python 3.12, on Ubuntu, on 2026-09-30.
