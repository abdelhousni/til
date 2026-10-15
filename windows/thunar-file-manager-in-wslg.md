# A lightweight graphical file manager in WSLg: Thunar on Ubuntu, RHEL 9 and NixOS

**WSLg** is the part of WSL2 that shows Linux graphical applications as ordinary Windows windows. It's included in WSL on Windows 11 and recent Windows 10 builds, and it only works with WSL2 distributions, not WSL1. A WSL distribution has no file manager by default. That matters as soon as something asks to "open a folder", such as a browser's *Show in folder*: nothing happens, or you get an error.

**Thunar**, Xfce's file manager, is a light choice. It has few dependencies, and the same steps work on all three distributions. Only the package and its source change.

## How "open this folder" is resolved

Linux desktop applications don't name a file manager. They ask for the default application for the **MIME type** `inode/directory`. A MIME type is a label for a kind of content, such as `text/plain` or `image/png`, and `inode/directory` means "a folder". The answer is the name of a **`.desktop` file**, the launcher description that every graphical application installs under `/usr/share/applications/`.

`xdg-mime` (from `xdg-utils`) reads and writes that default, in `~/.config/mimeapps.list`:

```sh
xdg-mime default thunar.desktop inode/directory
xdg-mime query default inode/directory     # thunar.desktop
```

The command is the same on every distribution. Run it as your user, not with `sudo`, because the setting is per user.

## Ubuntu

```sh
sudo apt install --no-install-recommends thunar xdg-utils
xdg-mime default thunar.desktop inode/directory
thunar &
```

`--no-install-recommends` leaves out the optional packages apt would add, which keeps the install small. On Ubuntu 24.04 this installs Thunar 4.18.8, and the launcher is `/usr/share/applications/thunar.desktop`.

## RHEL 9 and rebuilds (Rocky, AlmaLinux)

Red Hat supports RHEL 9 on WSL2 for development and learning, with a subscription, including the free Developer subscription ([Red Hat article 7115538](https://access.redhat.com/articles/7115538)). Thunar isn't in RHEL's own repositories. It comes from **EPEL** (Extra Packages for Enterprise Linux), a Fedora project that rebuilds extra packages for RHEL. Some EPEL packages need **CRB** (CodeReady Builder), a Red Hat repository of build dependencies that's off by default, so enable both:

```sh
# RHEL
sudo subscription-manager repos --enable codeready-builder-for-rhel-9-$(arch)-rpms
sudo dnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm

# Rocky Linux or AlmaLinux instead
sudo dnf config-manager --set-enabled crb
sudo dnf install epel-release

sudo dnf install --setopt=install_weak_deps=False Thunar xdg-utils
xdg-mime default thunar.desktop inode/directory
```

The package name has a capital T (`Thunar`), but the launcher file doesn't. Check what's installed with `ls /usr/share/applications | grep -i thunar`. `install_weak_deps=False` is dnf's equivalent of apt's `--no-install-recommends`.

## NixOS (NixOS-WSL)

On NixOS, software is declared in the system configuration, not installed with a command (see [the first steps entry](../nixos/first-steps-configuration-generations-rollback.md)). The `programs.thunar` module installs Thunar and also turns on `programs.xfconf`, the settings store Thunar saves its preferences in:

```nix
programs.thunar = {
  enable = true;
  plugins = with pkgs; [ thunar-archive-plugin ];   # optional
};

# The default for folders, for every user
xdg.mime.defaultApplications."inode/directory" = "thunar.desktop";
```

Then run `sudo nixos-rebuild switch`. `programs.thunar` exists only as a NixOS option, not in Home Manager. If your user's settings live in Home Manager ([the NixOS module entry](../nixos/home-manager-nixos-module.md) explains how it's set up), set the default there instead. Its option has a different name:

```nix
xdg.mimeApps.enable = true;
xdg.mimeApps.defaultApplications."inode/directory" = "thunar.desktop";
```

NixOS-WSL makes the WSLg X11 socket available in `/tmp/.X11-unix` itself, and its `wsl.startMenuLaunchers` option adds the installed graphical applications to the Windows Start menu.

## Without installing anything

To open folders in Windows Explorer instead, `explorer.exe` takes a Windows path, and `wslpath -w` converts a Linux path to one:

```sh
explorer.exe "$(wslpath -w ~/Downloads)"
```

That works by hand. It doesn't change what `inode/directory` opens, though, so applications that ask for a folder still need a `.desktop` file that calls Explorer.

## A browser's "Show in folder"

On Ubuntu, the `chromium-browser` package is a stub that installs the Chromium **snap** instead. Snaps are sandboxed packages run by `snapd`, which needs systemd. A sandboxed browser doesn't start the file manager directly. It asks the **XDG desktop portal**, a D-Bus service that applications in a sandbox use to reach the desktop, so *Show in folder* also needs `xdg-desktop-portal` and a D-Bus session. A browser installed as a deb, such as Google Chrome, calls the `inode/directory` default directly.

## Sources

- None of this was run on WSL, Windows, RHEL or NixOS. On 2026-10-15 the Ubuntu install and the `xdg-mime` commands ran in an Ubuntu 24.04 container, without a display. The NixOS and Home Manager options were checked against the module sources of nixpkgs and home-manager (`programs/thunar.nix`, `config/xdg/mime.nix`, `misc/xdg/mime-apps.nix`) and NixOS-WSL (`wsl-distro.nix`). The rest is from the documentation below.
- [WSLg: run Linux GUI apps](https://learn.microsoft.com/windows/wsl/tutorials/gui-apps) (Microsoft Learn).
- [Red Hat Enterprise Linux on WSL](https://access.redhat.com/articles/7115538), and [EPEL: getting started](https://docs.fedoraproject.org/en-US/epel/getting-started/).
- `xdg-mime(1)` and the freedesktop.org [MIME applications associations](https://specifications.freedesktop.org/mime-apps-spec/latest/) specification.
- NixOS options [`programs.thunar`](https://search.nixos.org/options?query=programs.thunar) and [`xdg.mime.defaultApplications`](https://search.nixos.org/options?query=xdg.mime.defaultApplications); Home Manager [`xdg.mimeApps`](https://nix-community.github.io/home-manager/options.xhtml#opt-xdg.mimeApps.enable).
