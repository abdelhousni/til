# A Let's Encrypt certificate for a LAN-only service: Caddy, DNS-01 and deSEC

A follow-up to [ntfy behind Caddy](../proxmox/ntfy-lxc-behind-caddy-tls.md). Caddy's default way of getting a certificate, the *HTTP-01 challenge*, needs Let's Encrypt to reach the server on port 80 from the Internet. A homelab service that stays on the LAN can't do that. The *DNS-01 challenge* proves you control the domain instead: the ACME client (Caddy here) creates a TXT record `_acme-challenge.<name>` through the DNS provider's API, Let's Encrypt checks it, and the record is removed. Nothing needs to be reachable from outside, and it's the only challenge that allows wildcard certificates.

[deSEC](https://desec.io) is a free, non-profit DNS host with an API, and it gives out free subdomains under `dedyn.io`. Caddy talks to it through the [`caddy-dns/desec`](https://pkg.go.dev/github.com/caddy-dns/desec) module.

## 1. A domain and a token at deSEC

Register at desec.io, create a domain such as `myhome.dedyn.io`, and create an API token. A plain token can change any record in the account. deSEC's *token policies* restrict it per record: a deny-by-default policy, plus write access to `_acme-challenge.ntfy` of type `TXT` only (see deSEC's *Token Scoping: Policies*).

Point `ntfy.myhome.dedyn.io` at the proxy's **LAN** address (an `A` record such as `192.168.1.20`). Let's Encrypt never connects to it; LAN clients resolve it and reach Caddy.

## 2. Caddy with the deSEC module

The official Caddy image has no DNS provider modules. Build one with `xcaddy`, the tool that compiles Caddy with extra modules:

```dockerfile
FROM caddy:2.11.7-builder AS builder
RUN xcaddy build v2.11.7 --with github.com/caddy-dns/desec@v1.1.0

FROM caddy:2.11.7
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

```sh
docker build -t caddy-desec:2.11.7 .
docker run --rm caddy-desec:2.11.7 caddy list-modules | grep desec   # dns.providers.desec
```

## 3. The Caddyfile

```caddyfile
{
	acme_dns desec {
		token {env.DESEC_TOKEN}
	}
}

ntfy.myhome.dedyn.io {
	reverse_proxy http://NTFY_LXC_IP:80
}
```

`acme_dns` in the global block applies DNS-01 to every site; for one site only, put `dns desec { token ... }` inside that site's `tls { }` block. `{env.DESEC_TOKEN}` reads the token from the environment, so it stays out of the file:

```sh
docker run -d --name caddy -p 443:443 -e DESEC_TOKEN \
  -v ./Caddyfile:/etc/caddy/Caddyfile:ro -v caddy_data:/data caddy-desec:2.11.7
```

Test against Let's Encrypt's staging CA first, which has much higher rate limits: add `acme_ca https://acme-staging-v02.api.letsencrypt.org/directory` to the global block, then remove it once a staging certificate comes through. Keep the `/data` volume: it holds the account and certificates, and Caddy renews them from there.

## What a failure looks like

With a wrong token, Caddy's log shows each step: the staging order, `trying to solve challenge` with `challenge_type: dns-01`, then deSEC's refusal:

```text
presenting for challenge: adding temporary record for zone "example.dedyn.io.":
retrieving RRSet: unexpected status code 401: {"detail":"Invalid token."}
```

Caddy retries on its own, so fix the token and restart.

## Without Caddy: the Proxmox ACME client

Proxmox VE has its own ACME client (Datacenter, ACME). It reuses acme.sh's DNS plugins, and the admin guide lists `desec` among them: add an ACME account, a DNS challenge plugin of type `desec` with the token, then the domain on the node (Certificates). That route gets a certificate for the Proxmox web UI itself, not for the services behind Caddy.

## Sources

- [`caddy-dns/desec`](https://pkg.go.dev/github.com/caddy-dns/desec) v1.1.0 README: module `dns.providers.desec`, the `acme_dns` and `tls { dns }` syntax.
- Let's Encrypt, *Challenge Types*: HTTP-01 can't issue wildcard certificates, DNS-01 can.
- Proxmox VE admin guide, *Certificate Management*: the ACME client reuses acme.sh DNS plugins, `desec` among them.
- deSEC API docs: *Manage Tokens*, *Token Scoping: Policies*, *TLS Certificates with Let's Encrypt* (acme.sh among supported clients).
- Tested on 2026-10-06: the image above builds with Caddy v2.11.7 and lists `dns.providers.desec`; `caddy validate` accepts the Caddyfile; against Let's Encrypt staging with a placeholder domain and an invalid token, Caddy reached deSEC's API and got the 401 above. A real issuance needs a deSEC account and wasn't run here; neither were the token policies nor the Proxmox ACME client.
