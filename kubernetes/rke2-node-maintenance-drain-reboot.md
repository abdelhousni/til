# Cleanly stopping an RKE2 node for planned maintenance

Draining and stopping a node the right way for a patch/reboot is mostly ordinary Kubernetes practice; the one RKE2-specific trap is reaching for the wrong bundled script to actually stop it.

## The sequence

```sh
# 1. Move workloads off first
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data

# 2. Stop RKE2 cleanly
systemctl stop rke2-server   # control-plane / server node
systemctl stop rke2-agent    # worker / agent node

# ... patch, reboot, whatever the maintenance is ...

# 3. RKE2 is enabled in systemd, so it starts itself on boot.
# Once the node's Ready again:
kubectl uncordon <node>
```

`kubectl drain` cordons the node for you (no separate `kubectl cordon` needed first), evicts pods respecting PodDisruptionBudgets, and `--ignore-daemonsets` skips the daemonset pods that would otherwise block it forever, since a daemonset pod is supposed to run on every node. `--delete-emptydir-data` is what lets it proceed past pods using `emptyDir` volumes, whose data doesn't survive a reschedule anyway.

**A PDB with no room to evict will hang the drain.** `kubectl get pdb -A` before draining anything with a `minAvailable`/`maxUnavailable` that leaves zero slack — a single-replica deployment behind a PDB requiring 1 available is the classic way to watch `kubectl drain` sit there.

## The one thing that's actually RKE2-specific: don't use `rke2-killall.sh` for this

RKE2 ships an `rke2-killall.sh` alongside the binaries. It sounds like exactly what you'd want to stop a node — it is not. Reading [the script itself](https://github.com/rancher/rke2/blob/master/bundle/bin/rke2-killall.sh), after stopping the services it also force-kills every containerd-shim process tree, unmounts and **deletes** the kubelet pod and CNI mount points, deletes the CNI network interfaces (`cni0`, `flannel.*`, Calico/Cilium interfaces), removes the static pod manifests for `etcd`/`kube-apiserver`/`kube-scheduler`/etc., and strips Kubernetes/CNI rules out of `iptables`. That's a full teardown for an uninstall or a hard reset — not a stop-start-cleanly step. A plain `systemctl stop rke2-server`/`rke2-agent` is the actual clean stop; RKE2's [own uninstall docs](https://docs.rke2.io/install/uninstall) only ever call it out for removing RKE2 entirely, never for a reboot.

## Control-plane nodes: mind etcd quorum

If the node being rebooted runs `rke2-server` with the embedded etcd datastore, only take down **one at a time**. Per [RKE2's own HA install docs](https://docs.rke2.io/install/ha), quorum for `n` servers is `(n/2)+1` — for the standard 3-server cluster that's 2, meaning exactly one server can be unavailable before the cluster loses write quorum. Draining and rebooting a second server before the first has fully rejoined isn't a maintenance window anymore, it's an outage.

[RKE2's manual upgrade guide](https://docs.rke2.io/upgrades/manual) documents the same one-at-a-time rule for version upgrades specifically: servers first, one at a time, agents after — the same sequencing applies whether you're changing the RKE2 version or just rebooting for OS patches.
