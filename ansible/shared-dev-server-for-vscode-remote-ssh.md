# A shared Ansible dev server for VS Code Remote-SSH, built with Ansible

Ninth entry in the Ansible development environment series. [Part 4](where-to-run-an-ansible-dev-environment.md) listed Remote-SSH as the option for shops that only have VMs: VS Code stays on the laptop, and the code, the tools and the *execution environments* (EEs, the container images that Red Hat Ansible Automation Platform runs jobs in; [part 3](execution-environment-from-a-locked-requirements-file.md) builds one) live on a Linux server that developers reach over SSH. On the first connection, the Remote-SSH extension installs the **VS Code Server** into the user's home directory, `~/.vscode-server`, and extensions such as Red Hat's Ansible extension run there.

This part builds that server with a playbook: Podman, one shared install of ADT (the Ansible Development Tools package from [part 5](ansible-development-tools-adt.md)), and one shared copy of the EE. It follows Alex Dworjan's two roles, `shadowman_dev_vs_codeserver` and `shadowman_dev_shared_image_store`, updated where testing showed they needed it. Everything below ran from ansible-core 2.21.4 against Rocky Linux 9.8, a RHEL 9 rebuild, booted with systemd, with Podman 5.8.2 and developers logging in over SSH.

## The playbook

```yaml
---
- name: Shared Ansible development server for VS Code Remote-SSH
  hosts: devservers
  become: true
  vars:
    dev_users: [alice, bob]
    adt_venv: /opt/adt
    shared_image_store: /var/lib/ee-shared
    ee_image: ghcr.io/ansible-community/community-ee-base@sha256:9f2836592ab92794e8b1982311d504ba3c28a2c09b3f8de221ca3564842c0902

  tasks:
    - name: Install Podman, fuse-overlayfs, git, Python 3.12, and packaging for the pip module
      ansible.builtin.dnf:
        name: [podman, fuse-overlayfs, git, python3.12, python3-packaging]
        state: present

    - name: Copy the ADT lock file
      ansible.builtin.copy:
        src: adt-requirements.txt
        dest: /opt/adt-requirements.txt
        mode: "0644"

    - name: Install the locked ADT into one venv for everyone
      ansible.builtin.pip:
        requirements: /opt/adt-requirements.txt
        virtualenv: "{{ adt_venv }}"
        virtualenv_command: python3.12 -m venv
        extra_args: --require-hashes

    - name: Put the venv on every login shell's PATH
      ansible.builtin.copy:
        dest: /etc/profile.d/adt.sh
        content: |
          case ":$PATH:" in
            *":{{ adt_venv }}/bin:"*) ;;
            *) PATH="{{ adt_venv }}/bin:$PATH" ;;
          esac
        mode: "0644"

    - name: Create the shared image store
      ansible.builtin.file:
        path: "{{ shared_image_store }}"
        state: directory
        mode: "0755"

    - name: Check whether the EE is already in the shared store
      ansible.builtin.command: podman --root {{ shared_image_store }} image exists {{ ee_image }}
      register: ee_present
      changed_when: false
      failed_when: ee_present.rc > 1

    - name: Pull the EE into the shared store
      ansible.builtin.command: podman --root {{ shared_image_store }} pull {{ ee_image }}
      when: ee_present.rc == 1
      changed_when: true

    - name: Make the shared store readable by every developer
      ansible.builtin.file:
        path: "{{ shared_image_store }}"
        mode: a+rX
        recurse: true

    - name: Check each developer has subordinate IDs for rootless Podman
      ansible.builtin.command: getsubids {{ item }}
      changed_when: false
      loop: "{{ dev_users }}"

    - name: Keep each developer's user services running between SSH sessions
      ansible.builtin.command: loginctl enable-linger {{ item }}
      args:
        creates: /var/lib/systemd/linger/{{ item }}
      loop: "{{ dev_users }}"

    - name: Create each developer's Podman and VS Code Server config folders
      ansible.builtin.file:
        path: /home/{{ item.0 }}/{{ item.1 }}
        state: directory
        owner: "{{ item.0 }}"
        group: "{{ item.0 }}"
        mode: "0700"
      loop: "{{ dev_users | product(['.config', '.config/containers', '.vscode-server', '.vscode-server/data', '.vscode-server/data/Machine']) }}"

    - name: Give each developer's rootless Podman the shared store, read-only
      ansible.builtin.copy:
        dest: /home/{{ item }}/.config/containers/storage.conf
        content: |
          [storage]
          driver = "overlay"

          [storage.options]
          additionalimagestores = ["{{ shared_image_store }}"]
          mount_program = "/usr/bin/fuse-overlayfs"
        owner: "{{ item }}"
        group: "{{ item }}"
        mode: "0644"
      loop: "{{ dev_users }}"

    - name: Point the Ansible extension at the shared venv
      ansible.builtin.copy:
        dest: /home/{{ item }}/.vscode-server/data/Machine/settings.json
        content: '{ "ansible.python.interpreterPath": "{{ adt_venv }}/bin/python" }'
        owner: "{{ item }}"
        group: "{{ item }}"
        mode: "0644"
        force: false
      loop: "{{ dev_users }}"
```

It passes ansible-lint 26.9.0 at the `production` profile. A second run reported `changed=0`.

## One locked ADT, on Python 3.12

Dworjan's role installs ADT for each user with `pip3.11 --user`. As [part 5](ansible-development-tools-adt.md) showed, Python 3.11 now resolves ADT to ansible-core 2.19, which reaches end of life in November 2026. RHEL 9's AppStream repository has Python 3.12 (3.12.14 on 9.8), which gets the current 2.21.

The playbook installs ADT once, into a *venv* (a directory with its own Python and packages) at `/opt/adt`, from a lock file made as in [part 2](pinning-ansible-core-pip-tools-uv-poetry.md):

```sh
echo 'ansible-dev-tools==26.9.0' > requirements.in
uv pip compile --python-version 3.12 --python-platform x86_64-manylinux_2_34 \
  --generate-hashes requirements.in -o adt-requirements.txt
```

*Wheels* are PyPI's pre-built packages, and their `manylinux_2_NN` tag names the oldest glibc, the GNU C library, they need. `manylinux_2_34` matches RHEL 9's glibc 2.34, so uv picks wheels that run there. The file pinned 69 packages, including ansible-core 2.21.4. Everyone on the server gets the same versions, and an upgrade is a new lock file and one more run. Two details came from the test runs:
- **The `pip` module needs the `packaging` library in the server's system Python.** The first run stopped with *"Failed to import the required Python library (packaging) on devsrv's Python /usr/bin/python3"*. The `python3-packaging` package fixes it.
- **The `case` guard in `adt.sh` keeps the venv on `PATH` once.** Without it, an SSH login shell had `/opt/adt/bin` on its `PATH` twice.

## A shared image store for the EE

*Rootless* Podman runs containers as the developer, and keeps each user's images under their home directory. [This site's rootless entry](../podman/root-vs-rootless-rhel10-ubuntu2604.md) explains how. Fifteen developers means fifteen copies of the same EE. An *additional image store* avoids that: a read-only store that Podman searches besides the user's own. Root pulls the EE into it once with `podman --root`, and every user's Podman reads it from there.

Three things were needed before a developer's EE would run from it:
1. **Read permission.** Podman created the store's folders as `0700`, root only. A user's Podman then failed with *"open /var/lib/ee-shared/overlay-images/images.lock: permission denied"*. Dworjan's role runs `chmod -R a+rx` after each pull, and the playbook does the same with `mode: a+rX`. It adds read and search permission without removing any other bits.
2. **A per-user `storage.conf`.** Adding the store to `/etc/containers/storage.conf` had no effect for rootless users: `podman info` as a user showed no additional store. Podman's storage man page, on its main branch, lists a directory for all rootless users at once, `/etc/containers/storage.rootless.conf.d/`, but Podman 5.8.2 ignored it too. A `~/.config/containers/storage.conf` for each user, as in Dworjan's role, worked.
3. **fuse-overlayfs.** Podman normally builds a container's filesystem with the kernel's *overlay* filesystem, which stacks the image's read-only layers under a writable one. With the shared store, every container failed before starting: *"creating temporary passwd file for container … /etc/passwd: permission denied"*. The layers belong to the host's root, which isn't mapped into the developer's user namespace, so inside the container they're owned by `nobody` (UID 65534), and even the container's root can't change them. `mount_program = "/usr/bin/fuse-overlayfs"`, the line Dworjan's template also has, mounts the layers through *fuse-overlayfs* instead: the same stacking, implemented as a user-space program. With it, the containers ran.

The result, as Alice, using part 7's `ansible-navigator.yml` with `pull: policy: missing`:
- **`ansible-navigator run`** used the EE from the shared store and reported its ansible-core, `2.21.3`. Alice's own image storage stayed at 196 KB.
- **Carol**, a user without the shared store, needed her own copy of the image: 483 MB.
- **The Ansible extension's EE mode** was checked by running its `podman run` flags, taken from the extension's language server source, with `ansible-playbook --syntax-check`. It passed with the shared store too. Unlike navigator, those flags run the image's own user, not root.

One difference remains. The EE's home directory `/runner` also shows as owned by `nobody`, so the image's *entrypoint*, the script that starts every container, set `HOME=/tmp` instead. `ansible-navigator` isn't affected: it mounts its own writable `/runner`.

If the EE comes from a registry that needs a login, don't copy Dworjan's `podman pull --creds=USER:PASS`. On a shared server, any user can read another process's command line with `ps`. Log in first, with `podman login` or the `containers.podman.podman_login` module and `no_log: true`.

## Subordinate IDs and lingering

Rootless Podman maps a range of *subordinate* user and group IDs, reserved per user in `/etc/subuid` and `/etc/subgid`, into each container. `useradd` reserved one range per local user: `alice:100000:65536` and `bob:165536:65536`. Users who come from a directory, such as LDAP or Red Hat Identity Management (IdM), don't get one that way. To test, Dave's entries were removed:
- `getsubids dave` answered *"Error fetching ranges"*. The playbook's check task fails on it, which is the point: better at provisioning time than in a developer's first `podman run`.
- Podman itself logged *"no subuid ranges found for user "dave" in /etc/subuid"* and fell back to *"rootless single mapping into the namespace. This might break some images."*

For local users, `usermod --add-subuids` adds a range. For directory users, Podman's rootless tutorial notes that shadow-utils 4.9 and later, the version RHEL 9 has, can read them from SSSD, the service RHEL uses to look up directory users, with `subid: sss` in `/etc/nsswitch.conf`. Dworjan's role ships two small modules that write the files instead.

Systemd starts a per-user service manager, `user@<UID>.service`, and a runtime directory, `/run/user/<UID>`, when a user logs in, and removes them after the last session ends. Rootless Podman keeps its runtime state in that directory. *Lingering* keeps both running with no session open; [this site's Caddy entry](../podman/caddy-php-fpm-automatic-https.md) uses it for rootless services. In the test, Dave's `/run/user/1003` was still there 2 seconds after his SSH session closed, and gone 14 seconds after. Alice's user service was already running before her first login. Podman's troubleshooting guide gives the symptom without it, *"rootless containers exit once the user session exits"*, and `loginctl enable-linger` as the fix.

## The machine settings file

[Part 6](vscode-ansible-settings-per-repository.md) listed VS Code's settings scopes: default, user, **remote**, workspace. The remote scope is per server. VS Code Server reads it from `~/.vscode-server/data/Machine/settings.json`. That's where `ansible.python.interpreterPath` belongs, since part 6 found its scope is `machine-overridable`. The playbook points it at `/opt/adt/bin/python`. `force: false` writes the file only once, so a developer's own remote settings survive the next run, and a repository's `.vscode/settings.json` still overrides it.

## What the playbook leaves to VS Code

Dworjan's role also downloads the VS Code Server for one commit ID, and installs the Ansible extension with the server's own `--install-extension`. It's simpler to let Remote-SSH do both:
- **The server.** Remote-SSH's install script downloads the server build matching the laptop's own VS Code commit, so a pre-installed one goes unused after the laptop's next VS Code update. If the server has no internet access, the default `remote.SSH.localServerDownload: auto` falls back to downloading on the laptop and copying the server over with scp.
- **Extensions.** The repository's `.vscode/extensions.json` (part 6) prompts for them. Each developer can also list them under `remote.SSH.defaultExtensions` in their user settings to install them on every SSH host. Both need the server to reach the Visual Studio Marketplace over HTTPS; without that, VS Code's docs point to **Extensions: Install from VSIX…**.
- **The server's OS.** Since VS Code 1.99 (March 2025), the prebuilt server needs glibc 2.28 or later, so RHEL 8 or newer. RHEL 7 is out.

## Test notes

The server was a Rocky Linux 9.8 container running systemd, with sshd, reached by SSH from inside it. Four adjustments applied only to that test machine:
- the sandbox proxy's CA certificate was trusted;
- the file capabilities that `newuidmap` and `newgidmap` need were restored, because the container image had lost them (`rpm -V shadow-utils` flagged both);
- `/dev/fuse` and `/dev/net/tun` were opened to users;
- Ansible reached the server through the Docker connection plugin, since this sandbox has no SSH client.

On a RHEL 9 VM, the capabilities and device permissions are already set that way, and the proxy and the Docker connection don't apply.

## The example repository

The series' companion repository has the playbook and its ADT lock, in [abdelhousni/ansible-development-environment-series](https://github.com/abdelhousni/ansible-development-environment-series/tree/main/09-shared-dev-server-for-vscode-remote-ssh). The lock is compiled with uv's `--exclude-newer` set to this entry's test date, which makes uv ignore anything uploaded to PyPI after it. So it holds the same 69 packages, hashes included.

Its CI repeats the test on every push, against a Rocky Linux 9 container booted with systemd:
- it runs the playbook twice, and the second run must report `changed=0`;
- it checks that lingering is enabled for alice;
- then, as alice, it checks that `/opt/adt/bin` is on `PATH` once and that ADT has ansible-core 2.21.4;
- rootless Podman must find the EE through the shared store;
- `ansible-navigator run` must get the EE's ansible-core 2.21.3. Her own image storage stayed at 196 KB, as above;
- the machine settings file must point at `/opt/adt/bin/python`.

Most of the test notes above apply there too. One more was needed on GitHub's runner. systemd in the container couldn't start alice's user manager: PAM refused it with *"Authentication service cannot retrieve authentication info"*, for a reason not found. So CI checks that lingering is enabled, then gives alice a runtime directory directly. The repository's README lists each of these adjustments.

## Sources

- Alex Dworjan, [Dev Server Using VS Code Remote SSH](https://www.youtube.com/watch?v=2QwkRiVHaxU) (2023-12), and his [shadowman-lab/Ansible-Development](https://github.com/shadowman-lab/Ansible-Development) repository at commit `2e3ea6f` (2026-08-19): `ansibleremoteserver.yml`, `ansiblesharedimage.yml`, and the `shadowman_dev_vs_codeserver` and `shadowman_dev_shared_image_store` roles.
- VS Code docs, in [microsoft/vscode-docs](https://github.com/microsoft/vscode-docs) at `8889b05` (2026-09-29): [Remote-SSH](https://code.visualstudio.com/docs/remote/ssh) (`remote.SSH.defaultExtensions`), the [Remote Development FAQ](https://code.visualstudio.com/docs/remote/faq) (server download, `localServerDownload`, glibc 2.28 since 1.99), and [settings](https://code.visualstudio.com/docs/configure/settings) (the remote scope).
- The Remote-SSH extension's manifest and install script (`ms-vscode-remote.remote-ssh` 0.129.2026091815): the `localServerDownload` default and enum, and the download URL built from the client's commit.
- VS Code's `src/vs/server/node/server.main.ts`: the server's `data/Machine` folder for machine settings.
- Podman: [rootless tutorial](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md) (subordinate IDs, `usermod --add-subuids`, `subid: sss`) and [troubleshooting](https://github.com/containers/podman/blob/main/troubleshooting.md) (lingering). [`containers-storage.conf(5)`](https://github.com/containers/container-libs/blob/main/storage/docs/containers-storage.conf.5.md) for `additionalimagestores`, `mount_program` and the config file locations.
