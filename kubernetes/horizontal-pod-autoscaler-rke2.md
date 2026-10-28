# The HorizontalPodAutoscaler scales on an average, and it can't see a quota

Sixteenth entry in the RKE2/Kubernetes series. So far every Deployment has run the number of replicas someone typed. The *HorizontalPodAutoscaler* (HPA) changes that number on its own, from a measurement. This entry runs one on RKE2 v1.36.4 under real CPU load, and watches how fast it scales up, how slowly it scales down, and two cases where its numbers say one thing and the cluster another.

## Two autoscalers, two different things to add

Kubernetes has two common autoscalers, and they add different things:

- The **HorizontalPodAutoscaler** is built into Kubernetes. It changes `replicas` on a Deployment (or anything else with a scale subresource) to keep a metric near a target. It adds Pods, on the nodes the cluster already has.
- The **Cluster Autoscaler** is a separate component that adds and removes *nodes*. It watches for Pods stuck in `Pending` because no node has room, and asks an infrastructure provider (a cloud, or a platform that can create VMs) for another machine.

The two work together: the HPA asks for more Pods, and when they don't fit, the Cluster Autoscaler adds a node for them. The Cluster Autoscaler needs that provider integration, and a lab where the nodes were created by hand has none, so this entry covers the HPA only.

## Where the numbers come from

The HPA doesn't measure anything itself. Every 15 seconds the HPA controller, which runs inside `kube-controller-manager`, reads the *resource metrics API*. That API is served by *metrics-server*, which collects CPU and memory usage from each node's kubelet. RKE2 installs it by default as `rke2-metrics-server`, which is also what makes `kubectl top` work:

```sh
kubectl top nodes
```

```text
NAME   CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)
vm     656m         16%      3975Mi          24%
```

The test workload is `resource-consumer`, another image from the Kubernetes project's test suite. It's an HTTP server that burns a requested amount of CPU on demand.

## Without a CPU request, there's nothing to compute

```sh
kubectl create namespace hpa
kubectl -n hpa create deployment burner \
  --image=registry.k8s.io/e2e-test-images/resource-consumer:1.13
kubectl -n hpa expose deployment burner --port=80 --target-port=8080
kubectl -n hpa autoscale deployment burner --cpu=50% --min=1 --max=6
```

`kubectl autoscale` creates the HPA in one line. Written out, it is this `autoscaling/v2` object:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: burner
  namespace: hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: burner
  minReplicas: 1
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
```

A minute later the HPA still has no number:

```text
NAME     REFERENCE           TARGETS              MINPODS   MAXPODS   REPLICAS
burner   Deployment/burner   cpu: <unknown>/50%   1         6         1
```

The HPA's events give the reason:

```text
FailedGetResourceMetric   failed to get cpu utilization: missing request for cpu in container resource-consumer of Pod burner-655b5b7cb4-8b8kk
```

`50%` means 50% *of the CPU request*. Without a request there's nothing to take a percentage of. [The namespaces entry](namespaces-resourcequota-limitrange-rke2.md) showed a quota making requests mandatory. Here they're mandatory for a different reason. Setting one:

```sh
kubectl -n hpa set resources deployment burner --requests=cpu=100m --limits=cpu=500m
```

```text
NAME     REFERENCE           TARGETS       MINPODS   MAXPODS   REPLICAS
burner   Deployment/burner   cpu: 0%/50%   1         6         1
```

## Scaling up: one formula, applied every 15 seconds

A Pod asks the Service to burn 300 millicores (three times the request) for 10 minutes:

```sh
kubectl -n hpa run load --image=registry.k8s.io/e2e-test-images/agnhost:2.53 --restart=Never \
  --command -- sh -c 'wget -qO- --post-data="" "http://burner/ConsumeCPU?millicores=300&durationSec=600"'
```

`kubectl get hpa` every 15 seconds, and the HPA's own events:

```text
21:21:28 cpu: 0%/50%    1
21:21:43 cpu: 199%/50%  1
21:21:59 cpu: 301%/50%  4
21:22:14 cpu: 75%/50%   6
21:22:29 cpu: 50%/50%   6

21:21:41   New size: 4; reason: cpu resource utilization (percentage of request) above target
21:21:56   New size: 6; reason: cpu resource utilization (percentage of request) above target
```

From 1 to 6 replicas in 15 seconds. [Kubernetes' HPA docs](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) give the algorithm as one formula:

```text
desiredReplicas = ceil[currentReplicas * ( currentMetricValue / desiredMetricValue )]
```

Both steps match it. At 199% with one replica: ceil(1 × 199 / 50) = 4. At 75% with four: ceil(4 × 75 / 50) = 6, which is also `maxReplicas`. The HPA does nothing while the ratio stays within a tolerance, 10% by default, so that small swings don't resize the Deployment back and forth.

## The average hides a hot Pod

At 6 replicas the HPA reads exactly its target, `50%/50%`, and stops. `kubectl top` per Pod shows what that average is made of:

```sh
kubectl -n hpa top pods -l app=burner
```

```text
NAME                      CPU(cores)   MEMORY(bytes)
burner-6cb89cc99b-7grnl   1m           1Mi
burner-6cb89cc99b-87b5h   0m           1Mi
burner-6cb89cc99b-ng26q   0m           0Mi
burner-6cb89cc99b-ppnvj   1m           1Mi
burner-6cb89cc99b-r8vn5   301m         7Mi
burner-6cb89cc99b-wcqrd   0m           0Mi
```

One Pod is at 301% of its request, five are idle. `resource-consumer` burns the CPU inside whichever Pod received the request, for its whole duration. One request started 10 minutes of work on one Pod, and the five new replicas couldn't take any of it. 301m spread over six requests of 100m averages 50%. To the HPA that's on target. `Utilization` is an average over the Pods, so it only reflects load the Service can spread. Work that sticks to one Pod (a long-running job, a pinned session, a queue consumer holding a lock) scales the replica count without lowering anyone's load.

## Scaling down waits five minutes

The burn ended at about 21:31:20. The HPA's view, then its decisions:

```text
21:31:53 cpu: 11%/50%  6
21:32:13 cpu: 0%/50%   6
21:36:57 cpu: 0%/50%   1

21:36:27   New size: 2; reason: All metrics below target
21:36:42   New size: 1; reason: All metrics below target
```

Up took 15 seconds, down took five minutes. That's the HPA's default *stabilization window* for scale-down: 300 seconds. On each pass it computes a recommendation and keeps the highest one from the last five minutes. That's why the first step went to 2 rather than 1. Five minutes before 21:36:27, the CPU was still about 11%, and ceil(6 × 11 / 50) = 2. Scale-up has no window by default, so a spike gets replicas within one or two passes, and a dip doesn't take them away. Both directions can be tuned in the HPA's `behavior` field.

The same window applies when someone scales by hand:

```sh
kubectl -n hpa scale deployment burner --replicas=4    # at 21:37:16
```

```text
21:42:27   New size: 1; reason: All metrics below target
```

The HPA owns `replicas`. A manual `kubectl scale`, or a `replicas:` field applied from Git, is overwritten on its next decision, here five minutes later because it was a scale-down.

## A quota caps the HPA without telling it

The same setup in a namespace with a ResourceQuota of three Pods (the [namespaces entry](namespaces-resourcequota-limitrange-rke2.md) covers quotas):

```sh
kubectl create namespace hpa-quota
kubectl -n hpa-quota create quota pods --hard=pods=3
# same burner Deployment, request, Service, HPA and load as above
```

```text
NAME     REFERENCE           TARGETS         MINPODS   MAXPODS   REPLICAS
burner   Deployment/burner   cpu: 150%/50%   1         6         6

NAME     READY   UP-TO-DATE   AVAILABLE
burner   3/6     3            3

NAME   REQUEST
pods   pods: 3/3
```

The HPA set `replicas` to 6, and its conditions report nothing wrong:

```text
AbleToScale=True ReadyForNewScale: recommended size matches current size
ScalingActive=True ValidMetricFound: the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
ScalingLimited=False DesiredWithinRange: the desired count is within the acceptable range
```

`ScalingLimited=False`: as far as the HPA knows, it isn't limited. Its job ends at writing `replicas`. Creating the Pods is the ReplicaSet's job, and that's where the quota refuses them, visible only in the ReplicaSet's events:

```text
Error creating: pods "burner-6cb89cc99b-wqrgv" is forbidden: exceeded quota: pods, requested: pods=1, used: pods=3, limited: pods=3
```

The CPU stays above target and nothing more can be added. When `READY` stays below `REPLICAS` on an autoscaled Deployment, the reason is in the ReplicaSet's events or in Pods stuck `Pending`, not in the HPA.

## Where this series goes next

Installing RKE2 without internet access: the air-gapped install, with its images loaded from a tarball or a private registry.

These commands ran on a single-node RKE2 v1.36.4 cluster inside a Docker container in a cloud sandbox, not on the Proxmox homelab the earlier entries used.
