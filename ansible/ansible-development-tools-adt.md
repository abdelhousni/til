# Ansible Development Tools (ADT): one install, and the Python version decides what you get

Fifth entry in the Ansible development environment series. [Part 4](where-to-run-an-ansible-dev-environment.md) chose where the tools run; this one is about the tools themselves. **ADT** (Ansible Development Tools) is the PyPI package `ansible-dev-tools`. It's a *meta-package*: its own code is little more than an `adt` command, and its job is to depend on the rest of the toolchain, so one install brings all of it. Alex Dworjan [introduced it in May 2024](https://www.youtube.com/watch?v=qzi-oQ1dQL0) as the one install every environment should start from.

## What's in it

`adt --version` lists the tools. With ADT 26.9.0 on Python 3.13, on 2026-09-29:

| Tool | Version | What it does |
|---|---|---|
| ansible-core | 2.21.4 | The engine: `ansible-playbook`, `ansible-galaxy`, `ansible-doc` |
| ansible-navigator | 26.9.0 | Runs playbooks, by default inside an [execution environment](execution-environment-from-a-locked-requirements-file.md) (EE); also a text UI for browsing results and docs |
| ansible-builder | 3.1.1 | Builds EEs ([part 3](execution-environment-from-a-locked-requirements-file.md)) |
| ansible-creator | 26.9.0 | Scaffolds playbook projects, collections and EE projects |
| ansible-dev-environment (`ade`) | 26.9.0 | Creates a venv and installs collections with their Python dependencies |
| ansible-lint | 26.9.0 | Checks playbooks and roles against best-practice rules |
| molecule | 26.9.0 | Tests roles and collections against real targets, such as containers |
| ansible-sign | 0.1.6 | Signs a project's files with GPG so automation controller can verify them |
| pytest-ansible, tox-ansible | 26.9.0 | Run a collection's tests under pytest, and across Python and ansible-core versions with tox |

The install pulled in 69 packages in total.

## Three ways to install it

**From PyPI, in a venv.** A *venv* is a directory with its own Python and packages ([part 1](locking-an-ansible-dev-environment-pip-to-ee.md) compares the options). With uv:

```sh
uv venv --python 3.13 .venv
uv pip install ansible-dev-tools
```

`python3.13 -m venv .venv` followed by `.venv/bin/pip install ansible-dev-tools` does the same with plain pip.

**As a container image.** `ghcr.io/ansible/community-ansible-dev-tools` has ADT preinstalled, plus Podman for running EEs inside it. [Part 4](where-to-run-an-ansible-dev-environment.md) ran one as a Dev Container.

**As an RPM, with an AAP subscription.** Red Hat's AAP documentation installs it from the platform's repository, for example on RHEL 9:

```sh
sudo dnf install --enablerepo=ansible-automation-platform-2.5-for-rhel-9-x86_64-rpms ansible-dev-tools
```

The RPMs follow the versions Red Hat supports for that AAP release, not the latest on PyPI.

## The Python you install with decides the ansible-core you get

ADT 26.9.0 declares `requires-python >=3.11`. But each ansible-core release has its own Python range ([part 2](pinning-ansible-core-pip-tools-uv-poetry.md) has the table), and pip quietly picks the newest release that fits. Resolving `ansible-dev-tools` with `uv pip compile --python-version` for each interpreter:

| Python | ADT resolved | ansible-core resolved | ansible-core status |
|---|---|---|---|
| 3.9 | none: *"No solution found"* | none | — |
| 3.10 | 25.10.0 | 2.16.19 | end of life since July 2025 |
| 3.11 | 26.9.0 | 2.19.13 | end of life in November 2026 |
| 3.12, 3.13, 3.14 | 26.9.0 | 2.21.4 | current |

Two of these rows install without a single warning:
- **Python 3.10** falls back to an older ADT, 25.10.0, and to ansible-core 2.16. 2.17 would also support 3.10, but ansible-lint and Molecule both declare `ansible-core!=2.17.*`, and 2.18 and later need Python 3.11.
- **Python 3.11** gets the current ADT, but ansible-core stops at 2.19, because 2.20 and 2.21 need Python 3.12.

This bites on RHEL, whose system `python3` is 3.9 on RHEL 9. Dworjan's own [Dev Spaces image](https://github.com/shadowman-lab/Ansible-Development/blob/main/devspaces/Containerfile) installs ADT with `pip-3.11`, so rebuilt today it would get ansible-core 2.19. Install with Python 3.12 or later. [This site's uv entry](../python/newer-python-with-uv-without-touching-system-python-rhel.md) gets one on RHEL without touching the system Python.

## ADT sets floors, not pins

Every dependency of ADT is a lower bound: `ansible-lint>=26.4.0`, `ansible-navigator>=26.1.3`, `molecule>=26.3.0`, and so on. Installing `ansible-dev-tools==26.9.0` next month can bring newer tools than the table above. To make two machines match, lock the environment as in [part 2](pinning-ansible-core-pip-tools-uv-poetry.md): compile `ansible-dev-tools==26.9.0` into a lock file, which here held 69 pinned packages.

## What it doesn't include

- **A container engine.** ansible-navigator runs playbooks inside an EE by default. With no Podman on the machine, `ansible-navigator run --ce podman` stops with *"The specified container engine could not be found: 'podman'"*. Install Podman or Docker separately, or pass `--ee false` to use the venv's own ansible-core.
- **An activated venv for `--ee false`.** Navigator then looks for `ansible-playbook` on `PATH`. It failed until the venv's `bin/` was on `PATH`, and ran once it was.
- **Collections.** ADT ships ansible-core, not the `ansible` package's collections. `ade` or `ansible-galaxy` installs them.

The `adt` command itself has one subcommand, `adt server`, which its help describes as starting "the Ansible Devtools server" on port 8000.

## The example repository

The series' companion repository reproduces this entry, in [abdelhousni/ansible-development-environment-series](https://github.com/abdelhousni/ansible-development-environment-series/tree/main/05-ansible-development-tools-adt):
- **`resolve-by-python.sh`** prints the per-Python table above. It passes uv's `--exclude-newer 2026-09-30T00:00:00Z`, which makes uv ignore anything uploaded to PyPI after that moment. So the table comes out the same after new releases.
- **`requirements.txt`** is the lock: `ansible-dev-tools==26.9.0` compiled for Python 3.13 into 69 pinned packages. Each carries hashes, as in [part 1](locking-an-ansible-dev-environment-pip-to-ee.md).
- **`site.yml`** is run with `ansible-navigator --ee false`, which shows the `PATH` requirement above.

Its CI checks all three on every push:
- the script's output must match the table;
- rerunning `uv pip compile` must leave the lock unchanged;
- after installing the lock, `adt --version` must show ansible-core 2.21.4 and ansible-lint 26.9.0;
- navigator must fail with `ansible: not found` when `PATH` has no `ansible`, and print `ansible-core 2.21.4` when `PATH` holds the venv's `bin/`.

## Sources

- Alex Dworjan, [Ansible Developer Environment Updates](https://www.youtube.com/watch?v=qzi-oQ1dQL0) (2024-05), and his [Dev Spaces Containerfile](https://github.com/shadowman-lab/Ansible-Development/blob/main/devspaces/Containerfile).
- [ADT documentation](https://ansible.readthedocs.io/projects/dev-tools/), and the `ansible-dev-tools` 26.9.0 metadata on PyPI (`requires_python`, `requires_dist`).
- Red Hat AAP 2.5 docs, [Installing Ansible development tools](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html/developing_automation_content/installing-devtools) (the `dnf` commands).
- ansible-core support dates: Ansible's [release and maintenance](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html) page.
- Tested with uv 0.12.20: `adt --version`, the per-Python resolutions, the navigator runs, and `adt server --help`.
