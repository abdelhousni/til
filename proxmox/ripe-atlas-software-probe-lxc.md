# Installing a RIPE Atlas software probe in a Proxmox LXC

[RIPE Atlas](https://atlas.ripe.net/) probes are little devices (or software) that measure Internet connectivity from wherever you run them, and contribute that data back to a global measurement network. I wanted to run one from my homelab without dedicating a whole VM to it, so it's a good fit for a small unprivileged LXC container on Proxmox.

The current official probe is a plain Debian/RPM package, not a Docker image — earlier guides mentioning a `ripencc/ripe-atlas` container are out of date. That's actually good news for an LXC: no nesting, no privileged container, no Docker-in-LXC gymnastics needed.

## 1. Create the container

Any small **unprivileged** Debian 12/13 LXC works. From the Proxmox GUI: `Create CT`, pick a Debian 12 or 13 template, 1 core / 512MB RAM / a few GB disk is plenty, leave nesting/privileged unset (defaults are fine). Or from the host shell:

```sh
pct create 200 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname ripe-atlas --unprivileged 1 --cores 1 --memory 512 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp --rootfs local-lvm:4
pct start 200
pct enter 200
```

## 2. Install the probe package

Run inside the container. This follows the [official install steps](https://github.com/RIPE-NCC/ripe-atlas-software-probe#installation) exactly — download the RIPE NCC apt repo package, verify its checksum, then install the probe from that repo:

```sh
apt update && apt install -y wget
ARCH=$(dpkg --print-architecture)
CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
REPO_PKG=ripe-atlas-repo_1.6-1_all.deb
wget "https://ftp.ripe.net/ripe/atlas/software-probe/debian/dists/$CODENAME/main/binary-$ARCH/$REPO_PKG" \
  https://github.com/RIPE-NCC/ripe-atlas-software-probe/releases/latest/download/CHECKSUMS
grep -q "$(sha256sum "$REPO_PKG")" CHECKSUMS && echo "checksum OK" || echo "checksum MISMATCH -- stop here"

dpkg -i "$REPO_PKG" && rm "$REPO_PKG"
apt update
apt-get install -y ripe-atlas-probe
```

The package's postinst script generates an ed25519 keypair on first install (`/etc/ripe-atlas/probe_key` / `probe_key.pub`) and prints a registration URL with the public key already embedded in it — that's the only output you need to pay attention to.

## 3. Register the probe

Copy the registration URL the installer printed (it looks like `https://atlas.ripe.net/register/swprobe?key=...`), open it in a browser, and sign in with a RIPE Atlas account. If you missed the output, the key is still on disk:

```sh
cat /etc/ripe-atlas/probe_key.pub
```

and you can build the same URL yourself from the raw public key at <https://atlas.ripe.net/register/swprobe>.

## 4. Start it

The package does **not** auto-start the service — that's deliberate, so you register before it starts phoning home:

```sh
systemctl enable --now ripe-atlas.service
systemctl status ripe-atlas.service
```

It can take a few minutes for the probe to show up as "Connected" on its page under [atlas.ripe.net/probes/mine](https://atlas.ripe.net/probes/mine).

## Why this works fine unprivileged

The probe ships its own busybox binary for ping/traceroute-style measurements and grants it raw-socket access via a Linux file capability (`setcap cap_net_raw=ep`) at install time, rather than needing the whole process to run as root. File capabilities work fine inside an unprivileged LXC's own user namespace, so there was no need to reach for a privileged container just to let it send ICMP packets.

## Result

Mine has been up and connected since following these exact steps — you can see it live at [atlas.ripe.net/probes/1017419](https://atlas.ripe.net/probes/1017419/), quietly contributing measurements from a 512MB unprivileged LXC that costs nothing extra to run alongside everything else on the same Proxmox host.
