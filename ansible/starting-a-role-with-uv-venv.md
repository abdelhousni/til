# Starting an Ansible role project with uv for the venv

Ansible needs a Python environment (`ansible-core`, plus `ansible-lint`/`molecule` if you're testing), but a role's directory layout is fixed by `ansible-galaxy` — not something `uv init`'s project scaffolding understands. So the two tools stay in their own lanes: `ansible-galaxy` for the role skeleton, `uv` purely for the venv.

## Scaffold the role, then the venv

```sh
ansible-galaxy role init my_role
cd my_role
uv venv
```

`uv venv` creates a `.venv/` here with no `pyproject.toml` needed — there's no Python package being built, just an isolated interpreter to install `ansible-core` into.

## Install into it, without activating

```sh
uv pip install ansible-core ansible-lint molecule
```

`uv pip install` targets the `.venv` it finds in the current directory directly — no `source .venv/bin/activate` step required for the install itself.

## Running things

```sh
uv run ansible-lint
uv run molecule test
```

`uv run` also finds and uses that same `.venv` automatically, even with no `pyproject.toml` in sight — normally `uv run` implies a full uv-managed project, but outside of one it just falls back to whatever virtual environment it finds in the current or a parent directory. So the whole workflow never needs a manual `source .venv/bin/activate`, but if a specific tool insists on an activated shell, that still works exactly as normal: `source .venv/bin/activate` then run commands directly.

## The one thing not to forget

`.venv/` isn't part of the role and shouldn't be committed — add it to `.gitignore` (or check `ansible-galaxy role init`'s generated one already covers it, some templates do and some don't):

```
.venv/
```

Aside from that, the role directory `ansible-galaxy` created is untouched — `defaults/`, `tasks/`, `handlers/`, `meta/`, all exactly as normal. `uv` never needs to know any of that exists; it's just managing the interpreter these tools run under.
