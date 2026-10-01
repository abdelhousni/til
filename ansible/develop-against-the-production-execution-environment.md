# Running playbooks locally in the execution environment production uses

Seventh entry in the Ansible development environment series. [Part 6](vscode-ansible-settings-per-repository.md) pointed the editor at the team's *execution environment* (EE), the container image that AAP (Red Hat Ansible Automation Platform) and its automation controller run every job in. This part does the same for the terminal. The aim is Alex Dworjan's rule: run the playbook locally, in that same image, before pushing, rather than pushing, syncing the project in controller, and finding out there.

The tool is `ansible-navigator`, part of [ADT](ansible-development-tools-adt.md). By default it runs `ansible-playbook` *inside* an EE instead of on the host. Everything below was run with ansible-navigator 26.9.0 and Docker against the public `ghcr.io/ansible-community/community-ee-base` image. That image carries ansible-core 2.21.3 and three collections: `ansible.posix`, `ansible.utils` and `ansible.windows`.

## Commit an `ansible-navigator.yml`

Navigator reads `ansible-navigator.yml` from the project directory, so the choice of image travels with the repository:

```yaml
---
ansible-navigator:
  execution-environment:
    enabled: true
    container-engine: auto
    image: ghcr.io/ansible-community/community-ee-base@sha256:9f2836592ab92794e8b1982311d504ba3c28a2c09b3f8de221ca3564842c0902
    pull:
      policy: missing
    environment-variables:
      pass:
        - DEMO_TOKEN
  mode: stdout
  playbook-artifact:
    enable: false
```

- **`image`** is the EE, by digest, as in [part 3](execution-environment-from-a-locked-requirements-file.md). It's the same value as the editor's `ansible.executionEnvironment.image` in part 6.
- **`container-engine: auto`** tries Podman first, then Docker. On this machine, with no Podman, `ansible-navigator settings --effective` showed it resolved to `docker`.
- **`pull.policy: missing`** pulls only when the image isn't there yet. With a digest, a new version is a new reference, so nothing goes stale.
- **`environment-variables.pass`** lists the host variables the container may see (below).
- **`mode: stdout`** prints plain `ansible-playbook` output instead of navigator's interactive text UI.
- **`playbook-artifact.enable: false`** turns off the JSON record navigator otherwise saves after every run. The default is `true`, which writes `where-artifact-<timestamp>.json` into the project directory. Keep it on, and ignore the files in `.gitignore`, if you want to replay runs.

## What runs where

A playbook that prints where it is:

```yaml
- hosts: localhost
  gather_facts: false
  tasks:
    - ansible.builtin.debug:
        msg:
          - "ansible-core {{ ansible_version.full }}"
          - "playbook_dir {{ playbook_dir }}"
          - "config {{ ansible_config_file }}"
          - "DEMO_TOKEN={{ lookup('ansible.builtin.env', 'DEMO_TOKEN') | default('unset', true) }}"
          - "OTHER_VAR={{ lookup('ansible.builtin.env', 'OTHER_VAR') | default('unset', true) }}"
```

Run with `DEMO_TOKEN=abc123 OTHER_VAR=xyz ansible-navigator run where.yml`:

```text
"ansible-core 2.21.3",
"playbook_dir <project>",
"config <project>/ansible.cfg",
"DEMO_TOKEN=abc123",
"OTHER_VAR=unset"
```

- **The version is the EE's.** The host venv had ansible-core 2.21.4; the playbook reported 2.21.3, the image's.
- **The project is mounted at the same path.** `playbook_dir` was the host path, and the project's `ansible.cfg` applied, with its inventory.
- **The host environment isn't.** Only `DEMO_TOKEN`, listed under `pass`, reached the playbook. Cloud credentials, proxy settings and tokens have to be listed there, or given per run with `--penv NAME`. Controller injects its own credentials instead, so a variable that works locally only because your shell has it would be missing there.

## The EE decides which collections exist

The same image has no `community.general`. A playbook using `community.general.json_query` failed in the EE with:

```text
No filter named 'community.general.json_query'.
```

That's the useful failure: it's the one controller would give. There's one way to hide it locally. Ansible also loads collections from a `collections/` directory next to the playbook. After `ansible-galaxy collection install community.general -p ./collections`, the same run found the filter, and `ansible-navigator collections --mode stdout` listed `community.general 13.4.0` from the project beside the EE's three. But it failed one step later:

```text
You need to install "jmespath" prior to running json_query filter
```

A collection copied into the project brings its code, not its Python dependencies. The EE has no `jmespath`, and the host venv's copy doesn't count. AWX's docs describe the controller-side equivalent: *"If you specify a collections requirements file in SCM at `collections/requirements.yml` of a project, then AWX will install collections from that file"* when the project updates. That installs collections only, into the job, so the same missing-library error would follow. A collection that needs Python libraries belongs in the EE, where ansible-builder installs its requirements too (part 3).

## Before pushing

1. **`ansible-navigator collections --mode stdout`** shows what the EE, plus anything in `./collections`, actually provides.
2. **`ansible-navigator run site.yml --check`** runs in the production image against a test inventory. `--check` is Ansible's dry run.
3. **Push when it passes.** What's left to differ in controller is what the EE can't reproduce: controller's inventory, credentials and survey answers.

In the editor, Dworjan notes that the first time the Ansible extension switches to an EE, it pulls the image and copies its plugin docs. Highlighting may need a window reload to catch up.

## The example repository

The series' companion repository has this project, in [abdelhousni/ansible-development-environment-series](https://github.com/abdelhousni/ansible-development-environment-series/tree/main/07-develop-against-the-production-execution-environment): `ansible-navigator.yml`, `ansible.cfg`, `where.yml` and the `json_query` playbook. Its CI installs ansible-navigator 26.9.0 and repeats each run above on every push:
- `where.yml` must report the EE's ansible-core 2.21.3, the project's `ansible.cfg`, `DEMO_TOKEN=abc123` and `OTHER_VAR=unset`;
- the `json_query` playbook must fail with the missing filter;
- after `community.general` 13.4.0 is installed into `./collections`, it must fail with the `jmespath` message.

On GitHub's runner, which has both Podman and Docker, `container-engine: auto` picked Podman, and the results were the same.

## Sources

- Alex Dworjan: [Ansible Development Environment Options](https://www.youtube.com/watch?v=SWa8bPLteAA) (2024), [Dev Containers](https://www.youtube.com/watch?v=kOGs6Ntt8JY) (2024) and [Dev Spaces with Execution Environments](https://www.youtube.com/watch?v=Kej_7MeoxmE) (2026), and his [ansible-navigator.yml template](https://github.com/shadowman-lab/Ansible-Development/blob/main/roles/shadowman_dev_server/templates/ansible-navigator.yml.j2).
- `ansible-navigator run --help` (26.9.0): `--penv`, and `--pae` *"(default: true)"*.
- AWX `docs/collections.md`, "Project Collections Requirements", in [ansible/awx](https://github.com/ansible/awx).
- Every output above came from ansible-navigator 26.9.0 with Docker 29.3.1 and `ghcr.io/ansible-community/community-ee-base` (digest `sha256:9f283659…`, built 2026-08-21).
