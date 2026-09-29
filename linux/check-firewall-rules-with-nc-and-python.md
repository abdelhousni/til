# Checking new firewall rules with nc and Python: open, refused, or dropped

The security team has opened these flows for `dar-servera`:

| Direction | Flow | Ports |
|---|---|---|
| In | from `dar-serverb` and `laptop-abdel` | 80 (http), 443 (https), 22 (ssh), 3306 (mysql) |
| Out | to the Git server | 22 (ssh), 443 (https) |

Checking them takes two tools that are almost always there, `nc` and `python3`. It also takes knowing which of three answers you got. Everything below was run with OpenBSD `nc` 1.234 (the Debian/Ubuntu `netcat-openbsd`), Nmap `ncat` 7.99 (what `nc` is on RHEL), and Python 3.11.

## The three answers a TCP check can give

```sh
nc -zv -w 3 dar-servera 3306
```

`-z` connects and closes without sending data, `-v` prints the result, and `-w 3` gives up after 3 seconds.

| Result | OpenBSD `nc` | `ncat` | Meaning |
|---|---|---|---|
| **Open** | `Connection to … 3306 port [tcp/mysql] succeeded!` | `Ncat: Connected to …:3306.` | Flow allowed, service listening |
| **Refused** | `connect to … port 3306 (tcp) failed: Connection refused` | `Ncat: Connection refused.` | **The firewall let it through**; nothing listens on that port |
| **Dropped** | `connect to … port 3306 (tcp) timed out` | `Ncat: TIMEOUT.` | No answer: a firewall is dropping it (or the host is down) |

"Refused" is good news for the firewall ticket: the packet reached `dar-servera`, and its kernel answered. "Timed out" is the one to send back to the security team.

Two variants to recognize:
- `No route to host` usually means a firewall that *rejects* instead of dropping. firewalld's default reject does that.
- `Name or service not known` is DNS, not the firewall.

Both commands exit with 0 for open and 1 otherwise, so they work in a loop:

```sh
for p in 80 443 22 3306; do nc -zv -w 3 dar-servera "$p"; done
```

## Before the service exists: listen yourself

Rules often open before MySQL is installed, so every check would say "refused". Put a listener on `dar-servera` first, then test from `dar-serverb` or `laptop-abdel`:

```sh
# on dar-servera; ports below 1024 need sudo, and the port must be free
sudo nc -lk 3306      # OpenBSD nc; ncat: sudo ncat -lk 3306
```

```sh
# on dar-serverb or laptop-abdel
nc -zv -w 3 dar-servera 3306
```

Without `-k`, the listener exits after the first connection. For 80, Python does the same job and also answers HTTP: `sudo python3 -m http.server 80`. Stop the listener before the real service starts; it holds the port.

## Outbound from dar-servera to Git

Run from `dar-servera`, replacing `github.com` with your Git server:

```sh
nc -zv -w 3 github.com 22
nc -zv -w 3 github.com 443
```

Then use the real protocol. It also checks what a port test can't, such as a TLS-inspecting proxy or the SSH host key:

```sh
ssh -T git@github.com                      # "Permission denied (publickey)" still proves port 22 works
curl -sS -o /dev/null -w '%{http_code}\n' https://github.com
git ls-remote https://github.com/abdelhousni/til HEAD
```

## UDP: `nc -uz` can't tell you

UDP has no handshake, so there's no "connected" to report. Probing an address that doesn't answer:

```text
$ nc -uzv -w 2 10.255.255.1 5140
Connection to 10.255.255.1 5140 port [udp/*] succeeded!
```

`ncat -uz` says `UDP packet sent successfully`. Both exit 0 for a packet that went nowhere. The only way to prove a UDP flow is to have something on the other side print what arrives:

```sh
nc -ul 5140                                     # on the receiving host
echo "hello from laptop-abdel" | nc -u -w 1 dar-servera 5140   # on the sender
```

If the text appears on the receiving host, the flow works. If nothing appears, it doesn't, whatever the sender printed.

## Without nc: Python

`portcheck.py`, standard library only:

```python
#!/usr/bin/env python3
"""portcheck.py HOST PORT [PORT...] -- TCP: open, refused or dropped."""
import socket, sys

host, ports = sys.argv[1], sys.argv[2:]
for port in ports:
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            result = "open"
    except ConnectionRefusedError:
        result = "refused  (host reached, nothing listening)"
    except (socket.timeout, TimeoutError):
        result = "dropped  (no answer: firewall?)"
    except OSError as e:
        result = f"error    ({e.strerror or e})"
    print(f"{host}:{port:<5} {result}")
```

Example output, while MySQL isn't installed yet:

```text
$ python3 portcheck.py dar-servera 80 443 22 3306
dar-servera:80    open
dar-servera:443   open
dar-servera:22    open
dar-servera:3306  refused  (host reached, nothing listening)
```

A UDP listener, and a sender, in one line each:

```sh
python3 -c 'import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(("0.0.0.0",5140));print(*s.recvfrom(1024))'
python3 -c 'import socket;socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(b"ping",("dar-servera",5140))'
```

## One more thing to rule out

A timeout can also come from the host firewall on `dar-servera` itself, not the network one: firewalld, ufw, or nftables. Check with `sudo firewall-cmd --list-all` or `sudo nft list ruleset` before reopening the ticket.

## Sources

- The outputs above: OpenBSD `nc` 1.234, Nmap `ncat` 7.99 and Python 3.11. A local listener gave "open", a closed port gave "refused", and an unroutable address (`10.255.255.1`) gave "dropped" and the UDP false positive.
- `nc(1)` from OpenBSD netcat, and the [Ncat reference guide](https://nmap.org/book/ncat-man.html).
- Python's [`socket.create_connection`](https://docs.python.org/3/library/socket.html#socket.create_connection).
