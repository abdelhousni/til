# Running an AppImage in WSLg: libfuse2, a missing `$DISPLAY`, and `.wslconfig` vs `wsl.conf`

**WSLg** is the part of WSL2 that shows Linux graphical applications as ordinary Windows windows ([the Thunar entry](thunar-file-manager-in-wslg.md) covers what it is and which Windows versions have it). An **AppImage** is a Linux application packed into one executable file, with no installer and no package manager. Many desktop tools ship that way on Linux, including [Headlamp](https://headlamp.dev/), a graphical interface for Kubernetes clusters (Kubernetes itself is explained in [what Kubernetes is](../kubernetes/what-is-kubernetes-and-how-it-works.md)).

Getting Headlamp 0.46.0 to open on Ubuntu 26.04 under WSL2 hit two separate errors, one after the other. Each has its own cause and fix.

## Homebrew installs the AppImage but no command

[Homebrew](https://brew.sh/) is a package manager from macOS that also runs on Linux. Its **casks** are packages for graphical applications. `brew install headlamp` downloads the AppImage, then:

```text
==> Moving App Image 'Headlamp-0.46.0-linux-x64.AppImage' to '/home/abdel/Applications/Headlamp.AppImage'
🍺  headlamp was successfully installed!
```

and `headlamp` then answers `command not found`. The [cask definition](https://github.com/Homebrew/homebrew-cask/blob/main/Casks/h/headlamp.rb) has only an `app_image` line on Linux, which moves the file to `~/Applications`. Nothing is linked into a directory on `PATH`, so add the link yourself:

```sh
mkdir -p ~/.local/bin
ln -sf ~/Applications/Headlamp.AppImage ~/.local/bin/headlamp
```

Ubuntu's default `~/.profile` adds `~/.local/bin` to `PATH` when the directory exists at login.

## `dlopen(): error loading libfuse.so.2`

```text
dlopen(): error loading libfuse.so.2

AppImages require FUSE to run.
You might still be able to extract the contents of this AppImage
if you run it with the --appimage-extract option.
```

**FUSE** (Filesystem in Userspace) lets an ordinary program provide a filesystem. An AppImage uses it to mount its own contents and run the application from there. The AppImage runtime is built against version 2 of the FUSE library, `libfuse.so.2`, while recent Ubuntu releases ship FUSE 3 and no longer install version 2 by default. The two versions can be installed side by side.

Check whether the library is there. `ldconfig -p` prints the cache of shared libraries the dynamic loader knows about, which is what `dlopen()` searches:

```sh
ldconfig -p | grep libfuse
```

No `libfuse.so.2` line means it's missing. Install it:

```sh
sudo apt install libfuse2t64     # Ubuntu 24.04 and later
sudo apt install libfuse2        # Ubuntu 22.04
```

Ubuntu 24.04 renamed `libfuse2` to `libfuse2t64`, part of the switch to a 64-bit `time_t` (the type that holds timestamps). On 24.04 `libfuse2` has no installable version any more, and `libfuse2t64` declares that it provides and replaces it. Afterwards the check shows:

```text
	libfuse.so.2 (libc6,x86-64) => /lib/x86_64-linux-gnu/libfuse.so.2
```

Don't install the package called `fuse` to get it. On 24.04, `fuse3` declares that it breaks and replaces `fuse`, so installing `fuse` makes apt remove `fuse3`, which other packages may need. The library package alone is enough for an AppImage.

Without installing anything, the AppImage runtime can extract itself to a temporary directory, run from there, and clean up when the application exits. It's slower at every start:

```sh
~/Applications/Headlamp.AppImage --appimage-extract-and-run
```

## `Missing X server or $DISPLAY`

With FUSE fixed, Headlamp started and stopped at once:

```text
ERROR:ui/ozone/platform/x11/ozone_platform_x11.cc:249] Missing X server or $DISPLAY
ERROR:ui/aura/env.cc:257] The platform failed to initialize.  Exiting.
```

Headlamp is an **Electron** application, a desktop program built on the Chromium browser engine. It looked for an **X server**, the program that draws windows for Linux graphical applications, through the `DISPLAY` environment variable, and found none.

WSLg runs its X server, its Wayland server (Wayland being the newer display protocol) and its sound server in a separate **system distro**, a small Linux environment WSL starts next to your distribution. It shares their sockets with your distribution under `/mnt/wslg` and sets `DISPLAY` and `WAYLAND_DISPLAY` to point at them ([WSLg README](https://github.com/microsoft/wslg/blob/main/README.md)). So check both:

```sh
echo "DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
ls /mnt/wslg
```

Both variables empty and no `/mnt/wslg` means WSLg isn't running at all. Here the cause was this line in `%USERPROFILE%\.wslconfig` on the Windows side, which turns the system distro off:

```ini
[wsl2]
guiApplications=false
```

Set it to `true`, or delete the line, since `true` is the default. Then restart WSL from PowerShell, because this file is only read when the WSL virtual machine starts:

```powershell
wsl --shutdown
```

Open the distribution again, and `DISPLAY` is set and Headlamp opens. `/etc/wsl.conf` here has `[boot] systemd=true`, and nothing else needed changing.

## `.wslconfig` and `wsl.conf` set different things

WSL reads two configuration files, and `guiApplications` exists in only one of them ([Microsoft's WSL configuration page](https://learn.microsoft.com/windows/wsl/wsl-config)):

| | `%USERPROFILE%\.wslconfig` | `/etc/wsl.conf` |
|---|---|---|
| Lives | on Windows, in your user profile | inside each distribution |
| Applies to | every WSL2 distribution, because they share one virtual machine | that distribution only, WSL1 or WSL2 |
| Exists by default | no | depends on the distribution |
| Sections | `[wsl2]`, `[experimental]` | `[automount]`, `[network]`, `[interop]`, `[user]`, `[boot]`, `[gpu]`, `[time]` |
| Examples | `memory`, `processors`, `networkingMode`, `guiApplications`, `gpuSupport` | `systemd`, `appendWindowsPath`, `hostname`, `[gpu] enabled` |
| Takes effect | after `wsl --shutdown` | once the distribution has fully stopped |

So WSLg can't be turned on or off per distribution: `wsl.conf` has no key for it. The docs don't say what WSL does with a `guiApplications` line put in `wsl.conf` by mistake.

The GPU is the one feature both files have a say in, at two levels:

- `.wslconfig`, `[wsl2] gpuSupport`: GPU support in the WSL2 virtual machine, so for every distribution.
- `wsl.conf`, `[gpu] enabled`: whether Linux applications in this distribution can reach the Windows GPU, and `[gpu] appendLibPath`, which adds `/usr/lib/wsl/lib` to `PATH`.
- `wsl.conf`, `[automount] ldconfig`: adds the GPU libraries Windows provides to the dynamic loader's search path and runs `ldconfig`. It concerns those GPU libraries only, not `libfuse.so.2`.

All of them default to `true`. The docs don't state a precedence between the two files. They do say `ldconfig` "only applies to WSL 2 with GPU support enabled", and since every distribution runs in the same virtual machine, the likely reading is that `gpuSupport=false` leaves no GPU for any distribution's `wsl.conf` to enable. That reading wasn't tested here.

A distribution keeps running for a few seconds after its last shell closes, and an edited `wsl.conf` only applies after it has stopped. `wsl --list --running` shows whether it has; `wsl --terminate <distro>` stops one distribution, while `wsl --shutdown` stops them all along with the virtual machine. Microsoft also suggests changing the global settings in the **WSL Settings** app from the Start menu rather than editing `.wslconfig` by hand.

## Sources

- AppImage docs, [I get some errors related to something called "FUSE"](https://docs.appimage.org/user-guide/troubleshooting/fuse.html) (FUSE 2 alongside FUSE 3, the `libfuse2t64` rename, extract-and-run), from [AppImage/docs.appimage.org](https://github.com/AppImage/docs.appimage.org), fetched 2026-11-01.
- [WSLg README](https://github.com/microsoft/wslg/blob/main/README.md): the system distro, `DISPLAY` and `WAYLAND_DISPLAY`, and `guiApplications=false`; fetched 2026-11-01.
- Microsoft Learn, [Advanced settings configuration in WSL](https://learn.microsoft.com/windows/wsl/wsl-config), from [MicrosoftDocs/WSL](https://github.com/MicrosoftDocs/WSL), fetched 2026-11-01.
- Homebrew's [`headlamp` cask](https://github.com/Homebrew/homebrew-cask/blob/main/Casks/h/headlamp.rb), version 0.46.0.
- The package facts (`libfuse2t64` replacing `libfuse2`, `fuse3` breaking `fuse`, the `ldconfig -p` output) were checked with apt on Ubuntu 24.04.

The Headlamp install, both errors and the `.wslconfig` fix happened on Ubuntu 26.04.1 under WSL2 on Windows. They didn't run in the Linux cloud container where this entry was drafted, which has no WSLg.
