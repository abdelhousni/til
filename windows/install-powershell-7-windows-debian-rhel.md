# Installing PowerShell 7 on Windows, Debian, Ubuntu and RHEL, the way Microsoft documents it

PowerShell 7 (`pwsh`) is the cross-platform PowerShell. On Windows, it installs next to Windows PowerShell 5.1 (`powershell.exe`) rather than replacing it. On Linux, Microsoft's preferred source is its own package repository, packages.microsoft.com ("PMC"). Commands below are from Microsoft Learn, current for PowerShell 7.6 (LTS). LTS stands for Long Term Servicing: an LTS release only gets security and servicing fixes and is supported for longer than a regular release. 7.6 is supported until 14 November 2028 ([support lifecycle](https://learn.microsoft.com/en-us/powershell/scripting/install/powershell-support-lifecycle)).

## Windows: WinGet

WinGet, the Windows Package Manager, is Microsoft's command-line installer for Windows. It is included in Windows 11 and Windows Server 2025 as part of the App Installer. Windows can install PowerShell from two kinds of package, which is why the next paragraph matters: **MSI** is the classic Windows Installer package, which installs for all users and supports remoting; **MSIX** is the newer packaged-app format, the one Microsoft Store apps use.

```powershell
winget search --id Microsoft.PowerShell --exact
winget install --id Microsoft.PowerShell --source winget
```

Since 7.6, WinGet installs the **MSIX** package by default. That install is per user, and it doesn't support incoming PowerShell remoting (running commands on this machine from another one) or all-users profiles (profile scripts that run for every user). The cause is that an MSIX app runs in a sandbox that blocks changes to its own install folder, `$PSHOME`, where those settings live. From 7.7, MSIX is the only package WinGet offers. For a server or an all-users install, ask for the MSI while it still exists:

```powershell
winget install --id Microsoft.PowerShell --source winget --installer-type wix
```

Upgrade and remove with the same tool:

```powershell
winget upgrade --id Microsoft.PowerShell
winget uninstall --id Microsoft.PowerShell
```

WinGet ships with Windows 11. On Windows Server, only Server 2025 with Desktop Experience has it; for other servers, use the MSI.

## Debian 12 and 13: the Microsoft repository

```sh
sudo apt-get update && sudo apt-get install -y wget
source /etc/os-release
wget -q https://packages.microsoft.com/config/debian/$VERSION_ID/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb   # adds the repository and its signing key
rm packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y powershell
```

Remove it with `sudo apt-get remove powershell`.

## Ubuntu 22.04, 24.04 and 26.04: the same repository

```sh
sudo apt-get update
sudo apt-get install -y wget apt-transport-https software-properties-common
source /etc/os-release
wget -q https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb   # adds the repository and its signing key
rm packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y powershell
```

Remove it with `sudo apt-get remove powershell`. Interim releases such as 25.10 aren't supported; use the `.deb` from GitHub there.

One catch: Ubuntu's own repository ships .NET packages at different versions from Microsoft's. Registering the Microsoft repository makes both available, which can break a later .NET install. If you also install .NET, pin the feed you want with apt priorities ([Microsoft's instructions](https://learn.microsoft.com/en-us/dotnet/core/install/linux-package-mixup)).

## RHEL 8, 9 and 10: the same repository, through dnf

```sh
source /etc/os-release
majorver=${VERSION_ID%.*}                  # 9.6 -> 9
curl -sSL -O https://packages.microsoft.com/config/rhel/$majorver/packages-microsoft-prod.rpm
sudo rpm -i packages-microsoft-prod.rpm
rm packages-microsoft-prod.rpm
sudo dnf install -y powershell
```

Remove it with `sudo dnf remove powershell`. Microsoft's script also runs a full `sudo dnf update` before the install; that step is optional.

On all three Linux distributions, the repository package keeps `pwsh` updated with the rest of the system (`apt upgrade`, `dnf upgrade`). If there's no repository for your release, Microsoft's fallback is the `.deb` or `.rpm` from the [GitHub releases](https://github.com/PowerShell/PowerShell/releases).

## Check it

```powershell
pwsh -NoLogo -Command '"$($PSVersionTable.PSVersion)  $PSHOME"'
```

`$PSHOME` also tells you how it was installed:

| `$PSHOME` | Installed by |
|---|---|
| `C:\Program Files\PowerShell\7` | MSI |
| `C:\Program Files\WindowsApps\...` | MSIX (WinGet's default since 7.6, or the Store) |
| `/opt/microsoft/powershell/7` | the `.deb` or `.rpm` package |

On Linux, profiles and modules follow XDG: `~/.config/powershell/` and `~/.local/share/powershell/Modules`.

## Sources

- Microsoft Learn: install PowerShell 7 on [Windows](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows), [Debian](https://learn.microsoft.com/en-us/powershell/scripting/install/install-debian), [Ubuntu](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu) and [RHEL](https://learn.microsoft.com/en-us/powershell/scripting/install/install-rhel), all current for 7.6.
- The repository config packages (`config/debian/{12,13}`, `config/ubuntu/{22.04,24.04,26.04}` and `config/rhel/{8,9,10}`) all return HTTP 200 from packages.microsoft.com.
- Ubuntu: the steps above ran in `ubuntu:22.04` and `ubuntu:24.04` containers on 2026-10-06 and installed PowerShell 7.6.6 with `$PSHOME` at `/opt/microsoft/powershell/7`. The Debian, RHEL and Windows installs weren't run here.
