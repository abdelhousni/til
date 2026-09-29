# Getting a newer Python on RHEL without touching the system python3

RHEL (and Rocky/Alma/CentOS Stream) ties `/usr/bin/python3` to whatever version the OS release shipped with. `dnf` and a bunch of system tooling depend on that exact interpreter, so replacing it is how you break `dnf` on the next update. [uv](https://docs.astral.sh/uv/), a Python package and project manager from Astral, sidesteps the whole problem: it downloads its own standalone Python builds into your home directory, completely separate from anything RPM-managed. Based on [this Fedora Magazine writeup](https://fedoramagazine.org/enhancing-your-python-workflow-with-uv-on-fedora/). It was written for Fedora, but nothing in it is Fedora-specific, since uv doesn't install RPMs. Checked with uv 0.11.

## Install uv itself

On RHEL there's no guaranteed `uv` package in the default repos (unlike Fedora, which has one). The official installer script works the same everywhere and doesn't need root:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

It puts `uv` in `~/.local/bin`, which RHEL's default `~/.bashrc` already adds to `PATH`.

## Install a newer Python, alongside the system one

```sh
uv python install 3.13
```

The interpreter itself lands under `~/.local/share/uv/python/cpython-3.13…/`, nowhere near `/usr/bin/python3`. uv also adds one **versioned** command, `~/.local/bin/python3.13`, so `python3.13` works straight away. `python3` and `python` are left alone: `which python3` still answers `/usr/bin/python3`.

## Use it, without making it "the" python3

A *venv* (virtual environment) is a project directory with its own interpreter and packages, isolated from the system ones:

```sh
uv venv --python 3.13          # a .venv/ for this project, built on 3.13
uv run --python 3.13 script.py # run one script against 3.13 directly
```

Both work whatever `python3` on `PATH` points to, because you name the interpreter explicitly. [Starting an Ansible role project with uv](../ansible/starting-a-role-with-uv-venv.md) uses the same `uv venv` for `ansible-core`.

## If you want `python3` itself to be the new one

```sh
uv python install 3.13 --default
```

This also adds unversioned `python3` and `python` commands to `~/.local/bin`. Since that directory comes before `/usr/bin` in your `PATH`, they win in your own shells. `/usr/bin/python3` is untouched, and so are `dnf` and anything else that calls it by full path. uv won't overwrite a `python3` in `~/.local/bin` that it didn't create either: it warns "Executable already exists … but is not managed by uv; use `--force` to replace it" and leaves the file in place.

Older uv releases marked `--default` as experimental and needed `--preview`; uv 0.11 doesn't.

## Sources

- The [uv docs](https://docs.astral.sh/uv/) and `uv python install --help`. The behaviour above was checked with uv 0.11.21: the versioned `python3.13` in `~/.local/bin`, `--default` adding `python3`, and the refusal to replace an unmanaged `python3`.
- RHEL's default `~/.bashrc` (`dot-bashrc` in the CentOS Stream 9 and 10 `bash` package) prepends `~/.local/bin` and `~/bin` to `PATH`.
