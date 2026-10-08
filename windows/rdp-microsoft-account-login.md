# RDP into Windows 11 with a Microsoft account: the password, not the PIN, and `MicrosoftAccount\`

RDP (Remote Desktop Protocol, Microsoft's protocol for using another computer's desktop over the network) to a Windows 11 PC signed in with a Microsoft account usually fails for two reasons. RDP needs the account's **password**, not the Windows Hello PIN. (Windows Hello is the sign-in method that uses a PIN or biometrics, such as a fingerprint or a face scan, instead of a password.) And the username often has to name the account provider explicitly.

## On the host (the PC you connect to)

1. **Edition**: Pro, Enterprise or Education. Windows 11 Home can run the RDP client, but it can't accept incoming sessions.
2. *Settings → System → Remote Desktop*: turn it on.
3. *Settings → Accounts → Sign-in options → Additional settings*: turn off "For improved security, only allow Windows Hello sign-in for Microsoft accounts on this device".
4. Lock the PC (`Win + L`), choose *Sign-in options → Password*, and sign in once with the Microsoft account password. That leaves a password credential RDP can use.

## In the client (`mstsc`)

`mstsc` (`mstsc.exe`) is the Remote Desktop Connection program that ships with Windows. Type `mstsc` in the Start menu or in *Win + R* to open it, and enter the computer's name and the username from the table below.

| Account type | Username | Password |
|---|---|---|
| Microsoft account | `MicrosoftAccount\you@outlook.com` | the Microsoft account password |
| Local account | `.\opsadmin` or `HOSTNAME\opsadmin` | the local password |

The `MicrosoftAccount\` prefix selects the Microsoft account provider. `.\` forces a local account when Windows would otherwise resolve the name as a Microsoft Entra ID or domain user. Microsoft Entra ID is Microsoft's cloud identity service, which organizations use to sign in to Microsoft 365 and Azure; a domain user is an account kept by an organization's own Windows domain server instead of on the PC. Run `whoami` on the host to get the exact `HOSTNAME\user`.

## If it still fails

On the host, in an elevated PowerShell, check who may use RDP:

```powershell
Get-LocalGroupMember -Group "Remote Desktop Users"
Add-LocalGroupMember -Group "Remote Desktop Users" -Member "MicrosoftAccount\you@outlook.com"
```

Administrators are allowed by default. A policy can still override that. In `secpol.msc`, under *Local Policies → User Rights Assignment*, the account (or one of its groups) must be in *Allow log on through Remote Desktop Services*, and not in *Deny log on through Remote Desktop Services*.

On the client, delete a stale saved credential, then type the username instead of accepting the prefilled one:

```powershell
cmdkey /list
cmdkey /delete:TERMSRV/remote-pc-name
```

Then check that the port is reachable, the firewall rule is on, and the network profile is *Private*:

```powershell
Test-NetConnection remote-pc-name -Port 3389       # client: TcpTestSucceeded : True
Get-NetFirewallRule -DisplayGroup "Remote Desktop" |
  Select-Object DisplayName, Enabled, Direction, Action   # host
Get-NetConnectionProfile                                  # host
```

## For a homelab: a local break-glass account

A local administrator doesn't depend on Windows Hello, a Microsoft account or internet access:

```powershell
$Password = Read-Host "Password" -AsSecureString
New-LocalUser -Name "rdp-admin" -Password $Password -FullName "RDP Administrator"
Add-LocalGroupMember -Group "Administrators" -Member "rdp-admin"
```

Connect as `.\rdp-admin`. Give it a strong, unique password, allow RDP only over the LAN or a VPN, and never expose TCP 3389 to the internet.

## Sources

- Microsoft Q&A:
  - [Windows 11 Remote Desktop cannot log into Microsoft account](https://learn.microsoft.com/en-us/answers/questions/5644653/windows-11-remote-destkop-cannot-log-into-microsof);
  - [Can't login via RDP with my @live.com account](https://learn.microsoft.com/en-us/answers/questions/5878568/cant-login-via-rdp-with-my-@live-com-account);
  - [Remote Desktop: your credentials did not work](https://learn.microsoft.com/en-us/answers/questions/2187488/remote-desktop-your-credentials-did-not-work);
  - [Windows 11 Pro Remote Desktop connection login attempt](https://learn.microsoft.com/en-us/answers/questions/5561697/windows-11-pro-remote-desktop-connection-login-att).
- Microsoft Learn: [mstsc](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/mstsc), [Windows Hello for Business overview](https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/) and [What is Microsoft Entra?](https://learn.microsoft.com/en-us/entra/fundamentals/what-is-entra).
- Microsoft Learn: [Troubleshooting "access denied" and "user not authorized" RDS issues](https://learn.microsoft.com/en-us/troubleshoot/windows-server/remote/troubleshooting-access-denied-and-user-not-authorized-rds-issues).
- TechTarget: [Fix Windows 11 remote desktop credentials that don't work](https://www.techtarget.com/enterprise-software/tip/Fix-Windows-11-remote-desktop-credentials-that-dont-work).
