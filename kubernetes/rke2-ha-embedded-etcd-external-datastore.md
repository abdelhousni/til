# Going HA with RKE2: three servers, one address, and the datastore choice

Ninth entry in the RKE2/Kubernetes series. Everything so far has run on the single node from [the lab install](rke2-single-node-lab-install.md), where "the control plane" and "that one machine" are the same thing. This is what changes when they stop being the same thing — and the two decisions that get made permanently in the process.

## Three servers, and specifically not two or four

The quorum formula — `(n/2)+1` — already came up in [the node-maintenance entry](rke2-node-maintenance-drain-reboot.md), as the reason you reboot control-plane nodes one at a time. It's also the reason HA starts at three rather than two, and the reason four is a worse three.

[RKE2's HA docs](https://docs.rke2.io/install/ha) put the arithmetic plainly: *"For any odd-sized cluster, adding one node will always increase the number of nodes necessary for quorum."* Run the numbers and the shape is obvious:

| Servers | Quorum needed | Failures tolerated |
|---|---|---|
| 1 | 1 | 0 |
| 2 | 2 | **0** |
| 3 | 2 | 1 |
| 4 | 3 | **1** |
| 5 | 3 | 2 |

Two servers tolerate nothing — either one dying takes write quorum with it, so you've doubled the hardware and doubled the chance of an outage. Four tolerates exactly what three does, while adding a machine that can fail. Every even number is strictly worse than the odd number below it, which is why the recommendation is three and the next step up is five.

## One address in front of all of them

A single-node cluster has one IP and nothing to decide. Three servers need a **fixed registration address** — one stable endpoint that stays valid as individual servers get replaced. RKE2's docs accept a TCP load balancer, round-robin DNS, or a virtual/elastic IP; the requirement isn't the mechanism, it's that the name outlives any particular node.

Two ports matter here, and they're different ports for different jobs:

- **`6443`** is the Kubernetes API — what `kubectl` talks to, covered back in [the off-node access entry](kubectl-off-node-rke2-tls-san.md).
- **`9345`** is RKE2's own registration endpoint. Per the docs: *"The `rke2 server` process listens on port `9345` for new nodes to register."* Nodes joining the cluster talk to 9345; nothing else does.

```mermaid
flowchart TB
    KUBECTL["kubectl"] -->|"6443, Kubernetes API"| LB
    JOIN["A node joining the cluster"] -->|"9345, registration"| LB
    LB["Fixed registration address: LB, round-robin DNS, or VIP"]
    LB --> S1["Server 1: etcd + control plane"]
    LB --> S2["Server 2: etcd + control plane"]
    LB --> S3["Server 3: etcd + control plane"]
    S1 <-->|"Raft: quorum is 2 of 3"| S2
    S2 <--> S3
    S1 <--> S3
```

This is also the exact case [the TLS SAN entry](kubectl-off-node-rke2-tls-san.md) flagged as needing `tls-san`. The node's own hostname and interface IPs are in the server certificate automatically; a load balancer name in front of three nodes is not on any of them, so it has to be declared. First server:

```yaml
# /etc/rancher/rke2/config.yaml -- first server
token: my-shared-secret
tls-san:
  - my-kubernetes-domain.com
```

Every server after it points at the same address and presents the same token:

```yaml
# /etc/rancher/rke2/config.yaml -- servers 2 and 3
server: https://my-kubernetes-domain.com:9345
token: my-shared-secret
tls-san:
  - my-kubernetes-domain.com
```

Worth noting for anyone arriving from k3s, where this trips people up: **the first RKE2 server needs no `cluster-init` flag.** Embedded etcd is already the default datastore — per [RKE2's own docs](https://docs.rke2.io/datastore/embedded), *"Embedded Etcd is the default datastore, and will be used if no other datastore configuration is present"* — so the first server starting normally *is* the cluster-init step. If you don't set `token:` yourself, one is generated at `/var/lib/rancher/rke2/server/node-token` for the other servers to use.

## Splitting etcd off from the control plane

Three identical servers each running etcd and the control plane is the common shape, but RKE2 will separate them. A dedicated etcd node disables the control-plane components:

```yaml
# etcd-only node
disable-apiserver: true
disable-controller-manager: true
disable-scheduler: true
```

and a dedicated control-plane node disables etcd and joins an existing one:

```yaml
# control-plane-only node
server: https://<etcd-only-node>:9345
disable-etcd: true
```

Two ordering constraints come with this, both from [the server roles docs](https://docs.rke2.io/install/server_roles), and both are the kind of thing you hit at 2am rather than read in advance. A dedicated control-plane node *"cannot be the first server in the cluster; there must be an existing node with the `etcd` role before joining."* And going the other way, an etcd-only first node *"will start etcd, and wait for additional `etcd` and/or `control-plane` nodes to join"* — the cluster is unusable until something with an API server shows up. Whichever role you stand up first, the cluster isn't a cluster until the other one exists.

## Embedded etcd or an external datastore

The other permanent-ish decision. RKE2 will run against an external database instead of embedded etcd, using [kine](https://github.com/k3s-io/kine) as the translation layer for SQL engines. Per [the external datastore docs](https://docs.rke2.io/datastore/external), the certified set is etcd (3.6.7), MySQL (8.4.8), MariaDB (11.4.10), and PostgreSQL (18.3), configured through `datastore-endpoint`:

```yaml
# /etc/rancher/rke2/config.yaml
datastore-endpoint: "postgres://username:password@hostname:port/database-name"
```

The honest framing from the docs is organizational rather than technical: external suits *"organizations with existing database infrastructure or those who have more experience operating an enterprise-grade SQL database."* If you already have a team that runs Postgres properly — backups, failover, monitoring — that's a real argument. If you don't, you've swapped a database you don't have to think about for one you do.

One caveat that's easy to trip over if you front your database with a pooler: *"RKE2 requires prepared statements support from the DB."* PgBouncer in transaction pooling mode doesn't provide that by default.

## What HA doesn't do for you

Quorum protects against a node dying. It does not protect against the cluster state being wrong — a bad `kubectl delete`, a corrupted upgrade, a mistake replicated faithfully to all three servers in milliseconds. That's what snapshots are for, and RKE2 takes them without being asked: `etcd-disable-snapshots` defaults to off, the schedule defaults to `0 */12 * * *` (every twelve hours), and five are retained, all verifiable in [the flag definitions](https://github.com/k3s-io/k3s/blob/master/pkg/cli/cmds/server.go) RKE2 inherits.

Which means a fresh HA cluster is already taking backups you haven't configured, retaining them somewhere you haven't chosen, on a node that is itself part of what you'd be recovering from.

## Where this series goes next

That last sentence is the whole next entry: where RKE2's etcd snapshots actually land, what restoring one does to the other servers, and why "we have snapshots" and "we can restore" are different claims.
