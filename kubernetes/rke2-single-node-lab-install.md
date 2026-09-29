# Installing a single-node RKE2 server for a lab

Third entry in the RKE2/Kubernetes series. A lab needs the minimum viable cluster: one machine running `rke2-server`, which acts as both control plane and worker — no separate node to join, no `agent` install at all for this size.

## The install script, and one default worth knowing

```sh
curl -sfL https://get.rke2.io | sh -
```

Per [the install script's own source](https://github.com/rancher/rke2/blob/master/install.sh), two defaults matter if you don't set anything: `INSTALL_RKE2_TYPE` defaults to `server` (an `agent` install — a worker joining an existing cluster — is a different, later step, not something a lab node needs), and `INSTALL_RKE2_CHANNEL` defaults to **`stable`**, not `latest`. If you actually want the newest release rather than the last one that's been out long enough to be called stable, that's `INSTALL_RKE2_CHANNEL=latest sh -s -` explicitly — the plain command doesn't give you it by default.

## Enable it, then start it

```sh
systemctl enable rke2-server.service
systemctl start rke2-server.service
```

Two separate commands because `enable` and `start` do different things: `enable` makes it come back on the next boot, `start` makes it run now. Per [RKE2's own quickstart docs](https://docs.rke2.io/install/quickstart), the service is also configured to restart itself automatically after a crash or a kill — the same systemd behavior the earlier [node-maintenance TIL](rke2-node-maintenance-drain-reboot.md) relies on to bring a node back up after a reboot without a manual step.

## Where everything actually lands

- **Data and binaries**: `/var/lib/rancher/rke2`
- **Config file**: `/etc/rancher/rke2/config.yaml` — per [RKE2's own config docs](https://docs.rke2.io/install/configuration), this file **has to be created manually**; nothing scaffolds it for you on install. Its YAML keys mirror the CLI flags directly, a repeatable flag becomes a YAML list, and when both the file and a CLI flag set the same thing, the CLI flag wins — except for repeatable values, where the CLI flag replaces the whole list rather than merging into it.
- **Generated kubeconfig**: `/etc/rancher/rke2/rke2.yaml`

## Worth setting in `config.yaml` before the first start

```yaml
# /etc/rancher/rke2/config.yaml
write-kubeconfig-mode: "0644"
```

The generated kubeconfig at `/etc/rancher/rke2/rke2.yaml` is root-owned and root-only by default — it embeds full cluster-admin credentials, so that's a sensible default, not an oversight. But it also means `kubectl` fails with a permissions error the moment you try it as your own user. `write-kubeconfig-mode` (confirmed as a real, current flag in [RKE2's own server command source](https://github.com/rancher/rke2/blob/master/pkg/cli/cmds/server.go)) is the config-file way to loosen that from install time, rather than hand-editing the file's permissions after every regeneration.

## Where this series goes next

This gets a node running; it doesn't get `kubectl` pointed at it from anywhere but the node itself. The next entry covers why — the generated kubeconfig's server URL points at `127.0.0.1`, which works fine logged into the node directly and breaks the moment you copy that file to your own workstation.
