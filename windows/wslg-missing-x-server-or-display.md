# WSLg: "Missing X server or $DISPLAY" when a Linux GUI app won't open

I hadn't used a graphical Linux desktop since Mandrake, a Linux distribution from the late 1990s and early 2000s later renamed Mandriva. Linux has been terminals and servers for me since. So running one graphical tool in WSL2 meant learning where WSL's display server comes from, which is probably obvious to people who never left the Linux desktop.

**WSLg** is the part of WSL2 that shows Linux graphical applications as ordinary Windows windows ([the Thunar entry](thunar-file-manager-in-wslg.md) covers what it is and which Windows versions have it). When it isn't running, a graphical application starts and exits at once. With [Headlamp](https://headlamp.dev/) 0.46.0, a graphical interface for Kubernetes clusters, on Ubuntu 26.04 under WSL2:

```text
ERROR:ui/ozone/platform/x11/ozone_platform_x11.cc:249] Missing X server or $DISPLAY
ERROR:ui/aura/env.cc:257] The platform failed to initialize.  Exiting.
```

Headlamp is an **Electron** application, a desktop program built on the Chromium browser engine, which is why the message comes from Chromium's source files. It looked for an **X server**, the program that draws windows for Linux graphical applications, through the `DISPLAY` environment variable, and found none.

## Where `DISPLAY` comes from in WSL

WSLg runs its X server, its Wayland server (Wayland is the newer Linux display protocol) and its sound server in a separate **system distro**, a small Linux environment that WSL starts next to your distribution. It shares their sockets with your distribution under `/mnt/wslg`, and sets `DISPLAY` and `WAYLAND_DISPLAY` to point at them ([WSLg README](https://github.com/microsoft/wslg/blob/main/README.md)). Nothing needs installing or configuring inside the distribution for that.

So check both from the distribution:

```sh
echo "DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
ls /mnt/wslg
```

Both variables empty and no `/mnt/wslg` means WSLg isn't running at all, and nothing inside the distribution will fix it.

## The cause here: `guiApplications=false`

WSLg is turned on or off in `%USERPROFILE%\.wslconfig`, the Windows-side file that configures WSL2 for every distribution. This line turns the system distro off:

```ini
[wsl2]
guiApplications=false
```

Set it to `true`, or delete the line, since `true` is the default. The file is only read when the WSL virtual machine starts, so restart WSL from PowerShell:

```powershell
wsl --shutdown
```

Open the distribution again: `DISPLAY` is set, `/mnt/wslg` is there, and Headlamp opens. `/etc/wsl.conf` in this distribution has `[boot] systemd=true`, and nothing else needed changing.

Looking in `/etc/wsl.conf` for a WSLg setting doesn't help: it configures one distribution and has no key for WSLg. [`.wslconfig` vs `wsl.conf`](wslconfig-vs-wsl-conf.md) lists what each file sets.

## Sources

- [WSLg README](https://github.com/microsoft/wslg/blob/main/README.md): the system distro, `DISPLAY` and `WAYLAND_DISPLAY`, and `guiApplications=false`; fetched 2026-11-01.
- Microsoft Learn, [Advanced settings configuration in WSL](https://learn.microsoft.com/windows/wsl/wsl-config): `guiApplications` and its default, fetched 2026-11-01.

The error and the `.wslconfig` fix happened on Ubuntu 26.04.1 under WSL2 on Windows. They didn't run in the Linux cloud container where this entry was drafted, which has no WSLg.
