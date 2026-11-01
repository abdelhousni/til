# AppImage: "error loading libfuse.so.2" on recent Ubuntu

I hadn't used a graphical Linux desktop since Mandrake, a Linux distribution from the late 1990s and early 2000s later renamed Mandriva. Linux has been terminals and servers for me since. So installing one graphical tool meant learning a few things that are probably obvious to people who never left the Linux desktop, starting with AppImages and FUSE.

An **AppImage** is a Linux application packed into one executable file, with no installer and no package manager. Many desktop tools ship that way, including [Headlamp](https://headlamp.dev/), a graphical interface for Kubernetes clusters (Kubernetes itself is explained in [what Kubernetes is](../kubernetes/what-is-kubernetes-and-how-it-works.md)). The example here is Headlamp 0.46.0 on Ubuntu 26.04, run under WSL2, though nothing in this entry depends on WSL.

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

## The error

```text
dlopen(): error loading libfuse.so.2

AppImages require FUSE to run.
You might still be able to extract the contents of this AppImage
if you run it with the --appimage-extract option.
```

**FUSE** (Filesystem in Userspace) lets an ordinary program provide a filesystem. An AppImage uses it to mount its own contents and run the application from there. The application itself doesn't use FUSE; the **runtime** does, the small program at the start of the AppImage file that does the mounting. Recent Ubuntu releases ship FUSE 3 and no longer install version 2 by default, and which one matters depends on the runtime:

- The older runtime loads version 2 of the FUSE library, `libfuse.so.2`, when it starts. Version 3 (`libfuse3.so.3`) is a different library and doesn't help.
- The newer [type2-runtime](https://github.com/AppImage/type2-runtime) is linked statically, and its README says `libfuse2` is then no longer required on the system.

## Which runtime an AppImage carries

Look for the library name in the start of the file, without running it:

```sh
head -c 1000000 ~/Applications/Headlamp.AppImage | strings | grep -m3 -i 'libfuse'
```

Headlamp 0.46.0 prints the older runtime's strings:

```text
libfuse.so.2
dlopen(): error loading libfuse.so.2
dlsym(): error loading symbol from libfuse.so.2
```

For that runtime, FUSE 2 has to be installed. It can sit side by side with FUSE 3.

## Install FUSE 2 next to FUSE 3

Check whether the library is there. `ldconfig -p` prints the cache of shared libraries that the **dynamic loader** (the part of Linux that finds shared libraries when a program starts) knows about, which is what `dlopen()` searches:

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

## Without installing anything

The AppImage runtime can extract itself to a temporary directory, run from there, and clean up when the application exits. It's slower at every start:

```sh
~/Applications/Headlamp.AppImage --appimage-extract-and-run
```

If the AppImage then starts but no window opens under WSL2, with `Missing X server or $DISPLAY`, the cause is WSLg, not FUSE: see [WSLg: "Missing X server or $DISPLAY"](../windows/wslg-missing-x-server-or-display.md).

## Sources

- AppImage docs, [I get some errors related to something called "FUSE"](https://docs.appimage.org/user-guide/troubleshooting/fuse.html) (FUSE 2 alongside FUSE 3, the `libfuse2t64` rename, extract-and-run), from [AppImage/docs.appimage.org](https://github.com/AppImage/docs.appimage.org), fetched 2026-11-01.
- [AppImage/type2-runtime README](https://github.com/AppImage/type2-runtime/blob/main/README.md): the statically linked runtime, fetched 2026-11-01.
- Homebrew's [`headlamp` cask](https://github.com/Homebrew/homebrew-cask/blob/main/Casks/h/headlamp.rb), version 0.46.0.
- The package facts (`libfuse2t64` replacing `libfuse2`, `fuse3` breaking `fuse`, the `ldconfig -p` output) were checked with apt on Ubuntu 24.04 in the Linux cloud container where this entry was drafted. The Headlamp install, the runtime check and the error happened on Ubuntu 26.04.1 under WSL2; the AppImage itself didn't run in the container.
