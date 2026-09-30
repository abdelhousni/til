# Ansible in OpenShift Dev Spaces: one workspace image, and your EE runs inside it

Tenth entry in the Ansible development environment series. [Part 4](where-to-run-an-ansible-dev-environment.md) introduced **OpenShift Dev Spaces**: Red Hat's product built on the upstream Eclipse Che project, which starts a browser-based VS Code per user, on demand, from a repository. Each repository describes its workspace container in a *devfile* (`devfile.yaml`). Part 4 also named the catch: until OpenShift 4.20, a workspace couldn't run containers, so it couldn't run your *execution environment* (EE, the container image AAP runs jobs in; [part 3](execution-environment-from-a-locked-requirements-file.md) builds one).

This part covers what changed and what a repository needs now. There was no OpenShift cluster to test on. What was checked:
- the Che operator's source and the `CheCluster` schema, for what the switch actually does;
- the devfiles and the `CheCluster` patch below, validated against their published schemas;
- the official workspace image, started under Docker with the same user, capabilities, devices and `/proc` setting the operator applies, running an EE through `ansible-navigator`.

## Before OpenShift 4.20: one workspace image per EE

In Alex Dworjan's [2023 Dev Spaces video](https://www.youtube.com/watch?v=Uccgi23livk), the workspace image *is* the EE. Each EE is rebuilt with a `.bashrc` and file permissions that work under the random user ID OpenShift assigns to pods, then named in the devfile. His repository keeps that recipe as `devspaces/olddevee`. With several EEs, each one has a second, Dev Spaces-specific image to rebuild and keep in step.

## From OpenShift 4.20: turn on container run

Nested containers rely on Linux *user namespaces*, where root inside a container maps to an unprivileged ID on the host; [this site's rootless Podman entry](../podman/root-vs-rootless-rhel10-ubuntu2604.md) explains them. OpenShift 4.20 can run a whole pod in its own user namespace. On that basis, Eclipse Che added a switch: the Che operator commit "feat: Nested containers" landed in October 2025 and first shipped in Che 7.111.0. Dworjan's README gives Dev Spaces 3.25 as the matching product version.

Dev Spaces is configured through one `CheCluster` *custom resource*, a Kubernetes object that the Dev Spaces operator reads and acts on. Enabling nested containers is one field, per the Che docs:

```sh
oc patch checluster/<name> -n <namespace> --type=merge \
  -p '{"spec":{"devEnvironments":{"disableContainerRunCapabilities":false}}}'
```

`oc get checluster -A` shows the name and namespace; upstream Che's docs use `eclipse-che` for both. The field defaults to `true`, and its schema description says it *"Can be enabled on OpenShift version 4.20 or later."* The earlier manual setup, a hand-written SecurityContextConstraint plus operator configuration, is no longer needed. Dworjan's March 2026 video and Chris Gruver's `ocp-4-20-nested-containers` repository both show that setup, and both now point to this field instead.

When the field is `false`, the operator applies the rest itself. Per its source and the `CheCluster` defaults:
- **A SecurityContextConstraint (SCC) named `container-run`.** An SCC is OpenShift's policy for what a pod may do. This one:
  - runs workspace containers as UID 1000;
  - requires the pod to have its own user namespace (`userNamespaceLevel: RequirePod`);
  - sets the SELinux type `container_engine_t`;
  - adds the `SETUID`, `SETGID` and `CHOWN` capabilities and drops `KILL` and `MKNOD`;
  - still forbids privileged containers.
- **Two devices for every workspace pod**, through the CRI-O annotation `io.kubernetes.cri-o.Devices: /dev/fuse,/dev/net/tun`. CRI-O is OpenShift's container runtime. `/dev/fuse` is needed by fuse-overlayfs, which [part 9](shared-dev-server-for-vscode-remote-ssh.md) explained. `/dev/net/tun` gives nested containers their network.
- **`procMount: Unmasked`** in the container security context. The schema explains why: it lets the container change its own sysctl settings to set up networking for nested containers. The pod's user namespace keeps that away from the host.

Two cautions:
- **Existing workspaces won't start afterwards.** The Che docs: *"Previously created workspaces can not be started after enabling this feature. Users will need to create new workspaces."*
- **GitOps.** Dworjan notes that when Argo CD or another GitOps tool manages the `CheCluster`, the operator adds security-context lines to it. His advice: patch the resource by hand first, then take the result into Git.

## The workspace image

Use the official image rather than building your own. `ghcr.io/ansible/ansible-devspaces` is built from the `devspaces/` folder of the ansible-dev-tools repository on every merge. The one from 2026-09-23 had:
- Red Hat Enterprise Linux 9.8 and Python 3.12.14;
- ADT 26.9.0 with ansible-core 2.21.4 ([part 5](ansible-development-tools-adt.md) covers ADT);
- Podman 5.8.2;
- UID 1000 as its default user, the UID the SCC forces.

Its entrypoint writes `/etc/subuid` from the pod's own user-namespace mapping at start-up, so rootless Podman gets whatever ID range OpenShift allotted. Dworjan's own `devspaces/Containerfile` installs ADT with `pip-3.11`, which part 5 showed now resolves to ansible-core 2.19.

In the test, the image ran as it would in a workspace:
- UID 1000, with `KILL` and `MKNOD` dropped;
- `/dev/fuse` and `/dev/net/tun` passed in;
- `/proc` unmasked, which is Docker's `--security-opt systempaths=unconfined`.

Inside it, a playbook run through `ansible-navigator` with an EE reported the EE's ansible-core, `2.21.3`, while the workspace's own tools were at 2.21.4. Each setting mattered:
- **Without the unmasked `/proc`,** the nested container failed with *"open `/proc/sys/net/ipv4/ping_group_range`: Read-only file system"*. That is the case the operator's `procMount: Unmasked` default covers.
- **Two adjustments were for Docker only.** With Docker's default security profiles, Podman couldn't create a user namespace (*"cannot clone: Operation not permitted"*), so the test turned off Docker's seccomp and AppArmor profiles. This sandbox also created the two devices readable by root only. OpenShift instead gives the pod its own user namespace and passes the devices through the CRI-O annotation, and neither of those could be tested here.

## What the repository commits

- **`devfile.yaml`**, naming the image by digest so every workspace gets the same tools:

  ```yaml
  schemaVersion: 2.3.0
  metadata:
    name: my-automation
  components:
    - name: ansible
      container:
        image: ghcr.io/ansible/ansible-devspaces@sha256:52de776aaa179689f7047f8a325affcb66cb923328e26bdf9ad0bc83741da066
        memoryRequest: 256M
        memoryLimit: 6Gi
        cpuRequest: 250m
        cpuLimit: 2000m
  ```

  It validates against the devfile 2.3.0 schema, as do Dworjan's devfile and the one in the ansible-dev-tools repository. The resource values are Dworjan's.
- **`ansible-navigator.yml`**, naming your EE by digest with `pull: policy: missing`, as in [part 7](develop-against-the-production-execution-environment.md). The workspace's Podman pulls it on first use. For a private registry, each user adds their login once under **User Preferences → Container Registries** in the Dev Spaces dashboard.
- **The editor settings and extensions** from [part 6](vscode-ansible-settings-per-repository.md). In this image `ansible.python.interpreterPath` can be committed, because the path is fixed: `/usr/bin/python3.12` exists and imports ansible-core 2.21.4 and ansible-lint.

## Sources

- Eclipse Che docs, "Enabling container run capabilities", in [eclipse-che/che-docs](https://github.com/eclipse-che/che-docs) at `1f4f0d5` (2026-09-30).
- The Che operator, [eclipse-che/che-operator](https://github.com/eclipse-che/che-operator) at `bac77e2` (2026-09-29):
  - `api/v2/checluster_types.go` for the field and its defaults, and `pkg/deploy/container-capabilities/container_run.go` for the SCC;
  - commit `dd0065d8` "feat: Nested containers" (2025-10-29), first in tag 7.111.0.
- The devfile 2.3.0 schema from [devfile/api](https://github.com/devfile/api), and the `ansible-devspaces` image source in [ansible/ansible-dev-tools](https://github.com/ansible/ansible-dev-tools) (`devspaces/`).
- Alex Dworjan:
  - [Dev Spaces for Ansible Development with Execution Environments](https://www.youtube.com/watch?v=Kej_7MeoxmE) (2026-03) and [Dev Spaces / Eclipse Che](https://www.youtube.com/watch?v=Uccgi23livk) (2023-12);
  - his repository's [devspaces/README.md](https://github.com/shadowman-lab/Ansible-Development/blob/main/devspaces/README.md) at `2e3ea6f`.
- Chris Gruver, [ocp-4-20-nested-containers](https://github.com/cgruver/ocp-4-20-nested-containers), for the manual setup the operator now does.
- Tested with the image `ghcr.io/ansible/ansible-devspaces` (digest `sha256:52de776a…`, built 2026-09-23) under Docker 29.3.1, with `ghcr.io/ansible-community/community-ee-base` as the EE.
