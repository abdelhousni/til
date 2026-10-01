# Committing the VS Code Ansible settings with the repository

Sixth entry in the Ansible development environment series. [Part 4](where-to-run-an-ansible-dev-environment.md) chose where VS Code runs and [part 5](ansible-development-tools-adt.md) installed the tools. This part makes every developer's editor behave the same way on a given repository. The means is two small files committed next to the code: one for **settings** and one for **recommended extensions**. The settings configure the Red Hat **Ansible extension** (`redhat.ansible`), which adds syntax checking, ansible-lint, completion and module docs to VS Code.

Every setting below was checked against the extension's own manifest, the `package.json` in [ansible/vscode-ansible](https://github.com/ansible/vscode-ansible) as of 2026-09-29. The released extension was 26.8.2 at the time.

## Where the files go

VS Code reads settings from several *scopes*, and *"later scopes override earlier scopes"*: default, then user, then remote, then workspace, then workspace folder. A *workspace* is usually just the project folder, and its settings live in `.vscode/settings.json`, which VS Code picks up when the folder is opened. Committed to Git, they apply to everyone who opens the repository, and they win over each developer's personal settings.

A *multi-root workspace*, several folders opened together, keeps its settings in a `*.code-workspace` file instead. Dworjan's repositories use one, [`.code-workspace`](https://github.com/shadowman-lab/Ansible-Development/blob/main/.code-workspace), because his Dev Spaces workspaces open through it. For a repository opened as a plain folder, `.vscode/settings.json` is the simpler choice.

## `.vscode/settings.json`

```json
{
  "ansible.validation.enabled": true,
  "ansible.validation.lint.enabled": true,
  "ansible.ansible.useFullyQualifiedCollectionNames": true,
  "ansible.executionEnvironment.enabled": true,
  "ansible.executionEnvironment.image": "registry.example.com/ansible/my-ee@sha256:c89caf41bc7dfc6aa701f1225b2177cfb711223693c89a3300d7ac8db2b3b897",
  "ansible.executionEnvironment.pull.policy": "missing",
  "files.insertFinalNewline": true,
  "files.trimFinalNewlines": true,
  "files.trimTrailingWhitespace": true
}
```

What each line does, and what the manifest says its default is:

| Setting | Default | Why set it |
|---|---|---|
| `ansible.validation.enabled` | `true` | Already on. Stating it in the workspace overrides a developer who turned it off in their user settings |
| `ansible.validation.lint.enabled` | `true` | Same: keeps ansible-lint on. When off, only `ansible-playbook --syntax-check` runs |
| `ansible.ansible.useFullyQualifiedCollectionNames` | `true` | Same: completion inserts `ansible.builtin.copy` rather than `copy` |
| `ansible.executionEnvironment.enabled` | `false` | Runs the extension's ansible-lint and docs inside an *execution environment* (EE), the container image AAP (Red Hat Ansible Automation Platform) runs jobs in. Completion then knows exactly the collections production has |
| `ansible.executionEnvironment.image` | `ghcr.io/ansible/community-ansible-dev-tools:latest` | **Must be set.** Without it, "EE enabled" means the generic ADT image, not your EE. Use the digest [part 3](execution-environment-from-a-locked-requirements-file.md) pushed, not a tag |
| `ansible.executionEnvironment.pull.policy` | `missing` | `missing` pulls only when the image isn't present locally. With a digest that's exactly right: a new digest is a new image. With a `:latest` tag, `missing` never picks up updates. Other values: `always`, `never`, `tag` |
| `files.*Newline*`, `files.trimTrailingWhitespace` | off | VS Code core settings. Fixes, on save, the whitespace findings ansible-lint's YAML rules would otherwise report |

Two settings from Dworjan's workspace file are left out on purpose:
- **`"files.associations": {"*.yml": "ansible"}`** isn't needed and does harm. The extension already declares Ansible files by path: `playbooks/*.yml`, `*playbook*.yml`, `roles/**/main.yml`, `tasks/`, `handlers/`, `defaults/`, `vars/`, `meta/`, `group_vars/`, `host_vars/`, `molecule/*/molecule.yml`, plus `site.yml`, `requirements.yml`, `galaxy.yml` and `execution-environment.yml`. Mapping every `*.yml` would also lint `.github/workflows/*.yml` or a Compose file as Ansible. If a playbook sits outside those patterns, add that one path, such as `"deploy.yml": "ansible"`.
- **`ansible.python.interpreterPath`** (`"/usr/bin/python3.12"` in his file) depends on the machine. Its manifest scope is `machine-overridable`, meaning each machine is expected to set its own. Commit it only where the path is fixed, inside a Dev Container or Dev Spaces image.

## `.vscode/extensions.json`

```json
{
  "recommendations": ["redhat.ansible"]
}
```

On desktop VS Code this only suggests: per VS Code's docs, *"VS Code prompts a user to install the recommended extensions"* when the folder is opened. One entry is enough. The manifest makes `redhat.vscode-yaml`, `ms-python.python` and `ms-python.vscode-python-envs` dependencies (`extensionDependencies`), so installing `redhat.ansible` brings them. Add `redhat.vscode-redhat-account` only if the team uses Ansible Lightspeed, which signs in through it.

## How each environment from part 4 picks them up

- **Desktop VS Code and Remote-SSH:** `.vscode/settings.json` applies on opening the folder, and `extensions.json` produces the install prompt.
- **Dev Container:** the settings file applies the same way. To install extensions without a prompt, list them in `devcontainer.json` under `customizations.vscode.extensions`, as the scaffold in part 4 does.
- **Dev Spaces / Eclipse Che:** Dworjan's [Dev Spaces guide](https://github.com/shadowman-lab/Ansible-Development/blob/main/devspaces/README.md) relies on `.vscode/extensions.json` being installed automatically when a workspace starts, and on a `.code-workspace` file for the settings.

Once the EE is set, lint and completion come from the same image the playbook runs in under ansible-navigator, and in AAP.

## The example repository

The series' companion repository has both files, in [abdelhousni/ansible-development-environment-series](https://github.com/abdelhousni/ansible-development-environment-series/tree/main/06-vscode-ansible-settings-per-repository). There the EE setting names a real image, part 7's, instead of the placeholder above. A script there checks the settings against the extension itself:
- it downloads the released `redhat.ansible` 26.8.2 from Open VSX and checks the file's SHA-256;
- it reads the extension's `package.json`, and fails if a committed `ansible.*` setting doesn't exist, has the wrong type, or isn't one of the allowed values;
- it prints each setting next to its default, and checks that `site.yml` opens as an Ansible file without `files.associations`.

VS Code silently ignores a misspelled setting such as `ansible.validation.lintt.enabled`; the script fails on it. Its CI runs the script on every push.

## Sources

- The Ansible extension's manifest, [`package.json`](https://github.com/ansible/vscode-ansible/blob/main/package.json) in ansible/vscode-ansible at commit `509d149` (2026-09-29): every setting name, default, scope and enum value above, the `extensionDependencies`, and the `filenamePatterns` for the `ansible` language. Released version from Open VSX: 26.8.2.
- VS Code docs: [settings](https://code.visualstudio.com/docs/configure/settings) (precedence, and `.vscode` for workspace settings) and [workspace recommended extensions](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace) (the install prompt).
- Alex Dworjan: [Ansible VSCode Extension](https://www.youtube.com/watch?v=iI6cSvL87xY) (2022), [Dev Spaces with Execution Environments](https://www.youtube.com/watch?v=Kej_7MeoxmE) (2026), and his repository's [`.code-workspace`](https://github.com/shadowman-lab/Ansible-Development/blob/main/.code-workspace) and [`.vscode/extensions.json`](https://github.com/shadowman-lab/Ansible-Development/blob/main/.vscode/extensions.json).
