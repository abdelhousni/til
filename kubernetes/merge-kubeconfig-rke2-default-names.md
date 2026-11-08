# Two RKE2 kubeconfigs merge into one cluster: rename before you merge

Sixteenth entry in the RKE2/Kubernetes series. [The off-node `kubectl` entry](kubectl-off-node-rke2-tls-san.md) copied one cluster's `rke2.yaml` to a workstation and pointed `kubectl` at it with `KUBECONFIG` or `--kubeconfig`. A second cluster brings a second file, and the usual next step is to merge both into `~/.kube/config` so that one file reaches every cluster. With two RKE2 files, that merge loses the second cluster and prints no error. This entry shows why, renames the entries with `kubectl` alone, and then merges safely.

## What a kubeconfig holds

A kubeconfig is the YAML file `kubectl` reads to find a cluster and log in to it. Per [Kubernetes' kubeconfig docs](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/), it has three lists of named entries and one pointer:

- **clusters**: where the API server is (`server:`) and the CA certificate that signed its TLS certificate (`certificate-authority-data:`).
- **users**: the credentials, which for RKE2's admin file are a client certificate and its private key (`client-certificate-data:`, `client-key-data:`).
- **contexts**: a name for a pair of one cluster and one user, the thing you switch between.
- **`current-context`**: the context `kubectl` uses when you don't pass `--context`.

Entries refer to each other by name: a context says `cluster: default` and `user: default`, and `kubectl` looks those names up in the other two lists.

RKE2 writes its admin kubeconfig to [`/etc/rancher/rke2/rke2.yaml`](https://docs.rke2.io/cluster_access) on each server, and by default the cluster, the user and the context in it are all called `default`:

```yaml
clusters:
- cluster:
    certificate-authority-data: LS0t...
    server: https://127.0.0.1:6443
  name: default
contexts:
- context:
    cluster: default
    user: default
  name: default
current-context: default
users:
- name: default
  user:
    client-certificate-data: LS0t...
    client-key-data: LS0t...
```

The name comes from k3s, which RKE2 builds its server on. k3s's [`WriteClientKubeConfig`](https://github.com/k3s-io/k3s/blob/master/pkg/clientaccess/kubeconfig.go) uses one name for all three entries, taken from the server option [`write-kubeconfig-name`](https://github.com/k3s-io/k3s/blob/master/pkg/cli/cmds/server.go), whose default is `default`. RKE2 passes that option through [since v1.37.0+rke2r1](https://github.com/rancher/rke2/blob/master/pkg/cli/cmds/server.go) (tagged 2026-09-10). The 1.34, 1.35 and 1.36 lines don't have it, and RKE2's [server configuration reference](https://docs.rke2.io/reference/server_config) doesn't list it yet. On 1.37 and later, a line in the server's `/etc/rancher/rke2/config.yaml` names the entries at the source:

```yaml
write-kubeconfig-name: rke2-second
```

This option wasn't run here. Everything below works on any version, and on a file already copied off a node.

## How kubectl merges, and why one cluster disappears

`KUBECONFIG` can hold several files, [separated by `:` on Linux and macOS and by `;` on Windows](https://kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/#set-the-kubeconfig-environment-variable). `kubectl` then merges them as it reads. The [merge rules](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/#merging-kubeconfig-files) are short:

- The first file to set a particular value or map key wins.
- A later file never changes it. If two files define the same user, only the first file's values are used, "even if the second file has non-conflicting entries" under it.
- The first file to set `current-context` keeps it.

Two RKE2 files define a cluster, a user and a context all named `default`, so the first file wins on all three and nothing from the second survives. With a lab already in `~/.kube/config` and a second cluster's file in `~/.kube/rke2-second.yaml`:

```console
$ KUBECONFIG=~/.kube/config:~/.kube/rke2-second.yaml kubectl config view --raw | grep server
    server: https://192.0.2.10:6443
```

One server, the first one. `kubectl config get-contexts` lists a single `default`, which answers from the first cluster, and no command warns that the second file was read at all. Swapping the order in `KUBECONFIG` swaps which cluster you get, still with no warning.

## Rename the entries, with kubectl alone

The fix is to give the second file's entries their own names before it meets the first. `kubectl config rename-context` renames a context, but `kubectl config` has no command to rename a cluster or a user. They can still be rebuilt under a new name with `kubectl` itself: `set-cluster` and `set` write the new entries, `set-context` ties them together, and `delete-*` removes the old ones.

[`kubectl config set`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_config/kubectl_config_set/) writes any field by its path, such as `users.<name>.client-key-data`. For the `*-data` fields it expects the value in base64, which is the form `kubectl config view --raw` prints, so a value can be copied across unchanged.

Run against the copied file only, never against `~/.kube/config`:

```sh
F=~/.kube/rke2-second.yaml     # the copied rke2.yaml
N=rke2-second                  # the new name, for all three entries
SERVER=https://192.0.2.20:6443 # the node's address, not 127.0.0.1

k()   { kubectl --kubeconfig="$F" "$@"; }
get() { k config view --raw -o jsonpath="$1"; }

k config set-cluster "$N" --server="$SERVER"
k config set "clusters.$N.certificate-authority-data" "$(get '{.clusters[0].cluster.certificate-authority-data}')"
k config set "users.$N.client-certificate-data" "$(get '{.users[0].user.client-certificate-data}')"
k config set "users.$N.client-key-data" "$(get '{.users[0].user.client-key-data}')"
k config set-context "$N" --cluster="$N" --user="$N"
k config use-context "$N"
k config delete-context default
k config delete-cluster default
k config delete-user default
```

`--kubeconfig` makes every command read and write that one file and nothing else, even if `KUBECONFIG` is exported in your shell. The `[0]` works because RKE2 writes exactly one cluster and one user. The `server:` line also replaces the `127.0.0.1` that the off-node entry had to edit by hand.

The file now says `rke2-second` where it said `default`, with the same certificate data. Merged with the first one, both clusters appear:

```console
$ KUBECONFIG=~/.kube/config:~/.kube/rke2-second.yaml kubectl config get-contexts
CURRENT   NAME          CLUSTER       AUTHINFO      NAMESPACE
*         default       default       default
          rke2-second   rke2-second   rke2-second
```

The first cluster is still `default`. Renaming it the same way (run the block above against a copy of the first file, with its own name) leaves no entry called `default` at all, so a third RKE2 cluster can't collide with it. If you bootstrap RKE2 with Ansible, the rename can happen when the file is fetched instead: [abdelhousni/dar-rke2-k8s](https://github.com/abdelhousni/dar-rke2-k8s) names all three entries after the server in its `playbook.yml`.

## Merge into ~/.kube/config, or keep the files apart

Once no names collide, there are two ways to reach both clusters.

**Keep separate files and list them in `KUBECONFIG`.** `kubectl` merges them on every read and nothing new is written to disk:

```sh
export KUBECONFIG=~/.kube/config:~/.kube/rke2-second.yaml
kubectl config get-contexts
```

The variable has to be set in every shell, for example from `~/.bashrc`. A file added later needs adding to the list too.

**Write one merged file.** [`kubectl config view`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_config/kubectl_config_view/) prints the merged result of everything in `KUBECONFIG`, and three of its flags decide what that output contains:

- `--merge` is on by default and merges the whole list.
- `--flatten` turns file references into inline data, for example a `certificate-authority: /path/ca.crt` into `certificate-authority-data:`. The result no longer depends on other files.
- `--raw` prints the certificates and keys. Without it, `view` replaces them with `DATA+OMITTED` and `REDACTED`, and a file built from that output can't log in to anything.

The output can't be redirected straight onto `~/.kube/config` while `kubectl` is reading it. The shell truncates the file before `kubectl` starts, so `kubectl` reads an empty first file and only the second one survives. Write to a temporary file in the same directory, check it, then move it into place:

```sh
(
  set -e
  umask 077
  cp -p ~/.kube/config ~/.kube/config.bak."$(date +%Y%m%d-%H%M%S)"
  TMP=$(mktemp ~/.kube/config.merge.XXXXXX)
  trap 'rm -f "$TMP"' EXIT
  KUBECONFIG=~/.kube/config:~/.kube/rke2-second.yaml \
    kubectl config view --flatten --raw > "$TMP"
  kubectl --kubeconfig="$TMP" config get-contexts
  chmod 600 "$TMP"
  mv "$TMP" ~/.kube/config
)
```

The parentheses run it in a subshell, so `set -e` (stop at the first failing command) and `umask 077` (new files readable by you alone) don't stay in your shell. `mktemp` creates the file with mode `0600` and the `trap` deletes it if anything fails before the `mv`. `mv` within one directory replaces `~/.kube/config` in one step, so no command ever reads a half-written file.

`cp -p` keeps the original's permissions, so if `~/.kube/config` was readable by other users, so is the backup. Check with `ls -l ~/.kube`. Either file holds the client key for every cluster in it, and RKE2's key gives full admin access, so neither belongs in a Git repository or a CI log.

The merge keeps the first file's `current-context`, so `kubectl` still talks to the first cluster afterwards. Switch with `kubectl config use-context rke2-second`, or pass `--context rke2-second` to a single command.

## Where this series goes next

Autoscaling with the HorizontalPodAutoscaler, as announced at the end of [the probes entry](liveness-readiness-startup-probes.md).

These commands ran with kubectl v1.37.2 (the current stable release on 2026-11-08) on Linux against kubeconfig files written to match RKE2's format; no cluster was contacted, `write-kubeconfig-name` wasn't run on an RKE2 node, and the Windows `;` separator wasn't tried.
