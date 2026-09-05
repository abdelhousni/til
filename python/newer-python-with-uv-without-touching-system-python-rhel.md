# Getting a newer Python on RHEL without touching the system python3

RHEL (and Rocky/Alma/CentOS Stream) ties `/usr/bin/python3` to whatever version the OS release shipped with — `dnf` and a bunch of system tooling depend on that exact interpreter, so replacing it is how you break `yum`/`dnf` on the next update. [uv](https://docs.astral.sh/uv/) sidesteps the whole problem: it downloads its own standalone Python builds into your home directory, completely separate from anything RPM-managed. Based on [this Fedora Magazine writeup](https://fedoramagazine.org/enhancing-your-python-workflow-with-uv-on-fedora/) — written for Fedora, but nothing in it is Fedora-specific, since uv isn't installing RPMs.

## Install uv itself

On RHEL there's no guaranteed `uv` package in the default repos (unlike Fedora, which has one in its own repos) — the official installer script works identically everywhere and doesn't need root:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Install a newer Python, alongside the system one

```sh
uv python install 3.13
```

This lands under `~/.local/share/uv/python/cpython-3.13.../bin/python3.13` — nowhere near `/usr/bin/python3`, and not on `PATH` by default. `which python3` still resolves to the system one after this, exactly as before.

## Use it, without making it "the" python3

```sh
uv venv --python 3.13          # a project venv built on 3.13
uv run --python 3.13 script.py # run one script against 3.13 directly
```

Both of these work regardless of what `python3` on `PATH` points to — you're telling uv which interpreter to use explicitly, every time, rather than relying on shadowing the system binary.

## If you actually want it on PATH (optional, and still experimental)

```sh
uv python install 3.13 --default
```

This adds `python`/`python3` executables to `~/.local/bin` — still not `/usr/bin/python3` itself, just a directory that (if it's earlier in your `PATH` than `/usr/bin`, which is the common `~/.local/bin` convention) takes priority for your own shell. uv only ever manages executables *it* created, so this can't clobber the system one by accident. This flag is marked experimental in uv's docs, so double-check `uv python install --help` on whatever version you have installed — some earlier uv releases required pairing it with `--preview`.
