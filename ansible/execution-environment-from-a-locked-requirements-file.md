# Building an Ansible execution environment from a locked requirements file

Third entry in the Ansible development environment series. An *execution environment* (EE) is a container image holding the whole Ansible runtime: ansible-core, [ansible-runner](pinning-ansible-core-pip-tools-uv-poetry.md), Python packages, collections and system packages. [The first entry](locking-an-ansible-dev-environment-pip-to-ee.md) ranks it against the venv-based options. AWX and Red Hat's Ansible Automation Platform (AAP) run their jobs inside one.

`ansible-builder` builds an EE from `execution-environment.yml`. It installs whatever that file and the files it references ask for. So an EE is reproducible only if every input is pinned. Tested with ansible-builder 3.1.1 and Docker, on 2026-09-29.

## A typical first definition, and what it actually builds

```yaml
---
version: 3
images:
  base_image:
    name: quay.io/fedora/fedora:latest
dependencies:
  ansible_core:
    package_pip: ansible-core==2.15.9
  ansible_runner:
    package_pip: ansible-runner
  galaxy: requirements.yml          # community.general, no version
  python: requirements.txt
  system: bindep.txt
```

ansible-builder uses Podman when it's installed and Docker otherwise; `--container-runtime` picks one explicitly. `ansible-builder build -t my-ee:2.15.9` fails:

```text
/usr/bin/python3 is not an executable
```

The Fedora container image has no Python. Ansible's own example declares one, and with this added the build succeeds:

```yaml
  python_interpreter:
    package_system: python3
```

The image then has three problems that no error reports:
- **`fedora:latest` was Fedora 44, with Python 3.14.** ansible-core 2.15 supports control-node Python 3.9 to 3.11. `ansible localhost -m ping` still worked; nothing checks the range.
- **The collection floated to the newest release.** `community.general` came in at 13.4.0, whose `meta/runtime.yml` says `requires_ansible: '>=2.18.0'`. Using it only printed a warning: `Collection community.general does not support Ansible version 2.15.9`.
- **ansible-core 2.15 has been end of life since November 2024.** [The pinning entry](pinning-ansible-core-pip-tools-uv-poetry.md) covers ansible-core's release cycle.

Rebuild next month and `latest`, the collection and every unpinned Python package can all change.

## A locked definition

```yaml
---
version: 3

images:
  base_image:
    name: quay.io/fedora/fedora:44@sha256:8938dce2600de0b78f5ef8d1541192f207fdafb7414d83957f6687147aa8998b

dependencies:
  python_interpreter:
    package_system: python3
    python_path: /usr/bin/python3
  ansible_core:
    package_pip: ansible-core==2.21.4
  ansible_runner:
    package_pip: ansible-runner==2.4.3
  python: requirements.txt
  galaxy: requirements.yml
  system: bindep.txt
```

Each input is pinned:

**The base image, by digest.** A tag such as `44` can be re-pushed; the `@sha256:` digest names one exact image. `docker inspect --format '{{index .RepoDigests 0}}' quay.io/fedora/fedora:44` prints it after a pull.

**ansible-core and ansible-runner, with `==`.** ansible-core 2.21 supports Python 3.12 to 3.14, which includes Fedora 44's 3.14.

**Python packages, from a lock compiled for the image's Python.** The top-level wishes go in `requirements.in`:

```text
ansible-core~=2.21.0
ansible-runner~=2.4.0
jmespath                 # for community.general.json_query
```

Compile it for the EE's Python and platform, not your laptop's:

```sh
uv pip compile requirements.in --python-version 3.14 --python-platform linux -o requirements.txt
```

`pip-compile` works too, run inside the base image so it sees Python 3.14. With a `uv.lock` project, `uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt` gives the same list. Leave hashes out: ansible-builder expects [PEP 508](https://peps.python.org/pep-0508/) lines, and passes anything else to pip as *"undefined and unsupported behavior"*.

**Collections, with `==`, including their dependencies.** `ansible-galaxy` has no lock file, and a collection's own dependencies float unless you list them:

```yaml
collections:
  - name: community.general
    version: "==13.4.0"
  - name: community.library_inventory_filtering_v1   # community.general's dependency
    version: "==1.1.5"
```

**System packages** go in `bindep.txt`. *bindep* is a format for listing system packages per platform, here one line: `openssh-clients [platform:rpm]`. These come from the distribution's repositories at build time, so they're the one layer a rebuild can still change. The base digest fixes everything already in the image.

## Checking that the image matches the lock

After the build, `pip list --format=freeze` inside the image matched `requirements.txt` line for line. The only extras were `dumb-init`, which ansible-builder adds pinned, and `pip`. The collections were exactly 13.4.0 and 1.1.5, and `community.general.json_query` worked.

ansible-builder installs `ansible-core==2.21.4 ansible-runner==2.4.3` first, which pulls ansible-core's own dependencies unpinned. It then installs the requirements file in a later stage. To check that the lock wins, I locked Jinja2 at 3.1.5, one release behind, and rebuilt: the image had Jinja2 3.1.5. Any dependency the lock names ends up at the locked version.

ansible-builder merges your `requirements.txt` with the `requirements.txt` of every collection it installs. It skips a fixed list of names from collections, including `ansible-core` and test tools such as `pytest` and `molecule`. `dependencies.exclude` (ansible-builder 3.1+) drops others.

## Tag, push, and reference by digest

```sh
ansible-builder build -t my-ee:2.21.4
podman tag my-ee:2.21.4 registry.example.com/ansible/my-ee:2.21.4
podman push registry.example.com/ansible/my-ee:2.21.4
```

The push produces a digest, `registry.example.com/ansible/my-ee@sha256:…`. Put that digest in AAP and in local runs, rather than the tag, which can be pushed again. A CI job can tag each build with the version and commit ID, but the digest is what pins the image.

`ansible-navigator`, the command-line runner for EEs, runs a playbook in the same image locally:

```sh
ansible-navigator run site.yml --eei registry.example.com/ansible/my-ee@sha256:… --mode stdout
```

Tested against a local registry, with `--ce docker`. A playbook calling `community.general.json_query` printed `"msg": "2.21.4 / 2"`: the image's ansible-core, and the jmespath dependency working.

## Sources

- [ansible-builder definition reference](https://ansible.readthedocs.io/projects/builder/en/stable/definition/) (the `python`, `python_interpreter` and `exclude` keys, and the PEP 508 note) and [collection metadata](https://ansible.readthedocs.io/projects/builder/en/stable/collection_metadata/) (merging and excluded names). Read from the 3.1.1 sdist, along with its generated `Dockerfile` and scripts.
- Ansible docs, [building your first EE](https://docs.ansible.com/projects/ansible/latest/getting_started_ee/build_execution_environment.html), from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation). Its example adds `python_interpreter` to a Fedora base.
- [uv `pip compile`](https://docs.astral.sh/uv/pip/compile/) and [`uv export`](https://docs.astral.sh/uv/concepts/projects/export/).
- Every output above was produced here with ansible-builder 3.1.1, ansible-navigator 26.9.0, uv 0.12.20, Docker 29.3.1 and a local `registry:2`. The test builds added this sandbox's proxy CA to the image's trust store, a test-only step left out of the listings.
