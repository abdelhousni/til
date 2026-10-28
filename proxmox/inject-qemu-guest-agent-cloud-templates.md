# Injecting qemu-guest-agent into Debian, Ubuntu, RHEL-family and openSUSE cloud templates, from the CLI

A **cloud image** is a disk image a distribution publishes with the OS already installed, meant to be configured at first boot rather than through an installer. On Proxmox you import one as a VM's disk, add a **cloud-init** drive (cloud-init is the program inside the image that applies SSH keys, users and network settings on first boot), and turn the VM into a **template**: a read-only VM that you clone instead of starting. Most of these images come as **qcow2**, QEMU's disk-image format.

Not every cloud image ships `qemu-guest-agent`, the small daemon that lets the Proxmox host talk to the guest: report its IP addresses, shut it down cleanly, freeze its filesystems during a backup ([source](https://pve.proxmox.com/wiki/Qemu-guest-agent)). Ubuntu's and Debian's `genericcloud` images don't have it, so every VM cloned from a template built on one starts without it. Two separate things need to be true before it works: the agent package running **inside** the guest, and the guest-agent channel **enabled on the VM** in Proxmox itself ([source](https://pve.proxmox.com/pve-docs/chapter-qm.html)). Missing either one and it silently doesn't work. Having cloud-init doesn't say anything about the agent either: they are separate packages.

Three components get confused here, so keep them apart:

| Component | Where it runs | What it does |
|---|---|---|
| QEMU/KVM | Proxmox host | Runs the VM. Nothing of it is installed in the guest. |
| `qemu-guest-agent` | Inside the guest | Answers the host's requests (IP, shutdown, freeze/thaw). |
| cloud-init | Inside the guest | Applies the first-boot settings from the cloud-init drive. |

## Which image to download

Each distribution publishes several cloud images; take the generic one for KVM/OpenStack, not a provider-specific one such as an AWS EC2 image. Proxmox's cloud-init support reads the same configuration drive that OpenStack images expect ([source](https://pve.proxmox.com/wiki/Cloud-Init_Support)).

| Distribution | Image to look for | Format | Catalog |
|---|---|---|---|
| Debian | `genericcloud` or `generic` | `.qcow2` | [cloud.debian.org](https://cdimage.debian.org/cdimage/cloud/) |
| Ubuntu Server LTS | `server-cloudimg` | `.img`, but qcow2 inside | [cloud-images.ubuntu.com](https://cloud-images.ubuntu.com/) |
| AlmaLinux | `GenericCloud` | `.qcow2` | [AlmaLinux wiki](https://wiki.almalinux.org/cloud/Generic-cloud.html) |
| Rocky Linux | `GenericCloud-Base` | `.qcow2` | [rockylinux.org/download](https://rockylinux.org/download) |
| Fedora Cloud | Cloud Base, QEMU | `.qcow2` | [fedoraproject.org/cloud](https://fedoraproject.org/cloud/download/) |
| RHEL 10 | KVM Guest Image | `.qcow2` | [Red Hat downloads](https://access.redhat.com/downloads/content/rhel) (Red Hat account needed) |
| openSUSE Leap 16.0 | `Minimal-VM` … `Cloud` | `.qcow2` | [download.opensuse.org](https://download.opensuse.org/distribution/leap/16.0/appliances/) |

RHEL, AlmaLinux, Rocky Linux and Fedora are the **RHEL family**: Fedora is where RHEL's changes start, AlmaLinux and Rocky Linux are rebuilt from RHEL's sources, so all four share the `dnf` package manager, the package names and SELinux, and one procedure covers them below. openSUSE is a separate family with its own package manager, `zypper`, but the package is also called `qemu-guest-agent`. What differs between the images:

- **Debian**: `genericcloud` drops most kernel hardware drivers that a VM doesn't need; `generic` keeps them. Both run cloud-init. The image called `nocloud` does *not* run cloud-init, despite sharing a name with cloud-init's NoCloud datasource ([source](https://cdimage.debian.org/cdimage/cloud/)).
- **Ubuntu**: `noble-server-cloudimg-amd64.img` is already qcow2 ([source](https://ubuntu.com/docs/public-images/public-images-how-to/launch-with-libvirt/)). Don't convert it because of the extension; `qemu-img info` shows the real format.
- **RHEL 10**: the image isn't on a public mirror. Download it from the Red Hat Customer Portal with an account; the no-cost Red Hat Developer subscription is enough. Its package repositories also need that subscription, which changes the injection step below.
- **openSUSE Leap**: the `Minimal-VM` appliance comes in several variants; take the one named `Cloud`, which runs cloud-init. The `kvm-and-xen` variant configures itself at first boot with openSUSE's own tools (jeos-firstboot, Combustion) instead, so a Proxmox cloud-init drive does nothing to it.

The URLs used below, all for x86_64:

```sh
# Debian 13
https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2
# Ubuntu 24.04 LTS
https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
# AlmaLinux 10
https://repo.almalinux.org/almalinux/10/cloud/x86_64/images/AlmaLinux-10-GenericCloud-latest.x86_64.qcow2
# Rocky Linux 10
https://dl.rockylinux.org/pub/rocky/10/images/x86_64/Rocky-10-GenericCloud-Base.latest.x86_64.qcow2
# openSUSE Leap 16.0
https://download.opensuse.org/distribution/leap/16.0/appliances/Leap-16.0-Minimal-VM.x86_64-Cloud.qcow2
```

Fedora's file names carry the release and build number, so copy the current one from its download page.

## Check whether the image already has the agent

`virt-ls`, from `libguestfs-tools`, lists files inside a disk image without booting it. Debian-family images install the agent as `/usr/sbin/qemu-ga`, RHEL-family and openSUSE ones as `/usr/bin/qemu-ga`:

```sh
apt update
apt install -y libguestfs-tools

IMG=debian-13-genericcloud-amd64.qcow2
wget -O "$IMG" "https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2"

qemu-img info "$IMG" | grep 'file format'
virt-ls -a "$IMG" /usr/sbin /usr/bin | grep qemu-ga
```

No output from the last line means the agent isn't there. Run it on every image you download: what a distribution includes can change between releases.

## Inject the package into the image before it's ever booted

`virt-customize`, from the same package, modifies a disk image offline, so no VM needs to exist yet. For Debian and Ubuntu:

```sh
virt-customize -a "$IMG" \
  --install qemu-guest-agent \
  --run-command 'systemctl enable qemu-guest-agent.service'
```

For the RHEL family, one command covers all four distributions. Two things differ from Debian:

- `--selinux-relabel`. These images run **SELinux**, which labels every file with a security context; files written from outside the running system get no label, and a guest with unlabelled files can refuse to boot or to start the service. The option relabels the files on the way out.
- On RHEL only, `--install` fails on an image that isn't registered, because its repositories need a subscription. `virt-customize` can register the image, install, and unregister it again, so the template doesn't carry your registration into every clone. The `SM` array holds those options for RHEL and stays empty for AlmaLinux, Rocky Linux and Fedora:

```sh
SM=()    # AlmaLinux, Rocky Linux, Fedora

# RHEL 10 only:
SM=(--sm-credentials "$RH_USER:password:$RH_PASSWORD" --sm-register --sm-attach auto)

virt-customize -a "$IMG" \
  "${SM[@]}" \
  --install qemu-guest-agent \
  --run-command 'systemctl enable qemu-guest-agent.service' \
  ${SM:+--sm-unregister} \
  --selinux-relabel
```

`${SM:+--sm-unregister}` expands to `--sm-unregister` only when `SM` is set, so the unregistering happens only on an image that was registered. `--sm-credentials` takes `USER:password:PASSWORD`, or `USER:file:FILENAME` to read the password from a file instead of the command line.

For openSUSE Leap, `--install` calls `zypper` inside the image, and the command is Debian's plus the relabel: Leap 16.0 runs SELinux too, and on an image without it the option does nothing:

```sh
virt-customize -a "$IMG" \
  --install qemu-guest-agent \
  --run-command 'systemctl enable qemu-guest-agent.service' \
  --selinux-relabel
```

If the `virt-ls` check above already found `qemu-ga`, drop the `--install` line (and, on RHEL, the `SM` options) and keep the `systemctl enable` and the relabel.

Then run the `virt-ls` check again before building anything on top of the image.

## Build the template, with the Proxmox-side agent flag turned on

The same commands work for every distribution; only the name changes:

```sh
VMID=9000
STORAGE=local-lvm

qm create "$VMID" --name debian-13-cloudinit --memory 2048 --cores 2 \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci

qm importdisk "$VMID" "$IMG" "$STORAGE"

qm set "$VMID" \
  --scsi0 "${STORAGE}:vm-${VMID}-disk-0,discard=on,ssd=1" \
  --boot order=scsi0 \
  --ide2 "${STORAGE}:cloudinit" \
  --serial0 socket --vga serial0 \
  --agent enabled=1

qm template "$VMID"
```

`--agent enabled=1` is the Proxmox-side switch: it adds the virtio serial port the agent talks through, for anything cloned from this template, and it's independent of whatever's installed inside the guest. On an existing VM, `qm set <vmid> --agent 1` does the same; the VM needs a full stop and start, not a reboot from inside, before the port appears.

## Verify on a disposable clone, not the template itself

```sh
qm clone 9000 101 --name agent-test --full
qm start 101

# give cloud-init + systemd a moment, then:
qm agent 101 ping
qm guest cmd 101 get-osinfo
```

A successful `qm agent 101 ping` is the end-to-end confirmation: both halves (guest package running, host-side channel enabled) connected. Check cloud-init separately, for example by logging in with the SSH key you set on the clone: a working agent doesn't prove cloud-init ran, and the reverse.

## If the template already exists (retrofit instead of rebuild)

Clone it to a real VM, install normally from inside, then re-templatize:

```sh
qm clone 9000 101 --name template-maintenance --full
qm start 101
```

Inside a Debian or Ubuntu guest:

```sh
sudo apt update && sudo apt install -y qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
```

Inside a RHEL 10, AlmaLinux, Rocky Linux or Fedora guest; the two `subscription-manager` lines are for RHEL only:

```sh
sudo subscription-manager register    # RHEL only
sudo dnf install -y qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
sudo subscription-manager unregister  # RHEL only
```

Inside an openSUSE Leap guest:

```sh
sudo zypper --non-interactive install qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
```

`enable --now` starts the agent and also starts it on every later boot; whether the package does the second part by itself differs between distributions. Then, on any of them:

```sh
sudo cloud-init clean --logs
sudo truncate -s 0 /etc/machine-id
sudo poweroff

# back on the Proxmox host, once it's off:
qm template 101
```

The `/etc/machine-id` truncation matters and has an ordering requirement: do it only at the very end, after `cloud-init clean`, and only once the VM is about to become a template, never on a VM you're still using. Every clone made from a template regenerates its own machine ID and cloud-init state on first boot; do this too early (or on a running VM you plan to keep using) and you've broken that VM's own identity for no benefit.

The five image URLs above were checked to resolve. The `qm` commands need a Proxmox host and the RHEL 10 steps a Red Hat account; neither was run for the distributions this revision added (Debian, AlmaLinux, Rocky Linux, Fedora, RHEL 10, openSUSE Leap).
