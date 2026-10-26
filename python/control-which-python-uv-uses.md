# Controlling which Python uv uses

[uv](https://docs.astral.sh/uv/) is Astral's Python package and project manager. When it needs an interpreter it can either use one already on the machine (a *system* Python: the OS's, or one from another installer such as pyenv) or download its own *managed* build into `~/.local/share/uv/python`. By default it prefers managed Pythons, but it still prefers an existing system Python over downloading a new one ([Python versions](https://docs.astral.sh/uv/concepts/python-versions/)).

That's how a surprise happens: a package manager installs a brand-new Python as a dependency of something else, uv picks it up, and a tool run with `uv tool run` (which runs a command-line tool in a throwaway environment) breaks because, for example, `ansible-core` doesn't support that version yet. Removing that Python can break whatever depends on it; telling uv which version to use leaves it in place. This entry covers how to choose, check and clean up the Python uv uses. Checked with uv 0.13.

## See which Python uv picks

```sh
uv python find                    # the interpreter uv would use here
uv python list --only-installed   # every Python uv can see, managed or not
```

`uv python list` prints one line per interpreter with its path, so you can tell a managed Python (under `~/.local/share/uv/python`) from a system one.

## Tell uv which version to use

Pick a scope:

```sh
# 1. One command
uv tool run --python 3.13 --from ansible-core --with jmespath,requests ansible-playbook site.yml

# 2. One project: writes .python-version in the current directory
cd ~/path/to/playbooks
uv python pin 3.13

# 3. Your user: a global default
uv python pin --global 3.13

# 4. One shell or CI job, without writing a file
export UV_PYTHON=3.13
```

`uv python pin` only writes a `.python-version` file containing `3.13`. uv looks for that file in the working directory and its parents, so it applies to the whole project. With `--global` the file goes into uv's user config directory instead (`~/.config/uv/.python-version` on Linux and macOS) and applies everywhere no project file overrides it. `UV_PYTHON` is the environment-variable form of `--python`, so it wins over both files for commands such as `uv run` and `uv sync`.

To pre-download the interpreter, run `uv python install 3.13`.

## Reinstall tools that were built on the wrong Python

`uv tool run` builds a fresh environment, but `uv tool install` builds a tool's environment once, under `~/.local/share/uv/tools/`, and keeps it. Pinning afterwards doesn't change an environment that already exists, so rebuild it:

```sh
uv tool install --reinstall --python 3.13 ansible-core
uv tool list --show-python    # which Python each installed tool uses
```

## `.python-version` versus `requires-python`

They answer different questions:

- `.python-version` picks **which interpreter** uv uses.
- `requires-python` in a project's `pyproject.toml` (the project's metadata file) says **which versions the project supports**.

When the pin falls outside that range, uv stops instead of guessing:

```text
error: The Python request from `.python-version` resolved to Python 3.13.17, which is incompatible with the project's Python requirement: `>=3.14` (from `project.requires-python`)
```

Change the pin (`uv python pin 3.14`) or the requirement, whichever is wrong.

## Choose managed or system Pythons for good

The `python-preference` setting in `~/.config/uv/uv.toml` (uv's user configuration file) decides which kind of interpreter uv may use:

| Value | Uses |
|---|---|
| `managed` (default) | managed first, system if no managed one fits |
| `only-managed` | managed only, never a system one |
| `system` | system first, managed if no system one fits |
| `only-system` | system only, for example where the OS's Python is mandated |

```toml
# ~/.config/uv/uv.toml
python-preference = "only-managed"
```

For a single command, `--managed-python` and `--no-managed-python` do the same as `only-managed` and `only-system`.

## Stop uv from downloading Pythons

On an offline machine, or one where downloads must go through review, turn automatic downloads off. uv then only uses interpreters already present:

```toml
# ~/.config/uv/uv.toml
python-downloads = "never"
```

The per-command forms are `--no-python-downloads` and `UV_PYTHON_DOWNLOADS=never`. Combined with `only-managed`, uv only uses the managed Pythons you installed yourself with `uv python install`.

## Upgrade and clean up managed Pythons

```sh
uv python upgrade 3.13      # move to the latest 3.13.x patch release
uv python uninstall 3.12    # remove a managed version you no longer use
```

Each managed version stays under `~/.local/share/uv/python` until you remove it.

## Get a `python` command without touching the system one

`uv python install 3.13` only adds a versioned command, `~/.local/bin/python3.13`. To also get `python` and `python3`:

```sh
uv python install --default 3.13
```

That adds `python` and `python3` links in `~/.local/bin`. Nothing under `/usr/bin` changes; whether your shell finds them first depends on `~/.local/bin` coming before those directories in `PATH`.

The uv commands ran in a Linux cloud container with uv 0.13, except `uv python install --default`, `uv python upgrade` and `uv python uninstall`, whose options were only checked in `uv help`.
