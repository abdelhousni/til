# Scaffolding with ansible-creator: roles inside a collection, and what to change in the output

Eleventh entry in the Ansible development environment series. *ansible-creator* is the ADT tool ([part 5](ansible-development-tools-adt.md)) that generates project layouts, so nobody builds the directories by hand. Alex Dworjan's 2024 videos use an older command syntax. Everything below ran ansible-creator 26.9.0 with ansible-core 2.21.4.

## The commands now

- **`init`** creates a project: `collection`, `playbook`, `execution_env` or `decision_environment`.
- **`add resource`** adds to an existing project: a `role`, a `playbook`, `devcontainer` or `devfile` files, an `execution-environment` file, `ee-ci` (an EE build workflow), `play-argspec` or `ai` (agent instruction files).
- **`add plugin`** adds an `action`, `filter`, `lookup`, `module` or `test` plugin to a collection.

The Ansible extension's command palette runs the same tool: **Ansible: Create New Playbook Project**, **Ansible: Create New Collection**, **Ansible: Add Role** and so on.

## A playbook project, with its own collection

```sh
ansible-creator init playbook myorg.webstack webstack
```

The argument `myorg.webstack` names a *collection* (a distributable package of roles, modules and plugins) that lives inside the project, in `collections/ansible_collections/myorg/webstack/`. Ansible loads collections from a `collections/` directory next to the playbook, as [part 7](develop-against-the-production-execution-environment.md) showed, so nothing needs installing. Around it, the project gets:
- `site.yml` and two sample playbooks;
- an `inventory/` with `host_vars/` and `group_vars/`;
- `ansible.cfg`, `ansible-navigator.yml` and `collections/requirements.yml`;
- the three `devcontainer.json` files from [part 8](ansible-dev-container-with-adt.md), a `devfile.yaml`, and `.vscode/extensions.json` ([part 6](vscode-ansible-settings-per-repository.md));
- a GitHub workflow and an `AGENTS.md`.

`--exclude devfile ai` leaves out bundles you don't want; the choices are `ai`, `devcontainer`, `devfile`, `gitignore`, `role` and `vscode`.

The scaffold's `site.yml` calls its sample role by its full name, `myorg.webstack.run`, and `ansible-playbook site.yml` ran it straight from the project's collection. A fresh scaffold also passes ansible-lint at the `production` profile: 26 files, 0 failures.

## Put roles inside that collection

```sh
ansible-creator add resource role webserver collections/ansible_collections/myorg/webstack
```

The new role is called as `myorg.webstack.webserver`, the same way on every machine. When the collection is ready to share, it's already the layout that `ansible-galaxy collection build` packages. Standalone roles, found by a bare name through a roles path, get neither.

Each generated role also has a `meta/argument_specs.yml`, which declares the role's variables. Ansible checks callers against it before the first task runs. With a `webserver_port` declared as a required `int`, passing `eighty` stopped the play:

```text
Validation of arguments failed:
argument 'webserver_port' is of type str and we were unable to convert to int: "'eighty'" cannot be converted to an int
```

## What to change in the output

**`ansible.cfg`:**
- **Two keys don't exist.** `host_vars_inventory` and `group_vars_inventory` aren't Ansible settings: neither appears in `ansible-config init --disabled`, and Ansible ignores them without a warning. It reads `host_vars/` and `group_vars/` next to the inventory anyway: `ansible-inventory --host server1` returned the same variables with and without the two keys, so delete both.
- **`verbosity = 2` makes every command verbose.** Even `ansible-doc` printed its version banner and config paths. Remove it, and use `-v` when you want it.
- **`remote_user = myuser`** is a placeholder.
- **Add `collections_path = ./collections`.** Without it, `ansible-doc -t role myorg.webstack.webserver` printed nothing: only a playbook run looks in the playbook's `collections/`. With it, `ansible-doc` showed the role and its options, and `site.yml` still ran.

**`ansible-navigator.yml` names no EE.** It falls back to the ADT image, as part 8 found. Name yours by digest, as in part 7.

**`collections/requirements.yml` is a sample.** It lists `cisco.ios` without a version and a collection straight from a Git repository. Replace it with your own dependencies, pinned.

**The CI workflow needs replacing, not just pinning.** `.github/workflows/tests.yml` calls a *reusable workflow* (a workflow from another repository, called like a function) at `ansible/ansible-content-actions/.github/workflows/ansible_lint.yaml@main`. zizmor 1.30.1 flags it twice:
- `unpinned-uses` (high): `@main` runs whatever that branch holds today;
- `excessive-permissions` (medium): the job gets the repository token's default permissions.

Pinning it by SHA wouldn't pin the linter, for two reasons found in that workflow:
- It runs `pip install ansible-lint` with no version.
- Its Python setup step is guarded by `if: inputs.setup_python == 'true'`, where `setup_python` is a boolean input. GitHub compares mismatched types as numbers: `true` becomes 1 and the string `'true'` becomes NaN. So the condition is never true, the step never runs, and ansible-lint is installed into the runner's own Python.

[Part 10](ansible-lint-fix-in-the-editor-and-in-ci.md)'s pinned workflow does the same job. The collection scaffold calls seven reusable workflows at `@main`, six of them from ansible-content-actions, including a release job that hands one the Galaxy API key as a secret. The EE scaffold uses `actions/checkout@v4` and `actions/setup-python@v5`, which are tags rather than SHAs.

## The other two scaffolds

- **`init collection myorg.platform`** is for a collection you publish on its own. It adds sample plugins, Molecule scenarios, unit and integration tests, `tox-ansible.ini`, changelog configuration and a release workflow.
- **`init execution_env`** writes an `execution-environment.yml` based on `quay.io/fedora/fedora:41`, a release that reached end of life on 2025-12-15, with ansible-core unpinned. [Part 3](execution-environment-from-a-locked-requirements-file.md) builds the same kind of file from a lock file and a base image pinned by digest.

## Sources

- `ansible-creator` 26.9.0: `--help` for `init`, `add resource` and `add plugin`, and the generated files.
- The Ansible extension's manifest, `package.json` in [ansible/vscode-ansible](https://github.com/ansible/vscode-ansible) at `509d149`: the `ansible.content-creator.*` commands.
- [ansible/ansible-content-actions](https://github.com/ansible/ansible-content-actions) at `cbdec1f`, `.github/workflows/ansible_lint.yaml`.
- GitHub docs, [Evaluate expressions in workflows and actions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions), the type-coercion table for `==`.
- Fedora end-of-life dates from [endoflife.date](https://endoflife.date/fedora).
- Alex Dworjan, [Ansible Developer Environment Updates](https://www.youtube.com/watch?v=qzi-oQ1dQL0) (2024-05) and [Ansible Developer Environment Tips](https://www.youtube.com/watch?v=ws_VsyfpGHo) (2024-06).
