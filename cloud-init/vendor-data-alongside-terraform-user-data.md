# Layering extra cloud-init config without fighting Terraform/OpenTofu's auto-generated user-data

When a VM is provisioned with the [`bpg/proxmox`](https://registry.terraform.io/providers/bpg/proxmox) Terraform/OpenTofu provider, the `initialization` block's `user_account`/`ip_config` settings get turned into cloud-init's `user-data` automatically. Wanting to run one extra command at boot — say, disabling `apt`'s daily background timers — doesn't mean hand-editing that generated user-data. Cloud-init has a second, independent input channel for exactly this: **vendor-data**.

## Why vendor-data, not user-data

`vendor_data_file_id` and `user_data_file_id` are genuinely separate attributes on the VM resource's `initialization` block — only `user_data_file_id` conflicts with `user_account` (using one means giving up the other). Vendor-data has no such conflict; it layers on top of whatever the provider is already generating, so extra `runcmd` directives can be added without touching or replacing the provider's own auto-generated config at all.

## The snippet

```yaml
# cloud-init/disable-apt-timers.yaml
#cloud-config
runcmd:
  - systemctl disable --now apt-daily.timer apt-daily-upgrade.timer
  - systemctl mask apt-daily.service apt-daily-upgrade.service
```

## Upload it once, reference it from every VM

```hcl
resource "proxmox_virtual_environment_file" "disable_apt_timers" {
  content_type = "snippets"
  datastore_id = var.storage_pool
  node_name    = var.proxmox_node

  source_raw {
    file_name = "disable-apt-timers.yaml"
    data      = file("${path.module}/cloud-init/disable-apt-timers.yaml")
  }
}
```

```hcl
resource "proxmox_virtual_environment_vm" "example" {
  # ...
  initialization {
    datastore_id        = var.storage_pool
    vendor_data_file_id = proxmox_virtual_environment_file.disable_apt_timers.id
    # ... user_account, ip_config, etc. untouched
  }
}
```

One file, uploaded once, referenced by as many VMs as need it.

## Two things the docs call out explicitly

**Snippets aren't enabled by default.** The Proxmox storage backing `datastore_id` needs the "Snippets" content type turned on first (Datacenter → Storage → the pool → Content). Skip this and `tofu apply` fails cleanly at the upload step — an easy first thing to check if it doesn't work.

**This resource needs SSH, not just the API token.** Per the provider's own docs: "The resource with this content type uses SSH access to the node." Snippet uploads specifically go over SSH rather than the Proxmox API, so the provider's `ssh` block needs to be configured even in an otherwise API-token-only setup — a real exception to "API access is enough for standard VM management," not a hypothetical one.

## It only affects new VMs

Cloud-init runs once, on first boot. A snippet like this changes what happens the *next time* a VM is created from this configuration — it does nothing for VMs that already exist and have already booted. Retrofitting already-running nodes needs a different tool (Ansible, a manual `systemctl mask`, whatever) for that half of the fleet.
