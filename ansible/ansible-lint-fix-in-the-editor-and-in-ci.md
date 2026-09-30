# Linting Ansible before it reaches Git: `--fix` in the editor, the same ansible-lint in CI

Tenth entry in the Ansible development environment series. *ansible-lint* is the ADT tool that checks playbooks and roles against best-practice rules ([part 5](ansible-development-tools-adt.md)). It runs in two places:
- **in the editor**, where the Ansible extension runs it on each file and can rewrite what it knows how to fix;
- **in CI** (continuous integration, checks that run on every push and pull request), where it gates what gets merged.

The aim is that both run the same rules, so nothing new appears after a push. Everything below used ansible-lint 26.9.0 with ansible-core 2.21.4, and the Ansible extension's source at commit `509d149` (2026-09-29).

## In the editor: `autoFixOnSave`

Alex Dworjan's [2024 tip](https://www.youtube.com/watch?v=ws_VsyfpGHo) was to add `--fix` to the extension's lint arguments. The extension now has a setting for it, `ansible.validation.lint.autoFixOnSave` (default `false`), which goes in the repository's `.vscode/settings.json` from [part 6](vscode-ansible-settings-per-repository.md):

```json
{
  "ansible.validation.lint.autoFixOnSave": true
}
```

The name undersells it. In the language server, this setting appends `--fix` to every full ansible-lint run, and a full run happens when a file is **opened** as well as when it's saved. So opening an old playbook can rewrite it on disk. The extension passes only that file's path. Run the same way, `ansible-lint --fix site.yml` left a second playbook in the same repository untouched.

## What `--fix` changed

A sample playbook with typical legacy style: an unnamed play, lowercase task names, `become: yes`, `yum: name=httpd state=present` in free form, `shell:` for a plain command, `when: "{{ … }}"`, a `block` whose `name` and `when` come after it, `become_user` without `become`, and a bare `debug:`. `ansible-lint --fix site.yml`, run repeatedly, as successive saves would:

| Run | Failures | Warnings |
|---|---|---|
| before | 19 | 2 |
| after `--fix` once | 6 | 1 |
| twice | 4 | 1 |
| three times | 4 | 0 |
| four times | 4 | 0, file unchanged |

One pass doesn't fix everything: the `block` task's name was only capitalised on the second pass, and the spaces inside `{{ }}` came on the third. Among the rewrites:
- FQCNs (fully qualified collection names such as `ansible.builtin.debug` instead of `debug`);
- `yes` to `true`, and the list indentation;
- free-form arguments to YAML keys;
- task names capitalised;
- `name` and `when` moved above `block`;
- Jinja braces removed from `when`, and spaces added inside `{{ }}`.

Three rewrites change more than style, so read the diff:
- **`shell:` became `ansible.builtin.command:`.** The rule only does this when the command uses no shell features.
- **`yum:` became `ansible.builtin.dnf:`.** In ansible-core 2.21, `yum` is a redirect to `dnf` (`ansible_builtin_runtime.yml`), so it's the same module under its real name.
- **`become: true` was added to the task that had `become_user: root`.** Here the play already had `become`, so nothing changed at run time. In a play without it, the task would now switch user where it didn't before.

The last four failures need a person: name the play, name the `debug` task, use the `systemd` module instead of `command: systemctl`, and add `changed_when`.

## One `.ansible-lint` for both

```yaml
---
profile: production
write_list:
  - formatting
```

- **`profile`** picks the rule set; `production` is the strictest of ansible-lint's built-in profiles.
- **`write_list`** limits which rules `--fix` may apply; the default is all of them. With `formatting`, a bare `--fix`, which is what the extension passes, applied only the FQCN, key-order and YAML fixes. It left the task names, free-form arguments, `shell` and `become` for a person: 13 failures instead of 6.

The extension looks for this file the way ansible-lint does, walking up from the linted file, and passes it with `-c`. So the editor and CI read the same file.

## In CI: pin what runs

Dworjan's example workflow uses `actions/checkout@v4` and `ansible/ansible-lint@main`. Both are moving references:
- `main` means a different ansible-lint whenever that branch moves;
- a tag like `v4` can be re-pointed.

Pinning an action by its commit SHA, with the version in a comment, freezes it. The example's commented-out `path:` input also no longer exists; the current action takes `args` and `working_directory`.

**With the ansible-lint action:**

```yaml
name: ansible-lint

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  ansible-lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: ansible/ansible-lint@e7f397ad6dfa20d274afa17cd7bbedd84ed136f5 # v26.9.0
```

The action installs ansible-lint from its own reference, so the SHA pins the ansible-lint version. It also installs from the action's lock file, but that file is exported with `--no-emit-package ansible-core`: ansible-core itself isn't pinned, and each run gets whatever version is newest that day. The action also defaults to Python 3.14.

**With the project's own lock file.** If the lock file from [part 2](pinning-ansible-core-pip-tools-uv-poetry.md) includes ansible-lint, as the ADT lock in [part 9](shared-dev-server-for-vscode-remote-ssh.md) does, CI can install exactly what developers have:

```yaml
name: ansible-lint (locked)

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  ansible-lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      - run: pip install --require-hashes -r requirements.txt
      - run: ansible-lint
```

Installed locally the same way, that lock gave ansible-lint 26.9.0 with ansible-core 2.21.4, and the same 19 failures and 2 warnings on the sample. The action's lock, by contrast, pinned ansible-compat 26.8.0 while the ADT lock had 26.9.0: close, but not the same set.

Both workflows pass actionlint 1.7.12, and zizmor 1.30.1 reported no findings. These are the two checks this site runs on its own workflows. `persist-credentials: false` stops checkout from leaving the job's token in `.git/config`, which zizmor flags.

## Sources

- ansible-lint, [ansible/ansible-lint](https://github.com/ansible/ansible-lint) at `f9364be` (2026-09-24):
  - `docs/autofix.md` and `docs/_autofix_rules.md` for `write_list` and the fixable rules;
  - `action.yml`, and `.config/requirements-lock.txt` at tag v26.9.0.
- The Ansible extension, [ansible/vscode-ansible](https://github.com/ansible/vscode-ansible) at `509d149`:
  - `package.json` for the `ansible.validation.lint.*` settings;
  - `packages/ansible-language-server/src/services/ansibleLint.ts`, where `--fix` is appended;
  - `ansibleLanguageService.ts`, which runs full validation on open and on save.
- Alex Dworjan, [Ansible Developer Environment Tips](https://www.youtube.com/watch?v=ws_VsyfpGHo) (2024-06), and his [Ansible-SNOW workflow](https://github.com/shadowman-lab/Ansible-SNOW/blob/main/.github/workflows/ansible-lint.yml).
- ansible-core 2.21.4's `ansible_builtin_runtime.yml`, for the `yum` → `dnf` redirect.
