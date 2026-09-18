# Finding and force-closing a locked file on a Windows SMB share

Someone leaves for the day with a spreadsheet still open over the network, or a desktop app crashes without releasing its file handle, and now everyone else gets: *"The document `filename` is locked for editing by another user."* Condensed and re-verified against current Microsoft docs from [a walkthrough on woshub.com](https://woshub.com/managing-open-files-windows-server-share/) — three ways to find and clear that lock, from oldest to most useful.

## GUI: Computer Management

`compmgmt.msc` → **System Tools → Shared Folders → Open Files** lists every open file on the SMB server: local path, the user holding it open, lock count, and Read vs. Read+Write mode. Right-click → **Close Open File** to force it shut. Fine for a one-off, useless for scripting or filtering by user across a real fleet of servers.

## The legacy CLI: `openfiles`

```cmd
openfiles /query /fo csv
```

Lists session ID, username, and full local path for every open file — on the local machine by default, or on a remote host with `/s`:

```cmd
openfiles /query /s lon-fs01 /fo csv
```

Piping through `find` narrows it to one file:

```cmd
openfiles /query /s lon-fs01 /fo csv | find /i "filename.docx"
```

`openfiles` only sees files opened *through a share*, not by local processes on the box, unless you turn on tracking — which comes with a real cost, per [Microsoft's own docs](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/openfiles): enabling it "might slow down your system," and the change only takes effect after a reboot.

```cmd
openfiles /local on
```

## PowerShell: `Get-SmbOpenFile` and `Close-SmbOpenFile`

The `SmbShare` module's cmdlets are the current, scriptable way to do this — no CSV parsing, real objects with real properties.

```powershell
Get-SmbOpenFile
```

```
FileId              SessionId           Path                             ClientComputerName  ClientUserName
------              ---------           ----                             ------------------  --------------
8813541326973       8813272891469       D:\Shares\Finance\annual2020.xlsx 192.168.1.190       CORP\mjenny
8813541327109       8813272891517       D:\Shares\Reports\weekly.docx     192.168.1.204       CORP\jsmith
```

Narrower queries, all filtering server-side on real parameters rather than piping through `Where-Object` when a direct one exists:

```powershell
# Everything one specific user has open
Get-SmbOpenFile -ClientUserName "CORP\mjenny" | Select-Object ClientComputerName, Path

# Everything open from one client machine
Get-SmbOpenFile -ClientComputerName 192.168.1.190 | Select-Object ClientUserName, Path

# Pattern match on the path -- Where-Object is still the right tool here
Get-SmbOpenFile | Where-Object Path -Like "*annual2020.xlsx"
```

Closing is the same shape, and the one thing worth not skimming: per [`Close-SmbOpenFile`'s own docs](https://learn.microsoft.com/en-us/powershell/module/smbshare/close-smbopenfile), this "can cause data loss to the client for which the file is being closed if the client has not flushed all of the file modifications back to the server before the file is closed." It's a hard kill, not a polite request — confirm you have the right file before running it unattended.

```powershell
# By file ID -- prompts for confirmation by default
Close-SmbOpenFile -FileId 8813541326973

# By name, matched through the pipeline, no prompt
Get-SmbOpenFile | Where-Object Path -Like "*annual2020.xlsx" | Close-SmbOpenFile -Force
```

An interactive picker, for when you'd rather eyeball the list than write a filter:

```powershell
Get-SmbOpenFile | Select-Object ClientUserName, ClientComputerName, Path, SessionId |
    Out-GridView -PassThru -Title "Select files to force-close" |
    Close-SmbOpenFile -Confirm:$false -Verbose
```

## Doing it remotely, and clearing out one user entirely

Both cmdlets take `-CimSession`, so a single session handles a remote server without `Enter-PSSession`:

```powershell
$sessn = New-CimSession -ComputerName lon-fs01

Get-SmbOpenFile -CimSession $sessn | Where-Object Path -Like "*pubs.docx" |
    Close-SmbOpenFile -CimSession $sessn
```

The scenario the whole thing exists for — someone went home and left files locked — is just the user-filtered version with `-Force` added so nothing waits on a prompt at 6pm:

```powershell
Get-SmbOpenFile -CimSession $sessn -ClientUserName "*mjenny*" |
    Close-SmbOpenFile -CimSession $sessn -Force
```

## Two options worth knowing that the walkthrough doesn't mention

Both confirmed in `Get-SmbOpenFile`'s current parameter list, useful specifically once a file server stops being one box:

- **`-ScopeName`** filters to files open through a particular Scale-Out File Server (SOFS) scope, when multiple file server roles share one cluster.
- **`-IncludeHidden`** surfaces handles the SMB server creates and uses internally, normally left out of the default listing — genuinely a debugging-only flag, not something to leave on.
