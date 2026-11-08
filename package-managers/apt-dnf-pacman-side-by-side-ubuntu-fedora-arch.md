# apt, dnf and pacman side by side: one cheat sheet for Ubuntu 26.04, Fedora 45 and Arch

Second entry in the Portable environments series. [The first entry](portable-environment-map-package-managers-to-images.md) keeps the distribution's own layer as small as possible. That small layer still has to be installed, upgraded and listed, with a different tool on each distribution. This entry puts the three tools in one table, with every command run on the current release of each distribution, and shows how to export the list of installed packages from one machine and replay it on another.

Versions measured here:

| Distribution | Package manager | Low-level tool |
|---|---|---|
| Ubuntu 26.04.1 LTS | `apt` 3.2.0 | `dpkg` |
| Fedora 45 | `dnf5` 5.4.7.0 | RPM 6.1.0 |
| Arch Linux (image of 7 November 2026) | `pacman` 7.1.0 | `libalpm` 16.0.1 |

Articles about Ubuntu 26.04 announced apt 3.1. Ubuntu 26.04.1 already ships 3.2.0, so check `apt --version` rather than trusting the release-day coverage.

## A few terms first

- **Repository index** (or *metadata*): the list of packages a repository publishes, with versions and dependencies. A package manager downloads it, then works from that local copy.
- **Front end and low-level tool**: `dpkg`, `rpm` and `libalpm` install and remove individual package files. `apt`, `dnf` and `pacman` sit on top: they download the index and packages, resolve dependencies and run the low-level tool. That's why some commands below use `dpkg` or `rpm` directly. Those commands only read the database of installed packages.
- **Transaction**: one install, upgrade or removal run, applied as a whole. `apt` and `dnf` number them and can undo them.
- **Install reason**: each package is marked as installed on request (*manual*, *user-installed*, *explicitly installed*) or pulled in as a dependency (*automatic*).
- **Orphan**: a package installed as a dependency that nothing needs any more.

## The cheat sheet

| Task | Ubuntu (`apt`) | Fedora (`dnf`) | Arch (`pacman`) |
|---|---|---|---|
| Refresh the index | `apt update` | `dnf makecache` | `pacman -Sy`, but only together with `-u` (see below) |
| Upgrade everything | `apt upgrade` (`full-upgrade` may also remove packages) | `dnf upgrade` | `pacman -Syu` |
| Search | `apt search ripgrep` | `dnf search ripgrep` | `pacman -Ss ripgrep` |
| Details of a package | `apt show ripgrep` | `dnf info ripgrep` | `pacman -Si ripgrep` (repository), `pacman -Qi ripgrep` (installed) |
| Install | `apt install ripgrep` | `dnf install ripgrep` | `pacman -S ripgrep` |
| Remove | `apt remove ripgrep` (`purge` also deletes its configuration) | `dnf remove ripgrep` | `pacman -Rns ripgrep` (`-s` its unneeded dependencies, `-n` its configuration files) |
| Remove orphans | `apt autoremove` | `dnf autoremove` | `pacman -Qdtq` lists them; `pacman -Qdtq \| pacman -Rns -` removes them |
| Which installed package owns a file | `dpkg -S /usr/bin/rg` | `rpm -qf /usr/bin/rg` | `pacman -Qo /usr/bin/rg` |
| Files of an installed package | `dpkg -L ripgrep` | `rpm -ql ripgrep` | `pacman -Ql ripgrep` |
| Which package provides a file you don't have | `apt-file search` (a separate package, not installed by default) | `dnf provides /usr/bin/tree` | `pacman -Fy` once, then `pacman -F /usr/bin/tree` |
| Packages you installed yourself | `apt-mark showmanual` | `dnf repoquery --userinstalled` | `pacman -Qqe` |
| Why a package is there | `apt why ripgrep` | `dnf leaves` lists packages nothing else needs | `pacman -Qi ripgrep`: "Install Reason" and "Required By" |
| Keep a package at its version | `apt-mark hold ripgrep` | `dnf versionlock add ripgrep` | `IgnorePkg = ripgrep` in `/etc/pacman.conf` |
| History | `apt history-list` | `dnf history list` | `/var/log/pacman.log` |
| Undo the last transaction | `apt history-undo <id>` | `dnf history undo last` | no undo command |
| Empty the package cache | `apt clean` | `dnf clean all` | `pacman -Scc` |
| Repository configuration | `/etc/apt/sources.list.d/ubuntu.sources` | `/usr/share/dnf5/repos.d/` for the distribution's repositories, `/etc/yum.repos.d/` for yours | `/etc/pacman.conf` and `/etc/pacman.d/mirrorlist` |

On all three, `ripgrep` 15 installed, `/usr/bin/rg` was reported as owned by the `ripgrep` package, and removing it left no orphans.

## What differs, and bites

**apt says it isn't for scripts.** Several `apt` commands printed `WARNING: apt does not have a stable CLI interface. Use with caution in scripts.` The [apt(8) man page](https://manpages.ubuntu.com/manpages/resolute/en/man8/apt.8.html) says the same: `apt` is an end-user tool that may change between versions, and scripts should prefer `apt-get` and `apt-cache`, which keep backward compatibility as much as possible.

**apt now has a history and an undo.** In apt 3.2.0, `apt history-list` numbers every transaction, and `apt history-undo <id>` reverses one. Give it the ID from the list. Undoing the last removal reinstalled `ripgrep`. A mistyped ID pointing at an old transaction from the image build tried to undo that one instead, and failed on a package that can't be removed.

**Ubuntu's repositories are in the deb822 format.** `/etc/apt/sources.list.d/ubuntu.sources` holds `Types`, `URIs`, `Suites`, `Components` and `Signed-By` fields, one block per repository. The old one-line `sources.list` format still works, and `apt modernize-sources` converts it.

**Fedora 45 moved its repository files out of `/etc`.** The distribution's `.repo` files (`fedora.repo`, `fedora-updates.repo`...) are in `/usr/share/dnf5/repos.d/`, owned by the `fedora-repos` package, and `/etc/yum.repos.d/` is empty on a fresh system. A repository you add yourself, with `dnf config-manager` or `dnf copr`, still goes into `/etc/yum.repos.d/` ([the Fedora 45 change](https://fedoraproject.org/wiki/Changes/RelocateRpmRepoConfigsToUsr)).

**Arch has no undo, only a log and a cache.** `/var/log/pacman.log` records every installed, upgraded and removed package with its version. The packages themselves stay in `/var/cache/pacman/pkg/` until you empty it, so an older version can be reinstalled from there. `paccache`, the tool that prunes that cache while keeping recent versions, is in the separate `pacman-contrib` package and isn't in the base image.

**Arch doesn't support partial upgrades.** `pacman -Sy ripgrep` refreshes the index and then installs one package built against newer libraries than the rest of the system. Arch's [system maintenance page](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported) says not to do this: run `pacman -Syu` instead, which upgrades everything and installs in the same transaction.

**`pacman -Qdtq` fails when there's nothing to find.** It exits with status 1 when there are no orphans, so a script running with `set -e` stops there. Add `|| true`, or test the output instead of the exit code.

## Export the list, replay it on a fresh machine

This is the piece that turns a package manager into something Git can describe. Each distribution can print the packages that were installed on request, without their dependencies, and install that list on a fresh machine. Here `ripgrep` and `tree` were installed in one container, the list written to a file, then installed in a second, fresh container:

```bash
# Ubuntu
apt-mark showmanual > packages-ubuntu.txt
xargs -a packages-ubuntu.txt apt-get install -y

# Fedora
dnf repoquery --userinstalled --queryformat '%{name}\n' > packages-fedora.txt
xargs -a packages-fedora.txt dnf install -y

# Arch: -n keeps packages from the official repositories, -m would list the others (AUR)
pacman -Qqen > packages-arch.txt
pacman -Syu --needed - < packages-arch.txt
```

All three imports succeeded, and `rg` and `tree` were present afterwards. The lists weren't the same size: 89 lines on Ubuntu, 23 on Fedora and 3 on Arch (`base`, `ripgrep`, `tree`). The Ubuntu and Fedora images mark much of their own content as installed on request, so before committing such a list, trim it to what you actually chose. The **AUR** (*Arch User Repository*) is Arch's collection of community build recipes, outside the official repositories; `pacman` can't install from it, so the `-m` list needs a separate tool.

## Pinning a whole repository to a date

`apt-mark hold`, `dnf versionlock` and `IgnorePkg` pin one package. To get the same versions as on a given day for everything, two of the three distributions publish dated copies of their repositories:

- **Ubuntu**: `apt update --snapshot 20260601T000000Z` read the index from `snapshot.ubuntu.com` as it was on 1 June 2026. The same `--snapshot` option works on `apt install` and `apt policy`.
- **Arch**: the [Arch Linux Archive](https://wiki.archlinux.org/title/Arch_Linux_Archive) keeps a copy of the repositories for each day. With `Server = https://archive.archlinux.org/repos/2026/10/01/$repo/os/$arch` as the only line of `/etc/pacman.d/mirrorlist`, `pacman -Syy` downloaded the index of 1 October 2026.
- **Fedora**: I found no dated copy of Fedora's repositories. `dnf versionlock` pins individual packages.

## Sources and where this ran

- apt: `apt --help`, `apt-get --help` and the commands above on Ubuntu 26.04.1; the [apt(8) man page](https://manpages.ubuntu.com/manpages/resolute/en/man8/apt.8.html).
- dnf: `dnf --help` on Fedora 45; [Relocate RPM repository configs to /usr](https://fedoraproject.org/wiki/Changes/RelocateRpmRepoConfigsToUsr).
- pacman: `pacman -h` and `pacman -Rh` on Arch; the Arch Wiki pages linked above (the wiki refused automated access on 8 November, so the Partial upgrades rule is as quoted by mirrors of that page).

Every command ran in the official container images (`ubuntu:26.04`, `quay.io/fedora/fedora:45`, `ghcr.io/archlinux/archlinux:latest`) under Docker in a Linux cloud container, on 7 and 8 November 2026. None of it ran in WSL, where these distributions use the same package managers.
