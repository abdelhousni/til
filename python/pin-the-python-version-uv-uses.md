# Pinning the Python version uv uses instead of uninstalling Homebrew's

[uv](https://docs.astral.sh/uv/) is Astral's Python package and project manager. When it needs an interpreter it can either use one already on the machine or download its own *managed* build. If you just ran `brew install` for something that pulled in a brand-new Python (say `python@3.15`), uv can pick that one up, and a tool run with `uv tool run` (which runs a command-line tool in a throwaway environment) breaks because, for example, `ansible-core` doesn't support it yet.

The reflex is to uninstall that Python. Homebrew often refuses, because another formula (a Homebrew package, here `keychain`) depends on it. Forcing it with `--ignore-dependencies` leaves that formula broken. Telling uv which version to use fixes the error without touching Homebrew.

## See what depends on the Homebrew Python

```sh
brew uses --installed --recursive python@3.15   # installed formulae that need it
brew deps --installed keychain                  # what keychain needs
```

If anything you still use shows up, leave the formula alone.

## Tell uv which version to use

uv prefers its own managed Pythons, but it still prefers an existing system Python over downloading a new one ([Python versions](https://docs.astral.sh/uv/concepts/python-versions/)). That's how Homebrew's 3.15 ends up in a tool environment. Pick a scope:

```sh
# 1. One command
uv tool run --python 3.13 --from ansible-core --with jmespath,requests ansible-playbook site.yml

# 2. One project: writes .python-version in the current directory
cd ~/path/to/playbooks
uv python pin 3.13

# 3. Your user: a global default
uv python pin --global 3.13
```

`uv python pin` only writes a `.python-version` file containing `3.13`. uv looks for that file in the working directory and its parents, so it applies to the whole project. With `--global` the file goes into uv's user config directory instead (`~/.config/uv/.python-version` on Linux and macOS) and applies everywhere no project file overrides it.

To pre-download the interpreter, run `uv python install 3.13`.

## Never use a non-uv Python

The `python-preference` setting decides which interpreters uv may use. `only-managed` rules out Homebrew's (and any other system Python): uv downloads its own when needed.

```toml
# ~/.config/uv/uv.toml
python-preference = "only-managed"
```

## If you still want the Homebrew Python gone

1. Remove what depends on it first, if you don't need it: `brew uninstall keychain`. Otherwise accept that `python@3.15` stays.
2. Run `brew autoremove --dry-run` and review the list before running `brew autoremove`, which removes formulae that were only installed as dependencies.
3. Run `brew uninstall python@3.15`.

Forcing the removal breaks dependents, and the usual way out is reinstalling them afterwards.

The `uv python pin` commands ran in a Linux cloud container with uv 0.13; the Homebrew commands were not run, and macOS wasn't used.
