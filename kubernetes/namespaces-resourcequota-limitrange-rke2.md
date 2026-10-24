# A namespace on its own protects nothing: quotas, limit ranges, network policies and Pod Security do

Fourteenth entry in the RKE2/Kubernetes series. Every object created so far has gone into the `default` namespace, or into `kube-system` when RKE2 put it there. This entry splits a cluster into two team namespaces and checks, one command at a time, what that split actually stops. Out of the box it stops nothing. Each layer of protection is a separate object you add to the namespace.

## What a namespace is

A *namespace* is a named scope for objects. Per [Kubernetes' namespace docs](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/), it gives *"a mechanism for isolating groups of resources within a single cluster"*. In practice that means names only have to be unique inside one namespace: `team-a` and `team-b` can each have a Service called `api`.

Not every object lives in a namespace. Nodes, PersistentVolumes, StorageClasses, ClusterRoles and namespaces themselves are *cluster-scoped*. RKE2 v1.36.4 lists 61 such resource types:

```sh
kubectl api-resources --namespaced=false -o name | wc -l
```

```text
61
```

So whatever a namespace protects, it doesn't cover the [nodes and their taints](rke2-node-scheduling-labels-taints-tolerations.md) or the [StorageClass](rke2-no-default-storageclass.md) from earlier entries.

## Out of the box, namespaces don't isolate the network

The setup: two namespaces, an HTTP server behind a Service in `team-a`, and a client Pod in `team-b`. Both use `agnhost`, the Kubernetes project's own test image, which includes a small HTTP server (`netexec`) and a TCP check (`connect`) that prints nothing and exits 0 when the connection succeeds.

```sh
kubectl create namespace team-a
kubectl create namespace team-b
kubectl -n team-a create deployment api \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 -- /agnhost netexec --http-port=8080
kubectl -n team-a expose deployment api --port=80 --target-port=8080
kubectl -n team-b run client \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --command -- /agnhost pause
```

From `team-b`, the Service in `team-a` answers straight away:

```sh
kubectl -n team-b exec client -- /agnhost connect --timeout=3s api.team-a.svc.cluster.local:80
echo $?
kubectl -n team-b exec client -- sh -c 'wget -qO- -T3 http://api.team-a/hostname'
```

```text
0
api-86b79696fd-sps7x
```

The namespace is part of the DNS name, `<service>.<namespace>.svc.cluster.local`, and that's all it does here. In the network, every Pod can reach every other Pod, as [the CNI entry](rke2-cni-canal-and-alternatives.md) set up.

## NetworkPolicy closes the network, if the CNI enforces it

A *NetworkPolicy* is a namespaced object that selects Pods and lists which traffic may reach them (ingress) or leave them (egress). Once a Pod is selected by any policy for a direction, all traffic in that direction that no policy allows is dropped. The API server only stores the object. The CNI plugin does the enforcing, and [Kubernetes' NetworkPolicy docs](https://kubernetes.io/docs/concepts/services-networking/network-policies/) warn that *"creating a NetworkPolicy resource without a controller that implements it will have no effect."* RKE2's default CNI, Canal, enforces it with its Calico half.

This policy selects every Pod in `team-a` (`podSelector: {}`) and allows ingress only from Pods in the same namespace:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: same-namespace-only
  namespace: team-a
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector: {}
```

The same check from `team-b` now times out. A Pod inside `team-a` still gets through:

```sh
kubectl -n team-b exec client -- /agnhost connect --timeout=3s api.team-a.svc.cluster.local:80
kubectl -n team-a run neighbour \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --command -- /agnhost pause
kubectl -n team-a exec neighbour -- /agnhost connect --timeout=3s api.team-a.svc.cluster.local:80
echo $?
```

```text
TIMEOUT
command terminated with exit code 1
0
```

Inside `from`, a `podSelector` without a `namespaceSelector` means "Pods in the policy's own namespace". That's what makes this policy namespace-wide.

## Pod Security Admission: RKE2's default lets anything in

*Admission* is the step where the API server checks or changes an object after authenticating the request but before storing it. *Pod Security Admission* is the built-in admission check that compares each new Pod against one of three [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/): `privileged` (no restrictions), `baseline` (blocks known privilege escalations), and `restricted` (current hardening practice). A namespace chooses its level with a label.

RKE2 writes the cluster-wide default to `/etc/rancher/rke2/rke2-pss.yaml`. Without the CIS profile it is the most permissive level:

```yaml
    defaults:
      enforce: "privileged"
```

Every namespace without a label therefore accepts privileged Pods, whose containers get full access to the node's devices. Labelling `team-a` turns that off for new Pods:

```sh
kubectl label namespace team-a pod-security.kubernetes.io/enforce=restricted
kubectl -n team-a run root-shell \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --privileged --command -- /agnhost pause
```

```text
namespace/team-a labeled
Warning: existing pods in namespace "team-a" violate the new PodSecurity enforce level "restricted:latest"
Warning: api-86b79696fd-sps7x (and 1 other pod): allowPrivilegeEscalation != false, unrestricted capabilities, runAsNonRoot != true, seccompProfile
Error from server (Forbidden): pods "root-shell" is forbidden: violates PodSecurity "restricted:latest": privileged (container "root-shell" must not set securityContext.privileged=true), allowPrivilegeEscalation != false (container "root-shell" must set securityContext.allowPrivilegeEscalation=false), [...]
```

The warnings matter. The two Pods already running in `team-a` break the new rule and keep running. Admission only judges objects as they are created, a pattern that comes back with quotas below.

## ResourceQuota caps what a namespace can consume

So far `team-b` can still start as many Pods, using as much CPU and memory, as the nodes hold. Two terms first. A container's *request* is the CPU and memory the scheduler reserves for it on a node. Its *limit* is the most it may use: a container that goes over its memory limit is killed. A *ResourceQuota* is a namespaced object that caps the total of requests, limits, or object counts across the whole namespace:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute
  namespace: team-b
spec:
  hard:
    pods: "3"
    requests.cpu: 500m
    requests.memory: 256Mi
    limits.memory: 512Mi
```

`500m` is 500 millicores, half of one CPU core.

### A quota on CPU or memory makes requests mandatory

Right after it's applied, the quota already counts the `client` Pod, but only as a Pod:

```text
NAME      REQUEST                                                     LIMIT                    AGE
compute   pods: 1/3, requests.cpu: 0/500m, requests.memory: 0/256Mi   limits.memory: 0/512Mi   3s
```

`client` was created without requests or limits, before the quota existed, so it uses CPU and memory without counting against the caps. A new Pod written the same way is refused:

```sh
kubectl -n team-b run worker \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --command -- /agnhost pause
```

```text
Error from server (Forbidden): pods "worker" is forbidden: failed quota: compute: must specify limits.memory for: worker; requests.cpu for: worker; requests.memory for: worker
```

The [ResourceQuota docs](https://kubernetes.io/docs/concepts/policy/resource-quotas/) state the rule: once a quota tracks a compute resource, every new Pod has to declare it, or the quota system rejects it. Otherwise the quota couldn't add the Pod to its total.

### LimitRange fills in the values a Pod leaves out

A *LimitRange* is the namespaced object that sets per-container defaults, minimums and maximums. With defaults in place, the same `kubectl run` passes:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
  namespace: team-b
spec:
  limits:
    - type: Container
      defaultRequest:
        cpu: 100m
        memory: 64Mi
      default:
        memory: 128Mi
```

```sh
kubectl -n team-b run worker \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --command -- /agnhost pause
kubectl -n team-b get pod worker -o jsonpath='{.spec.containers[0].resources}{"\n"}{.metadata.annotations.kubernetes\.io/limit-ranger}{"\n"}'
```

```text
pod/worker created
{"limits":{"memory":"128Mi"},"requests":{"cpu":"100m","memory":"64Mi"}}
LimitRanger plugin set: cpu, memory request for container worker; memory limit for container worker
```

The values are written into the stored Pod, and an annotation records which ones the LimitRange supplied. LimitRange runs during admission too, before the quota check, which is why the quota then sees a Pod with requests. Like the quota, it doesn't go back and change `client`.

### A Deployment over quota fails quietly

A Deployment asking for three replicas, in a namespace where two of the three Pod slots are taken:

```sh
kubectl -n team-b create deployment web \
  --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --replicas=3 -- /agnhost pause
kubectl -n team-b get deployment web
kubectl -n team-b get resourcequota compute
```

```text
deployment.apps/web created
NAME   READY   UP-TO-DATE   AVAILABLE   AGE
web    1/3     1            1           15s
NAME      REQUEST                                                            LIMIT                        AGE
compute   pods: 3/3, requests.cpu: 200m/500m, requests.memory: 128Mi/256Mi   limits.memory: 256Mi/512Mi   19s
```

`kubectl create deployment` succeeded because the quota judges Pods, not Deployments. The ReplicaSet controller is the one whose Pod creations get refused, and it keeps retrying. The reason only shows up in the Deployment's `ReplicaFailure` condition and in the ReplicaSet's events:

```sh
kubectl -n team-b get deployment web -o jsonpath='{.status.conditions[?(@.type=="ReplicaFailure")].message}{"\n"}'
```

```text
pods "web-6c9d799bf7-x9wrj" is forbidden: exceeded quota: compute, requested: pods=1, used: pods=3, limited: pods=3
```

`1/3` with no `Pending` Pods is the sign to look there. A Pod that can't be scheduled is still created and shows as `Pending`. A Pod refused by a quota never exists.

### Lowering a quota doesn't evict anything

Cutting the cap below current usage:

```sh
kubectl -n team-b patch resourcequota compute --type=merge -p '{"spec":{"hard":{"pods":"1"}}}'
kubectl -n team-b get resourcequota compute -o jsonpath='pods {.status.used.pods}/{.status.hard.pods}{"\n"}'
kubectl -n team-b get pods
```

```text
pods 3/1
NAME                   READY   STATUS    RESTARTS   AGE
client                 1/1     Running   0          80s
web-6c9d799bf7-px7xf   1/1     Running   0          19s
worker                 1/1     Running   0          19s
```

Three Pods against a cap of one, all still running. The quota docs say so directly: *"Neither contention nor changes to quota will affect already created resources."* The cap applies again only as Pods go away. Until usage drops below it, no new Pod gets in, including the replacement for a Pod that crashes and is deleted.

## Every layer is an admission check

Every control in this entry acts when an object is created. NetworkPolicy is the exception: Canal applies it to running Pods. The others leave existing objects alone:

| Layer | Object | What it stops | Applies to existing Pods |
|---|---|---|---|
| Names | Namespace | Name collisions | — |
| Network | NetworkPolicy | Traffic the policy doesn't allow | Yes, enforced by the CNI |
| Pod privileges | `pod-security.kubernetes.io/*` label | Pods above the namespace's level | No, only a warning |
| Consumption | ResourceQuota | Pods and objects beyond the caps | No, `used` can exceed `hard` |
| Defaults | LimitRange | Pods without requests or limits | No |

All five are namespaced objects, and nothing so far stops a user of `team-b` from deleting the quota or the policy. Deciding who may change them is the job of RBAC (role-based access control), the API server's check of who may do what to which objects.

## Where this series goes next

Liveness probes: how the kubelet decides a container that is running is no longer working, and restarts it.

These commands ran on a single-node RKE2 v1.36.4 cluster inside a Docker container in a cloud sandbox, not on the Proxmox homelab the earlier entries used.
