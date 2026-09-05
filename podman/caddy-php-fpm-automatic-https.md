# Hosting a simple PHP page with Podman + Caddy, with automatic HTTPS

I wanted to serve a small PHP page with a real Let's Encrypt certificate, without installing PHP, a web server, or certbot on the host. Two rootless Podman containers do the whole job: [Caddy](https://caddyserver.com/) as reverse proxy (it manages the certificate itself) talking FastCGI to a plain `php-fpm` container.

## Layout

```
myapp/
├── app/
│   └── index.php
└── Caddyfile
```

```php
<?php
echo "Hello from PHP " . phpversion() . " behind Caddy on Podman!";
```

```
example.com {
    root * /srv
    encode gzip
    php_fastcgi php:9000
    file_server
}
```

Replace `example.com` with a real domain whose DNS already points at this host — Caddy's automatic HTTPS needs a public domain to request a certificate for, it won't work against `localhost` or a bare IP. Caddy's [`php_fastcgi` directive](https://caddyserver.com/docs/caddyfile/directives/php_fastcgi) is the one doing the interesting work here: it sets up the `try_files`-style fallback to `index.php` and proxies `.php` requests over FastCGI, but it still needs `root` (so it knows the webroot) and `file_server` (to serve anything that isn't PHP) alongside it.

## Run it

A shared network first, so Caddy can resolve the PHP container by name — Podman's `aardvark-dns` gives every container on a custom bridge network working name resolution automatically:

```sh
podman network create webnet
```

The PHP-FPM container, with the app code mounted read-only:

```sh
podman run -d --name php \
  --network webnet \
  -v ./app:/srv:ro \
  php:8.3-fpm-alpine
```

Then Caddy, on the same network, with the same app directory mounted for `file_server`, plus a **named volume for `/data`**:

```sh
podman run -d --name caddy \
  --network webnet \
  -p 80:80 -p 443:443 \
  -v ./Caddyfile:/etc/caddy/Caddyfile:ro \
  -v ./app:/srv:ro \
  -v caddy_data:/data \
  caddy:2-alpine
```

That's it — visit `https://example.com` and Caddy requests and installs the certificate on first hit, no separate ACME client, no renewal cron job (Caddy renews automatically well before expiry).

## Two things that will trip you up

**The `caddy_data` volume is not optional.** That's where Caddy keeps its ACME account and issued certificates. Skip it (or use an anonymous volume that gets discarded on container removal) and every time you recreate the container, Caddy requests a brand new certificate — which is exactly the pattern Let's Encrypt's rate limits exist to catch. A named volume keeps the certificate across container restarts and re-creates.

**Rootless Podman can't bind ports 80/443 by itself.** Ports below 1024 are privileged, and rootless containers run as your unprivileged user, so `-p 80:80 -p 443:443` will fail with a permission error out of the box. Either:

- Lower the host's unprivileged port floor once: `sudo sysctl net.ipv4.ip_unprivileged_port_start=80` (persist it in `/etc/sysctl.d/`), or
- Run these two containers rootful (as root, or via a rootful Podman socket), or
- Publish to high ports (`-p 8080:80 -p 8443:443`) and put something else in front that can bind 80/443.

I went with the sysctl change — it's a one-line, one-time fix and keeps everything else rootless.

## Result

`podman ps` shows both containers running, `https://example.com` serves the PHP page with a valid padlock, and there's nothing PHP- or web-server-related installed on the host itself — just Podman.
