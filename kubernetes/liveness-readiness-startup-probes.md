# A liveness probe restarts a container, a readiness probe only takes it out of the Service

Fifteenth entry in the RKE2/Kubernetes series. [The object model entry](pods-deployments-services-object-model.md) showed a Deployment replacing a Pod that disappears. It didn't cover a container that keeps running but has stopped working: a deadlocked server, or a process stuck on a dependency. Kubernetes only knows about that if it asks, and a *probe* is how it asks. This entry runs the three kinds of probe on RKE2 v1.36.4 and checks what each one does when the answer is "no".

## Three probes, three different consequences

A probe is a check that the *kubelet*, the agent on each node that starts and watches containers, runs against a container on a schedule. Per [Kubernetes' probe docs](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/), there are three kinds, and what separates them is what happens when the check fails:

| Probe | Question | On failure |
|---|---|---|
| `livenessProbe` | Is the process still working? | The kubelet kills the container and restarts it |
| `readinessProbe` | Should it get traffic right now? | The Pod is taken out of its Services' endpoints; nothing restarts |
| `startupProbe` | Has it finished starting? | Liveness and readiness checks wait; after `failureThreshold` failures, the container is killed |

Each one checks in one of four ways: an HTTP `GET` that must return a status from 200 to 399, a TCP connection that must open, a gRPC health check, or a command run inside the container (`exec`) that must exit 0. The timing fields are the same for all of them. The defaults: every `periodSeconds: 10`, give up on one attempt after `timeoutSeconds: 1`, act after `failureThreshold: 3` failures in a row.

The examples use `agnhost`, the Kubernetes project's own test image. Its `liveness` mode serves `/healthz` with status 200 for 10 seconds, then with 500 for good, which makes it a server that breaks on cue.

## Liveness: a failing check restarts the container, in place

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: liveness-http
  namespace: probes
spec:
  containers:
    - name: app
      image: registry.k8s.io/e2e-test-images/agnhost:2.53
      args: ["liveness"]
      livenessProbe:
        httpGet:
          path: /healthz
          port: 8080
        periodSeconds: 3
        failureThreshold: 3
```

75 seconds later:

```sh
kubectl -n probes get pod liveness-http -o wide
kubectl -n probes get events --field-selector involvedObject.name=liveness-http
```

```text
NAME            READY   STATUS             RESTARTS     AGE   IP           NODE
liveness-http   0/1     CrashLoopBackOff   3 (3s ago)   75s   10.42.0.16   vm

REASON      COUNT   MESSAGE
Started     4       Container started
Unhealthy   12      Liveness probe failed: HTTP probe failed with statuscode: 500
Killing     4       Container app failed liveness probe, will be restarted
BackOff     2       Back-off restarting failed container app in pod liveness-http_probes(...)
```

What this shows:

- **The timing adds up.** The container started at 20:10:48 and was killed at 20:11:05: 10 healthy seconds, then three failed checks 3 seconds apart.
- **It's the same Pod.** The name, the IP and the node don't change. The kubelet restarts the *container* inside the existing Pod. No new Pod is scheduled, which is the difference from the Deployment replacement in the object model entry.
- **`CrashLoopBackOff` doesn't mean it crashed.** The process never exited on its own. After repeated restarts, the kubelet waits longer and longer before each new start. That waiting state is called `CrashLoopBackOff` whatever caused the restarts. The `Killing` event tells a liveness kill apart from a real crash.
- **Four restarts in 75 seconds didn't fix anything.** A restart only helps when the fault is in the process's own state. This server fails again ten seconds after every start.

## Readiness: a failing check removes the Pod from the Service, nothing restarts

A Deployment of two replicas behind a Service. The readiness probe is an `exec` check that passes as long as `/tmp/ready` exists:

```yaml
          command: ["sh", "-c", "touch /tmp/ready && exec /agnhost netexec --http-port=8080"]
          readinessProbe:
            exec:
              command: ["cat", "/tmp/ready"]
            periodSeconds: 2
            failureThreshold: 1
```

A Service doesn't send traffic to Pods directly. It sends it to the addresses listed in its *EndpointSlices*, which the control plane keeps up to date, with a `ready` condition on each address. Both Pods start ready. Deleting the file in one of them:

```sh
kubectl -n probes exec web-6dc6747479-5dvhz -- rm /tmp/ready
kubectl -n probes get pods -l app=web
kubectl -n probes get endpointslices -l kubernetes.io/service-name=web \
  -o jsonpath='{range .items[0].endpoints[*]}{.targetRef.name} ready={.conditions.ready}{"\n"}{end}'
```

```text
NAME                   READY   STATUS    RESTARTS   AGE
web-6dc6747479-5dvhz   0/1     Running   0          9s
web-6dc6747479-hvl89   1/1     Running   0          9s
web-6dc6747479-hvl89 ready=true
web-6dc6747479-5dvhz ready=false
```

`0/1`, still `Running`, zero restarts, and marked not ready in the EndpointSlice, so the Service stops routing to it. Putting the file back brings it back to `1/1` within one check, still with no restart. Readiness is for "alive, but don't send traffic now": warming a cache, a dependency that's down, being overloaded.

## Startup: protecting a slow start from the liveness probe

A container that takes 30 seconds to start listening, with a liveness probe that gives up after 15 (3 failures, 5 seconds apart):

```yaml
      command: ["sh", "-c", "sleep 30 && exec /agnhost netexec --http-port=8080"]
      livenessProbe:
        httpGet: {path: /healthz, port: 8080}
        periodSeconds: 5
        failureThreshold: 3
```

Created twice: `slow-without` exactly as above, and `slow-with` with a startup probe added that allows up to 60 seconds (12 failures × 5 seconds):

```yaml
      startupProbe:
        httpGet: {path: /healthz, port: 8080}
        periodSeconds: 5
        failureThreshold: 12
```

Three minutes later:

```text
NAME           READY   STATUS    RESTARTS     AGE
slow-with      1/1     Running   0            3m2s
slow-without   1/1     Running   4 (2s ago)   3m2s
```

```text
== slow-without
Unhealthy   8   Liveness probe failed: Get "http://10.42.0.19:8080/healthz": dial tcp 10.42.0.19:8080: connect: connection refused
Killing     2   Container app failed liveness probe, will be restarted
== slow-with
Unhealthy   6   Startup probe failed: Get "http://10.42.0.20:8080/healthz": dial tcp 10.42.0.20:8080: connect: connection refused
```

`slow-without` never gets to serve: liveness kills it before startup finishes, every time, forever. `slow-with` fails its startup probe six times (30 seconds), then passes, and only then does the liveness probe start checking. Raising `initialDelaySeconds` on the liveness probe would also get it through. But that delay applies to every start, and liveness can't detect anything while it runs. A startup probe stops waiting as soon as the container answers.

`slow-without` also shows `1/1`. With no readiness probe, a container counts as ready as soon as it's running, so for the first 30 seconds of each start a Service would have sent it requests it refused.

## A liveness kill waits for the grace period

The last run of `slow-without` ended like this:

```sh
kubectl -n probes get pod slow-without \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated.startedAt} -> {.status.containerStatuses[0].lastState.terminated.finishedAt} exit={.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

```text
2026-10-24T20:13:53Z -> 2026-10-24T20:14:37Z exit=137
```

The probe gave up after about 15 seconds, yet the container lived 44. A liveness kill is an ordinary stop. The kubelet sends `SIGTERM` and waits up to the Pod's `terminationGracePeriodSeconds`, 30 by default, before sending `SIGKILL`. The process here is `sh`, running as PID 1 of the container, and the Linux kernel doesn't deliver signals to PID 1 unless it has installed a handler for them. So `SIGTERM` did nothing, and `SIGKILL` came 30 seconds later. Exit code 137 is 128 + 9, killed by signal 9 (`SIGKILL`). The first Pod, where `agnhost` itself was PID 1, exited at once with code 2.

The probe has its own `terminationGracePeriodSeconds` field, which overrides the Pod's value for liveness and startup kills only. It exists because a hung process, the thing liveness is there to catch, is the one least likely to exit cleanly on `SIGTERM`.

## What a liveness probe should check

The restarts above follow from what each probe checks:

- A liveness check that calls a database restarts every replica at once when the database goes down. None of the restarts bring the database back.
- An `exec` probe forks a process every `periodSeconds` in every container. HTTP and TCP checks don't.
- `timeoutSeconds: 1` counts as a failure. On a loaded node, a slow response is enough to trigger a restart.

The probe docs draw the same line between the two checks: a liveness probe is for a container that can't recover without a restart, a readiness probe for one that is temporarily unable to serve.

## Where this series goes next

Autoscaling with the HorizontalPodAutoscaler: adding and removing replicas based on the CPU requests that the namespaces entry made mandatory.

These commands ran on a single-node RKE2 v1.36.4 cluster inside a Docker container in a cloud sandbox, not on the Proxmox homelab the earlier entries used.
