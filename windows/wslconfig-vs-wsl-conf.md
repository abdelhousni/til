# `.wslconfig` vs `wsl.conf`: which file sets what in WSL

**WSL** (Windows Subsystem for Linux) runs Linux distributions on Windows. WSL2, its current version, runs every distribution inside one shared, lightweight virtual machine. Two configuration files tune it, at two different levels, and a setting only works in the file that defines it ([Microsoft's WSL configuration page](https://learn.microsoft.com/windows/wsl/wsl-config)).

| | `%USERPROFILE%\.wslconfig` | `/etc/wsl.conf` |
|---|---|---|
| Lives | on Windows, in your user profile (`C:\Users\<you>\.wslconfig`) | inside each distribution |
| Applies to | every WSL2 distribution, because they share one virtual machine | that distribution only, WSL1 or WSL2 |
| Exists by default | no | depends on the distribution |
| Sections | `[wsl2]`, `[experimental]` | `[automount]`, `[network]`, `[interop]`, `[user]`, `[boot]`, `[gpu]`, `[time]` |
| Examples | `memory`, `processors`, `networkingMode`, `guiApplications`, `gpuSupport` | `systemd`, `appendWindowsPath`, `hostname`, `[gpu] enabled` |
| Takes effect | after `wsl --shutdown` | once the distribution has fully stopped |

Both use the INI format: a `[section]` line, then `key=value` lines. If a file is missing or malformed, WSL starts anyway without its settings.

## Neither file overrides the other

The two files have different keys, so for almost every setting the question of which one wins doesn't come up. A setting placed in the wrong file is just not one of that file's keys. For example, **WSLg**, the part of WSL2 that shows Linux graphical applications as Windows windows, is turned on or off by `guiApplications` in `.wslconfig` only. `wsl.conf` has no key for it, so WSLg can't be turned off for one distribution and kept for another. The docs don't say what WSL does with a `guiApplications` line written in `wsl.conf` by mistake.

The GPU is the one feature both files have a say in, at two levels:

- `.wslconfig`, `[wsl2] gpuSupport`: GPU support in the WSL2 virtual machine, so for every distribution.
- `wsl.conf`, `[gpu] enabled`: whether Linux applications in this distribution can reach the Windows GPU, and `[gpu] appendLibPath`, which adds `/usr/lib/wsl/lib` to `PATH`.
- `wsl.conf`, `[automount] ldconfig`: adds the GPU libraries Windows provides to the search path of the **dynamic loader** (the part of Linux that finds shared libraries when a program starts) and runs `ldconfig` to refresh its cache. It concerns those GPU libraries only.

All of them default to `true`. The docs don't state a precedence between the two files. They do say `ldconfig` "only applies to WSL 2 with GPU support enabled", and since every distribution runs in the same virtual machine, the likely reading is that `gpuSupport=false` leaves no GPU for any distribution's `wsl.conf` to enable. That reading wasn't tested here.

## When a change takes effect

`.wslconfig` is read when the virtual machine starts, so stop it from PowerShell or a Windows terminal, then open the distribution again:

```powershell
wsl --shutdown
```

That stops every running distribution.

`wsl.conf` is read when the distribution starts. A distribution keeps running for a few seconds after its last shell closes, so closing the terminal and reopening it right away can still find the old settings. Check, or stop just that one:

```powershell
wsl --list --running
wsl --terminate Ubuntu
```

Microsoft also suggests changing the global settings in the **WSL Settings** app from the Start menu rather than editing `.wslconfig` by hand.

## An example of each

```ini
# %USERPROFILE%\.wslconfig: the virtual machine, every distribution
[wsl2]
guiApplications=true
```

```ini
# /etc/wsl.conf: this distribution only
[boot]
systemd=true

[interop]
appendWindowsPath=false
```

`systemd=true` starts systemd as the distribution's init process (the first process, which starts services). `appendWindowsPath=false` stops WSL from adding the Windows `PATH` to the Linux one, so Windows programs are no longer found by name from the Linux shell.

## Sources

- Microsoft Learn, [Advanced settings configuration in WSL](https://learn.microsoft.com/windows/wsl/wsl-config), from [MicrosoftDocs/WSL](https://github.com/MicrosoftDocs/WSL) (`WSL/wsl-config.md`), fetched 2026-11-01.
- The examples are the files from a working Ubuntu 26.04.1 setup under WSL2. Nothing here ran in the Linux cloud container where this entry was drafted, which isn't WSL.
