# An Ansible Dev Container: choosing the scaffolded config, Podman, and the EE navigator falls back to

Eighth entry in the Ansible development environment series. [Part 4](where-to-run-an-ansible-dev-environment.md) listed the Dev Container as the local, zero-install option, and showed it can run an *execution environment* (EE) inside it. This part sets one up for real. A *Dev Container* is a container that VS Code, through Microsoft's **Dev Containers** extension, opens a project in: the editor's server, the extensions and every tool run inside, and the laptop only provides Docker or Podman. The configuration is a `devcontainer.json` file in the repository.

Everything below was run with the Dev Container spec's command-line implementation, `@devcontainers/cli` 0.89.0, on Docker 29.3.1. That's the same configuration VS Code reads, started without the editor.

## Three files from ansible-creator

`ansible-creator init playbook` (26.9.0) generates three configurations. They all use the public ADT image, `ghcr.io/ansible/community-ansible-dev-tools`, which [part 5](ansible-development-tools-adt.md) described:

| File | For |
|---|---|
| `.devcontainer/devcontainer.json` | GitHub Codespaces; the same content as the Docker one apart from the name |
| `.devcontainer/docker/devcontainer.json` | Docker Desktop or Docker Engine |
| `.devcontainer/podman/devcontainer.json` | Podman |

The spec allows exactly this layout. It lists `.devcontainer/devcontainer.json` first, then `.devcontainer/<folder>/devcontainer.json` *"(where <folder> is a sub-folder, one level deep)"*, and asks tools to *"consider providing a mechanism for users to select one"* when several exist. The CLI takes the one you name with `--config`.

## Starting it

```sh
npm install -g @devcontainers/cli
devcontainer up --workspace-folder . --config .devcontainer/docker/devcontainer.json
devcontainer exec --workspace-folder . --config .devcontainer/docker/devcontainer.json adt --version
```

After `up`:
- the project was mounted at `/workspaces/<folder name>`;
- the shell ran as `root`, because the file sets `"containerUser": "root"`;
- `adt --version` listed ansible-core 2.21.4 and the ADT tools at 26.9.0;
- Podman 5.8.7 was available inside, for EEs.

This sandbox's kernel refused one of the file's flags, `--cap-add=SYS_RESOURCE` (*"invalid CapAdd: capability not supported by your kernel"*), so the test ran on a copy without it. On an ordinary Docker Desktop or Linux host, the file works as generated.

## With Podman instead of Docker

The extension calls `docker` unless told otherwise. Its manifest documents `dev.containers.dockerPath` as *"Docker (or Podman or WSLc) executable name or path"*. So, in **user** settings:

```json
{
  "dev.containers.dockerPath": "podman",
  "dev.containers.dockerComposePath": "podman-compose"
}
```

Both settings have the scope `application`, which means they can't go in a repository's `.vscode/settings.json` (part 6). Each developer sets them once. Dworjan's [Dev Containers video](https://www.youtube.com/watch?v=kOGs6Ntt8JY) does this. He creates his Podman machine without root privileges, which he says isn't needed.

Then pick `.devcontainer/podman/devcontainer.json`. Compared with the Docker file, it adds a few `runArgs`:
- `--cap-add=CAP_MKNOD` and `--cap-add=NET_ADMIN`;
- `--security-opt unmask=/sys/fs/cgroup`, which unmasks the cgroup filesystem inside the container;
- `--userns=host`, which runs the container in the host's user namespace.

It also drops `"updateRemoteUserUID": true`.

## The EE navigator uses unless you name one

The scaffold's `ansible-navigator.yml` sets logging and artifacts but **no image**. Inside the Dev Container, `ansible-navigator settings --effective` showed what that means:

```text
Execution environment image name:     ghcr.io/ansible/community-ansible-dev-tools:latest
```

The default EE is the ADT image itself, the 2 GB tools image, run nested inside the container that already is that image. Navigator's default pull policy is `tag`: *"if the image tag is 'latest', always pull the image"*. So every run checks the registry for it again.

Set your own EE in `ansible-navigator.yml`, by digest, with `pull: policy: missing`, as in [part 7](develop-against-the-production-execution-environment.md). Loaded into the Dev Container's Podman and named with `--eei`, a small EE ran a playbook that reported the EE's ansible-core, 2.21.3, while the container's own tools were at 2.21.4. In this test, nested Podman stored it with the `vfs` driver, which keeps full copies of every layer. Leave room for EEs inside the container.

## Pin the Dev Container image too

`"image": "ghcr.io/ansible/community-ansible-dev-tools:latest"` gives each developer whichever ADT was newest when their container was built. For everyone to get the same tools, use the digest instead. On 2026-09-29 it was:

```json
"image": "ghcr.io/ansible/community-ansible-dev-tools@sha256:775c81d53058009dd47b97872f4a86d3b0a9ce16ad9af3cc48514ce4197aa787"
```

Moving to a newer one is then a reviewed one-line change. AAP subscribers can use Red Hat's supported ADT image from `registry.redhat.io` instead, after a `podman login` with their Red Hat account, as Dworjan does.

## The example repository

The series' companion repository has these files, in [abdelhousni/ansible-development-environment-series](https://github.com/abdelhousni/ansible-development-environment-series/tree/main/08-ansible-dev-container-with-adt). There are two commits:
- **the first** holds the three `devcontainer.json` files and `ansible-navigator.yml` exactly as ansible-creator generates them;
- **the second** pins the ADT image by digest, names the EE from part 7 by digest with `pull: policy: missing`, and adds a playbook. `git show` on it lists those changes.

VS Code looks for `.devcontainer/` at the root of the folder it opens, so open that directory rather than the whole repository. Its CI starts the Docker configuration with `@devcontainers/cli` 0.89.0, installed from a committed lock file, on every push. It then checks three things:
- `adt --version` inside reports ansible-core 2.21.4;
- navigator's effective EE is the pinned image;
- the playbook, run in that EE nested inside the Dev Container, reports ansible-core 2.21.3.

## Sources

- The Dev Container spec, [devcontainer.json locations](https://containers.dev/implementors/spec/), and [`@devcontainers/cli`](https://github.com/devcontainers/cli) 0.89.0.
- The Dev Containers extension's manifest (`ms-vscode-remote.remote-containers` 0.470.0): the `dev.containers.dockerPath` and `dockerComposePath` settings, their descriptions and their `application` scope.
- `ansible-creator init playbook` 26.9.0 for the three `devcontainer.json` files and `ansible-navigator.yml`; `ansible-navigator run --help` for the pull policies.
- Alex Dworjan, [Ansible Dev Server using VSCode Dev Containers](https://www.youtube.com/watch?v=kOGs6Ntt8JY) (2024-10), and Red Hat's AAP 2.5 docs, [installing Ansible development tools](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html/developing_automation_content/installing-devtools).
