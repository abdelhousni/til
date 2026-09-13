# Root vs rootless Podman on RHEL 10 and Ubuntu 26.04

Podman has no daemon either way — root and rootless are two different ways of running the same `podman` binary, distinguished by whether the containers it starts get a real root-owned process on the host or one mapped into a Linux user namespace. Same commands, same image format; different storage path, different capabilities, different default posture per distro.

## The core mechanism (same on every distro)

- **Rootless** maps your unprivileged user's UID/GID to root *inside* the container's user namespace, via ranges reserved for you in `/etc/subuid`/`/etc/subgid`. Root inside the container is still just your regular user on the host.
- **Storage and config live under your home directory when rootless**, not the system-wide paths root uses. Per [RHEL 10's own container docs](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/building_running_and_managing_containers/introduction-to-containers): container storage is `/var/lib/containers/storage` for root vs `$HOME/.local/share/containers/storage` rootless, and rootless config goes in `$HOME/.config/containers` instead of `/etc/containers`.
- **A rootless container can't bind a port below 1024** by default — that's a kernel restriction on unprivileged processes, not a Podman one. Lower it with the `net.ipv4.ip_unprivileged_port_start` sysctl if you actually need it.
- Edited `/etc/subuid`/`/etc/subgid` by hand? Run `podman system migrate` afterward — existing rootless containers don't pick up a changed ID range on their own.
- Current Podman (per [its own release notes](https://github.com/containers/podman/blob/main/RELEASE_NOTES.md)) uses **pasta** for rootless networking by default; slirp4netns support has since been dropped entirely. This is a Podman-version fact, not a distro one — it applies equally once either distro's Podman package is new enough.

## RHEL 10

Podman ships as a first-class package in the base repos, not an add-on, and RHEL's own docs treat rootless as the expected way to run containers — there's a dedicated "Special considerations for rootless containers" section in the official guide, not just a footnote. SELinux is enforcing by default, so bind-mounted host paths generally need an `:z`/`:Z` relabel suffix to be readable inside the container, rootless or not.

## Ubuntu 26.04 LTS ("Resolute")

Podman is packaged in `universe`, Ubuntu's community-maintained tier — not `main`, and not Canonical's own default container tooling the way it is Red Hat's. It's a real, current package (5.7.0 in 26.04 at release), but you're relying on Debian/Ubuntu's packaging team rather than upstream Red Hat integration for how quickly it tracks new Podman releases. The user-namespace/subuid mechanics are identical (it's a kernel feature, not a distro one); the confinement layer is AppArmor instead of SELinux, so there's no `:z`/`:Z` relabeling step, but any custom AppArmor profile on the host still applies to what a container can do.

## The practical takeaway

The rootless *mechanism* is the same everywhere Podman runs — it's Linux user namespaces plus `/etc/subuid`/`/etc/subgid`, full stop. What actually differs between these two is packaging posture: RHEL treats Podman and rootless-by-default as the supported, documented path; Ubuntu treats it as a community package you opted into, so double-check its `universe` version against upstream before assuming a fix or feature described in Podman's own docs has landed yet.
