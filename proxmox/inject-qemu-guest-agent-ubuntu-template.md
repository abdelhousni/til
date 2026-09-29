# Injecting qemu-guest-agent into an Ubuntu cloud template, from the CLI

A cloud image straight from Ubuntu doesn't have `qemu-guest-agent` installed, so every VM cloned from a template built on one starts without it — no IP reporting, no clean shutdown/snapshot coordination from Proxmox's side. Two separate things need to be true before it works: the agent package running **inside** the guest, and the guest-agent channel **enabled on the VM** in Proxmox itself ([source](https://pve.proxmox.com/pve-docs/chapter-qm.html)). Missing either one and it silently doesn't work.

## Inject the package into the image before it's ever booted

`virt-customize` (from `libguestfs-tools`) can modify a qcow2 image offline — no VM needs to exist yet:

```sh
apt update
apt install -y libguestfs-tools

IMG=ubuntu-24.04-server-cloudimg-amd64.img
wget -O "$IMG" "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"

virt-customize -a "$IMG" \
  --install qemu-guest-agent \
  --run-command 'systemctl enable qemu-guest-agent.service'
```

Confirm it actually landed before building anything on top of it:

```sh
virt-ls -a "$IMG" /usr/sbin | grep qemu-ga
```

## Build the template, with the Proxmox-side agent flag turned on

```sh
VMID=9000
STORAGE=local-lvm

qm create "$VMID" --name ubuntu-2404-cloudinit --memory 2048 --cores 2 \
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

`--agent enabled=1` is the Proxmox-side switch — it's what unlocks IP reporting and agent-aware shutdown/snapshot behavior for anything cloned from this template, and it's completely independent of whatever's installed inside the guest.

## Verify on a disposable clone, not the template itself

```sh
qm clone 9000 101 --name agent-test --full
qm start 101

# give cloud-init + systemd a moment, then:
qm agent 101 ping
qm guest cmd 101 get-osinfo
```

A successful `qm agent 101 ping` is the real end-to-end confirmation — it means both halves (guest package running, host-side channel enabled) actually connected.

## If the template already exists (retrofit instead of rebuild)

Clone it to a real VM, install normally from inside, then re-templatize:

```sh
qm clone 9000 101 --name ubuntu-template-maintenance --full
qm start 101

# inside the guest:
sudo apt update && sudo apt install -y qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
sudo cloud-init clean --logs
sudo truncate -s 0 /etc/machine-id
sudo poweroff

# back on the Proxmox host, once it's off:
qm template 101
```

The `/etc/machine-id` truncation matters and has an ordering requirement: do it only at the very end, after `cloud-init clean`, and only once the VM is about to become a template — never on a VM you're still actively using. Every clone made from a template regenerates its own machine ID and cloud-init state on first boot; do this too early (or on a running VM you plan to keep using) and you've just broken that VM's own identity for no benefit.
