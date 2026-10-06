# ntfy in a Proxmox LXC, private and behind Caddy for TLS

[ntfy](https://ntfy.sh/) is a self-hosted push notification server: a script publishes a message to a *topic* with one HTTP request, and phones or browsers subscribed to that topic receive it. It's a good alert channel for a homelab. This entry installs it as an LXC (a lightweight Linux container managed by Proxmox, sharing the host's kernel) and puts it behind a reverse proxy that handles HTTPS, with anonymous access turned off.

## Install the LXC

The [Community Scripts](https://community-scripts.org/scripts/ntfy) page gives the command to run in the Proxmox host shell:

```sh
var_os='debian' bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/ntfy.sh)"
```

Its default profile is Debian 13, 1 CPU, 512 MB RAM and 2 GB disk; ntfy listens on **plain HTTP, port 80**, and its config is `/etc/ntfy/server.yml`. The page listed ntfy v2.28.0 on 2026-10-06.

## Does it need TLS?

Not on a trusted LAN. Over plain HTTP, though, messages, topic names, passwords and tokens travel unencrypted. Add HTTPS as soon as you use passwords or tokens, reach it from outside the LAN (the phone app away from home), or send anything sensitive.

The usual layout keeps ntfy on HTTP and puts a **reverse proxy** in front: a server that receives the HTTPS connections, decrypts them (*TLS termination*) and forwards the requests to ntfy. ntfy can serve HTTPS itself (`listen-https`, `cert-file`, `key-file`), but then it has to manage certificates.

## Configure ntfy

In `/etc/ntfy/server.yml` in the LXC:

```yaml
base-url: "https://ntfy.example.net"
listen-http: ":80"
behind-proxy: true
auth-file: "/var/lib/ntfy/user.db"
auth-default-access: "deny-all"
```

- `behind-proxy: true`: ntfy rate-limits per visitor IP. Behind a proxy, every request comes from the proxy's IP, so without this setting all visitors share one limit. With it, ntfy reads the real IP from `X-Forwarded-For`.
- `auth-file` turns on users and access control. The default access is **read-write for everyone**, so anyone who can reach the server can read and write every topic.
- `auth-default-access: "deny-all"` makes the instance private: nothing works without an account.

Restart it (`systemctl restart ntfy`, the Debian package's service), then add users. Users have a role (`admin` can read and write everything), regular users get per-topic rights (an *ACL*, access control list), and a *token* lets a script authenticate without a password:

```sh
ntfy user add --role=admin admin       # for the phone app
ntfy user add backup                   # for the scripts
ntfy access backup alerts write-only
ntfy token add backup                  # prints tk_...
```

## Caddy in front

[Caddy](https://caddyserver.com/) gets certificates on its own ([as in this entry](../podman/caddy-php-fpm-automatic-https.md)). With a public DNS name pointing at the proxy, and ports 80 and 443 reachable for Let's Encrypt:

```caddyfile
ntfy.example.net {
    reverse_proxy http://NTFY_LXC_IP:80
}
```

LAN-only, add `tls internal`: Caddy signs the certificate with its own local CA (`/data/caddy/pki/authorities/local/root.crt` in the Caddy container), which clients must then trust. ntfy's docs note that Caddy's `reverse_proxy` handles WebSockets too, with no extra config.

## Check it

```sh
curl -d "hi" https://ntfy.example.net/alerts                     # 403 forbidden
curl -H "Authorization: Bearer tk_..." -H "Title: backup" \
     -d "nightly backup ok" https://ntfy.example.net/alerts      # 200
curl -u admin "https://ntfy.example.net/alerts/json?poll=1"       # the message
```

With the setup above, in containers (ntfy 2.28.0 behind Caddy 2 with `tls internal`):

| Request | Result |
|---|---|
| anonymous publish or read | 403 |
| `backup` token, publish to `alerts` | 200 |
| `backup` token, read `alerts` (write-only) | 403 |
| `backup` token, publish to another topic | 403 |
| `admin`, read `alerts` | the message |
| `http://` GET through Caddy | 308 to `https://` |

Expose only Caddy's ports; keep the LXC's port 80 reachable from the proxy alone, since direct HTTP bypasses TLS.

## Sources

- ntfy docs: [configuration](https://docs.ntfy.sh/config/) (`behind-proxy`, `auth-file`, `auth-default-access`, users, ACL and tokens, the Caddy example) and [installation](https://docs.ntfy.sh/install/) (the `ntfy` systemd service of the deb package).
- Community Scripts [ntfy page](https://community-scripts.org/scripts/ntfy), 2026-10-06: port 80, `/etc/ntfy/server.yml`, Debian 13 default.
- Tested on 2026-10-06 with `binwiederhier/ntfy:v2.28.0` and `caddy:2` containers on one Docker network: the table above. The `binwiederhier/ntfy` image has no `/var/lib/ntfy`, so the test mounted a volume there; the LXC install itself wasn't run here.
