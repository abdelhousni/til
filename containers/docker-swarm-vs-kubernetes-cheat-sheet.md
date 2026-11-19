# Docker Swarm and Kubernetes side by side: the same concepts, two vocabularies

A cheat sheet for someone who knows one of the two and keeps asking "what is the equivalent of X?". One row per concept, Docker Swarm in one column and Kubernetes in the other, grouped by theme: cluster and nodes, workloads, declaring things in files, networking, configuration and secrets, storage, scheduling, rolling updates, and what only one side has.

Both tools do the same job. You describe what should run (an image, how many copies, which ports, what configuration), and the tool keeps the cluster matching that description: it places containers on machines, restarts the ones that die, and replaces them when you change the description. Kubernetes calls that loop *reconciliation*; [the first entry of the RKE2 series](../kubernetes/what-is-kubernetes-and-how-it-works.md) explains it. Swarm does the same with fewer object types, less machinery and a much shorter vocabulary.

Versions checked: Docker Engine 29.10.0 (released 2026-11-16, API 1.57) for the Swarm column, run in this session; the Kubernetes documentation for the current release, 1.37, for the Kubernetes column, plus what the earlier entries of this series ran on RKE2 with Kubernetes 1.36.

One thing to know before investing in Swarm: Docker's [retired products page](https://docs.docker.com/retired/) says about SwarmKit, the library behind it, that "while Swarm mode remains functional, development has slowed in favor of Kubernetes-based solutions". It still ships in every Docker Engine release and the 29.x release notes still carry Swarm fixes (the [29.10.0 notes](https://docs.docker.com/engine/release-notes/29/) add experimental support for joining a swarm with the nftables firewall backend), but no new features are being added.

## Terms the tables use

- **Docker Engine**: the daemon (`dockerd`) that builds images and runs containers on one host, and the `docker` command that talks to it. [The hello-world entry](../podman/docker-and-podman-hello-world.md) shows the client, daemon, registry and container working together.
- **Swarm mode**: the cluster mode built into Docker Engine. `docker swarm init` turns a single engine into a one-node cluster; `docker swarm join` adds more engines. No extra software. (Docker's documentation says "Swarm mode" because a separate Docker Swarm product existed before Docker Engine 1.12 built the cluster in.)
- **Compose file**: a `compose.yaml` that describes a set of containers, their images, ports, volumes and networks. [The podman compose entry](../podman/podman-compose-docker-compose-plugin-needs-the-socket.md) shows one. Swarm reads the same file format, plus a `deploy:` section that only matters to Swarm.
- **Manifest**: Kubernetes' word for a YAML file describing one object, such as the Deployment and Service in [the object model entry](../kubernetes/pods-deployments-services-object-model.md).
- **Raft**: a consensus algorithm. A group of machines votes on every change, and a change is accepted once a majority has written it, so the group keeps one consistent copy of the state as long as a majority is up. Swarm managers run Raft themselves; Kubernetes stores its state in etcd, a separate database that also runs Raft.
- **Overlay network**: a virtual network spanning several hosts. Packets between containers on different hosts are wrapped inside UDP packets (VXLAN, port 4789) and unwrapped on the other side, so containers see one flat network whatever the physical one looks like.
- **CNI (Container Network Interface)**: Kubernetes doesn't ship a network of its own. A CNI plugin, chosen when the cluster is installed, gives every Pod an IP address and routes between nodes; [the RKE2 CNI entry](../kubernetes/rke2-cni-canal-and-alternatives.md) compares the options.
- **Pod**: the smallest thing Kubernetes schedules, one or more containers that share an IP address and can talk over `localhost`.
- **Task**: the smallest thing Swarm schedules, exactly one container. A *service* is the description Swarm turns into tasks.

## Cluster and nodes

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| The cluster | a *swarm*: a set of Docker Engines, each one a *node* | a *cluster*: control plane nodes plus worker nodes |
| Who decides | *manager* nodes. They hold the state in a Raft log, elect one leader, schedule tasks and serve the API. Use an odd number, 3 or 5, at most 7: an odd N survives losing (N-1)/2. More managers don't add capacity | the *control plane*: `kube-apiserver` (the API), etcd (the state), `kube-scheduler` (placement) and `kube-controller-manager` (the reconcile loops). 3 etcd members survive losing 1; [the RKE2 HA entry](../kubernetes/rke2-ha-embedded-etcd-external-datastore.md) sets this up |
| Who runs containers | *worker* nodes. Managers are workers too unless drained | *worker* nodes, each running `kubelet` (starts Pods), `kube-proxy` (Service routing) and a container runtime. Control plane nodes may run workloads too; [RKE2 leaves them schedulable](../kubernetes/rke2-node-scheduling-labels-taints-tolerations.md) |
| Where state lives | the managers' Raft log, replicated and encrypted at rest by default | etcd, replicated with Raft, unencrypted unless encryption at rest is configured |
| Create the cluster | `docker swarm init` on the first engine | depends on the distribution: `kubeadm init`, an RKE2 `config.yaml` plus `systemctl start rke2-server`, k3s, or a managed service |
| Add a node | `docker swarm join` `--token <token> <manager>:2377`; `docker swarm join-token worker` prints the command | depends on the distribution: `kubeadm join`, or an RKE2 agent pointed at the server with its token |
| The command-line tool | `docker`, pointed at a manager; `docker node`, `docker service`, `docker stack` only work there | `kubectl`, pointed at the API server from anywhere with a kubeconfig; [the off-node kubectl entry](../kubernetes/kubectl-off-node-rke2-tls-san.md) |
| List nodes | `docker node ls` | `kubectl get nodes` |
| Take a node out for maintenance | `docker node update` `--availability drain <node>`: running tasks move elsewhere, no new ones arrive. `--availability active` puts it back; `pause` keeps running tasks but takes no new ones | `kubectl cordon <node>` (no new Pods), `kubectl drain <node>` (evict the running ones too), `kubectl uncordon <node>`; [the RKE2 maintenance entry](../kubernetes/rke2-node-maintenance-drain-reboot.md) |
| Change a node's role | `docker node promote <node>`, `docker node demote <node>` | no command: a node is installed as a control plane node or as a worker |
| Label a node | `docker node update` `--label-add tier=web <node>` | `kubectl label nodes <node>` `tier=web` (and `tier-` to remove) |

## Workloads

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| Smallest scheduled unit | a *task*: one container, placed on one node, replaced (never moved) when it fails | a *Pod*: one or more containers with one IP, placed on one node, replaced when it fails |
| A long-running app with N copies | a *service* in `replicated` mode: `docker service create` `--replicas 3` `--name web nginx:alpine` | a *Deployment*, which creates a ReplicaSet, which keeps N Pods running: `kubectl create deployment web` `--image=nginx:alpine` `--replicas=3` |
| One copy on every node | a service in `global` mode: `--mode global` | a *DaemonSet* |
| Run once, to completion | a service in `replicated-job` or `global-job` mode: `--mode replicated-job` `--replicas 2`, with `--max-concurrent` for parallelism. `docker service ls` shows `0/2 (2/2 completed)` when done | a *Job*, with `completions` and `parallelism` |
| Run on a schedule | nothing built in; run cron somewhere | a *CronJob* |
| Stable names and a volume per copy (a database cluster) | nothing built in; approximated with one service per member, each pinned to a node with a constraint and a local volume | a *StatefulSet*: Pods named `db-0`, `db-1`, each with its own volume claim |
| Change the copy count | `docker service scale web=5`, or `docker service update` `--replicas 5 web` | `kubectl scale deployment/web` `--replicas=5` |
| Restart policy | `--restart-condition none`, `on-failure` or `any` (the default), set on the service | `restartPolicy: Always`, `OnFailure` or `Never` on the Pod, for the containers inside it. The controller above the Pod recreates the Pod itself |
| Health check | the image's `HEALTHCHECK`, or `--health-cmd`, `--health-interval`, `--health-retries`, `--health-start-period`. An unhealthy task is replaced | *liveness*, *readiness* and *startup* probes; [the probes entry](../kubernetes/liveness-readiness-startup-probes.md) explains which one restarts the container and which one only stops traffic |
| Logs | `docker service logs web` (all tasks, prefixed by task and node) | `kubectl logs deployment/web` `--all-pods` (prefixed by Pod), `kubectl logs -f <pod>` |
| A shell inside | `docker exec -it <container>` on the node running the task; find it with `docker service ps web` | `kubectl exec -it <pod> -- sh`, from anywhere `kubectl` works |
| See what is running | `docker service ls`, `docker service ps web`, `docker service inspect` `--pretty web` | `kubectl get deployments,pods`, `kubectl describe deployment web` |
| Events and failures | `docker service ps web --no-trunc` shows each task's state and error | `kubectl get events`, sorted with `--sort-by` on `.metadata.creationTimestamp`; `kubectl describe pod` |
| Resource usage | `docker stats` on each node | `kubectl top pod`, `kubectl top node` (needs metrics-server) |

The task-versus-Pod difference matters once two containers belong together: a web server and the sidecar that ships its logs, say. Kubernetes puts them in one Pod and they share `localhost`. Swarm has no such grouping: they become two services on the same overlay network, talking by service name.

## Declaring it in files

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| The file | a Compose file. Everything under `deploy:` (`mode`, `replicas`, `placement`, `resources`, `update_config`, `rollback_config`, `restart_policy`, `endpoint_mode`) is read by Swarm; `docker compose` on one host implements only some of it | one or more manifests, one object each, in plain YAML |
| Apply it | `docker stack deploy` `-c compose.yaml demo`; run on a manager | `kubectl apply -f dir/` |
| A group of related things | a *stack*: `docker stack deploy` names every service, network and volume `<stack>_<name>` | a *namespace* for isolation, labels for grouping, and tools above `kubectl` for packaging: Helm charts, or [Kustomize overlays](../kubernetes/kustomize-overlays-trimming-an-upstream-release.md) |
| Apply again after a change | the same `docker stack deploy`; `--prune` removes services no longer in the file | the same `kubectl apply`; `--prune` with a label selector removes objects no longer in the files |
| Remove the group | `docker stack rm demo` | `kubectl delete -f dir/`, or delete the namespace |
| Keys that only make sense on one host | `docker stack deploy` prints a warning naming `build` as unsupported and goes on; `container_name` and `depends_on` pass without a message and have no effect (containers are named `<stack>_<service>.<n>.<task id>`, and services start in no particular order) | nothing comparable: every field in a manifest is validated by the API server, and there is no start order either; a container that needs another one retries until it is there |

## Networking

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| Container-to-container across nodes | an *overlay network*, created with `docker network create` `--driver overlay backend` and attached to services with `--network`. Nodes need 7946 TCP and UDP (discovery) and 4789 UDP (VXLAN) open between them | the CNI plugin: every Pod gets a cluster-wide IP, routed between nodes by the plugin |
| Finding another app by name | built-in DNS on each overlay network: `web` resolves to the service's virtual IP (`endpoint_mode: vip`, the default) or to all task IPs (`dnsrr`) | a *Service* of type `ClusterIP`: `web` in the same namespace, `web.<namespace>` from another one, resolves to a stable virtual IP in front of the Pods selected by labels |
| The address that doesn't change | the service's virtual IP, held for the life of the service | the Service's cluster IP; Pod IPs change at every replacement |
| Opening a port to the outside | `--publish` `published=8080,target=80`: the *routing mesh* listens on 8080 on every node and forwards to a running task, even on a node without one | a Service of type `NodePort`: the same port (30000-32767 by default) on every node, forwarded by `kube-proxy` to a Pod; or type `LoadBalancer`, which also asks the cloud or a controller for an external address |
| A port only where the container is | `mode=host` in the long `--publish` syntax (example under the table), which bypasses the routing mesh, usually with `--mode global` | `hostPort` on the container, or `hostNetwork: true` on the Pod |
| No virtual IP, just the members | `endpoint_mode: dnsrr` | a headless Service, `clusterIP: None`: DNS returns the Pod IPs |
| HTTP routing by host name and path, TLS | nothing built in: run a reverse proxy (Traefik, nginx, Caddy) as a global service with the published ports, and give it the Docker socket or labels to read | an *Ingress* object plus an Ingress controller (Traefik or nginx), or the newer *Gateway API*. The Ingress API is frozen: kept, but no longer developed. [The RKE2 ingress entry](../kubernetes/rke2-ingress-traefik-nginx-retirement.md) covers both |
| Keeping apps apart on the network | separate overlay networks: two services can talk only if they share one | *NetworkPolicy* objects, enforced by the CNI plugin if it supports them; [the namespaces entry](../kubernetes/namespaces-resourcequota-limitrange-rke2.md) shows a default-deny policy |

The long `--publish` syntax in full, for a DNS cache that must answer on port 53 of every node, from the routing mesh documentation:

```sh
docker service create --name dns-cache --mode global \
  --publish published=53,target=53,protocol=udp,mode=host \
  dns-cache
```

## Configuration and secrets

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| A secret | `docker secret create db_pass -`; attached with `--secret db_pass`, appears as the file `/run/secrets/db_pass`, held in memory in the container, 500 KB maximum. The value is never readable back: `docker secret inspect` shows no data | a *Secret*: `kubectl create secret generic` `db-pass` `--from-literal=password=...`; mounted as a file (on tmpfs) or injected as an environment variable, 1 MiB maximum. The value is readable back by anyone allowed to `kubectl get secret -o yaml`, base64-encoded, not encrypted |
| At rest | in the managers' Raft log, encrypted | in etcd, in clear unless encryption at rest is turned on |
| A non-secret file | `docker config create nginx_conf` `nginx.conf`; attached with `--config`, appears as `/nginx_conf` unless a `target` path is given | a *ConfigMap*: `kubectl create configmap` `nginx-conf` `--from-file=nginx.conf`; mounted as a file or injected as an environment variable |
| Changing one | immutable: create `db_pass_v2`, then `docker service update` `--secret-rm db_pass` `--secret-add db_pass_v2 web`, which rolls the tasks | editable in place; a mounted file is refreshed in the running Pod, an environment variable is not, and nothing restarts on its own |
| Environment variables | `--env KEY=value`, or `environment:` in the Compose file | `env:` on the container, `envFrom:` to load a whole ConfigMap or Secret |
| In the Compose file or manifest | `secrets:` and `configs:` at the top level, `external: true` to use one created beforehand | the Secret and ConfigMap are objects of their own, referenced by name from the Pod template |

## Storage

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| A named volume | `--mount type=volume` with `source=` and `target=`, or `volumes:` in the Compose file. With the default `local` driver it exists on one node only, so a task rescheduled elsewhere starts empty; shared storage needs a volume plugin or a network filesystem | a *PersistentVolumeClaim* (the request) bound to a *PersistentVolume* (the storage), provisioned by a *StorageClass*. The claim follows the Pod to any node the storage can reach. [RKE2 ships no default StorageClass](../kubernetes/rke2-no-default-storageclass.md) |
| A host directory | `--mount type=bind` with `source=` and `target=`; the host path must exist on every node that may run the task | `hostPath` |
| Scratch space for the life of the container | `--mount type=tmpfs,target=/tmp` | `emptyDir` (lives as long as the Pod, shared by its containers) |

## Scheduling and resources

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| Must run on nodes like this | `--constraint` `node.labels.tier==web`, also `node.role==manager`, `node.hostname!=node-2`, `node.platform.arch==x86_64`, `engine.labels.<key>`. No matching node: the task stays `pending` | `nodeSelector` (`tier: web`), or a *required* `nodeAffinity` rule for expressions. No matching node: the Pod stays `Pending` |
| Prefer nodes like this, spread evenly | `--placement-pref` `spread=node.labels.zone`: best effort, ignored for global services | a *preferred* `nodeAffinity` rule; `topologySpreadConstraints` to spread across zones or nodes |
| Keep copies apart, or together | nothing direct; a spread preference over `node.hostname` approximates it | `podAntiAffinity` and `podAffinity`, matched on other Pods' labels |
| Keep workloads off a node unless allowed | drain the node, or a constraint on every service | *taints* on the node, *tolerations* on the Pod; [the RKE2 scheduling entry](../kubernetes/rke2-node-scheduling-labels-taints-tolerations.md) |
| Pin to one node | `--constraint` `node.hostname==node-1` | `nodeName` in the Pod spec, bypassing the scheduler |
| CPU and memory | `--reserve-cpu`, `--reserve-memory` (used for placement), `--limit-cpu`, `--limit-memory` (enforced). In the Compose file: `deploy.resources.reservations` and `limits` | `resources.requests` (used for placement) and `resources.limits` (enforced) on each container |
| Caps per team or project | nothing built in | *ResourceQuota* and *LimitRange* per namespace; [the namespaces entry](../kubernetes/namespaces-resourcequota-limitrange-rke2.md) |

The two `nodeAffinity` rules are spelled `requiredDuringSchedulingIgnoredDuringExecution` and `preferredDuringSchedulingIgnoredDuringExecution`: both apply when the Pod is placed, and neither moves a Pod that is already running when the labels change. A Swarm constraint behaves the same way.

## Rolling updates

| Concept | Docker Swarm | Kubernetes |
|---|---|---|
| Change the image | `docker service update` `--image nginx:1.29-alpine web`, or edit the Compose file and `docker stack deploy` again | `kubectl set image deployment/web` `nginx=nginx:1.29-alpine`, or edit the manifest and `kubectl apply` again |
| How many at a time, how fast | `--update-parallelism 1` `--update-delay 5s`, `--update-order start-first` to start the new task before stopping the old (default `stop-first`) | `strategy.rollingUpdate.maxSurge` (how many extra) and `maxUnavailable` (how many missing); both default to 25% |
| When a new copy fails | `--update-failure-action pause` (default), `continue` or `rollback`; `--update-monitor` says how long a task must stay up to count as a success | the rollout stops on its own, because new Pods that fail their readiness probe never count as available; `progressDeadlineSeconds` marks the Deployment as failed after a wait |
| Watch it | `docker service ps web` | `kubectl rollout status` `deployment/web` |
| Go back | `docker service rollback web`: one step, to the previous spec | `kubectl rollout undo` `deployment/web`, or `--to-revision=N` after `kubectl rollout history` |
| Automatic rollback | `--update-failure-action rollback`, paced by `--rollback-parallelism`, `--rollback-delay` | nothing built in; the stalled rollout waits for someone to run `rollout undo` |

## What only one side has

| | Docker Swarm | Kubernetes |
|---|---|---|
| Only here | the whole thing is inside Docker Engine: no install, one `docker swarm init`, and `docker ps` still works on every node. Nodes talk over mutual TLS set up and rotated automatically. Secrets are encrypted at rest without any configuration. One file format, the Compose file, for both the single-host and the cluster case | *namespaces* and *RBAC* (role-based access control: who may do what to which objects) for several teams on one cluster. The *HorizontalPodAutoscaler*, which adds and removes replicas from metrics. *Custom resources* and *operators*, so that software such as Prometheus or a database can be managed as objects of its own; [the kube-prometheus entry](../kubernetes/kube-prometheus-on-rke2-step-by-step.md) installs one. *StatefulSet*, *Ingress* and *Gateway API*, *NetworkPolicy*, *PodDisruptionBudget* (how many copies a drain may take down at once). Many distributions and managed offerings to choose from |
| Not here | everything in the right-hand cell, and multi-container Pods. Anything beyond "run these containers with these ports" is a service you run yourself | nothing from the left-hand cell, apart from the install effort: there is always a distribution to pick, a CNI to pick, a StorageClass to set up and a kubeconfig to distribute |

## Sources

Docker documentation, read on 2026-11-19: [Swarm mode key concepts](https://docs.docker.com/engine/swarm/key-concepts/), [how nodes work](https://docs.docker.com/engine/swarm/how-swarm-mode-works/nodes/), [services](https://docs.docker.com/engine/swarm/services/), [the routing mesh](https://docs.docker.com/engine/swarm/ingress/), [secrets](https://docs.docker.com/engine/swarm/secrets/), [the PKI and certificate rotation](https://docs.docker.com/engine/swarm/how-swarm-mode-works/pki/), the [`docker service create`](https://docs.docker.com/reference/cli/docker/service/create/), [`docker service update`](https://docs.docker.com/reference/cli/docker/service/update/), [`docker stack deploy`](https://docs.docker.com/reference/cli/docker/stack/deploy/) and [`docker node update`](https://docs.docker.com/reference/cli/docker/node/update/) references, the [Compose `deploy` specification](https://docs.docker.com/reference/compose-file/deploy/), the [retired products page](https://docs.docker.com/retired/) and the [Engine 29 release notes](https://docs.docker.com/engine/release-notes/29/).

Kubernetes documentation, read the same day: [releases](https://kubernetes.io/releases/), [Service](https://kubernetes.io/docs/concepts/services-networking/service/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/), [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/), [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/), [assigning Pods to nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/), the [kubectl quick reference](https://kubernetes.io/docs/reference/kubectl/quick-reference/) and the [`kubectl logs`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), [`kubectl create secret generic`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_generic/) and [`kubectl label`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_label/) references.

The Swarm commands ran on a single-node swarm, Docker Engine 29.10.0, in a Linux cloud container: `swarm init`, a replicated and a global service, a `replicated-job`, a stack from a Compose file with the `deploy:` keys above, a secret and a config checked from inside a container, a node label with a constraint, a drain, a scale, an image update and a rollback. The Kubernetes commands weren't run in this session: they come from the documentation linked above and from the earlier entries of this series, which ran them on RKE2.
