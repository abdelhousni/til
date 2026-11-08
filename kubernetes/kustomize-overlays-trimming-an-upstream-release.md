# Kustomize overlays: trimming an upstream release without editing it

[The kube-prometheus entry](kube-prometheus-on-rke2-step-by-step.md) installs a release of 131 objects as 62: no Grafana, no prometheus-adapter, one Prometheus instead of two. None of the release's files were edited. The changes are a Kustomize *overlay*, one file next to the unpacked release, and this entry goes through it.

## Kustomize in one paragraph

[Kustomize](https://kubectl.docs.kubernetes.io/references/kustomize/) builds Kubernetes manifests from a `kustomization.yaml`: a list of `resources` (files, or directories with their own `kustomization.yaml`) plus changes to apply to them. It ships inside `kubectl`: `kubectl kustomize <dir>` prints the result, and `kubectl apply -k <dir>` applies it. kubectl v1.37.1 reports `Kustomize Version: v5.8.1` in `kubectl version --client`. An *overlay* is a `kustomization.yaml` whose resource is another directory, the *base*, and which only adds changes on top.

kube-prometheus generates its manifests from jsonnet, and its documentation customizes them by compiling your own copy from its jsonnet library. It also publishes a `kustomization.yaml` at the root of the release, listing every file, so the release as unpacked is a valid base. The overlay uses that:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../upstream        # the release, unpacked here as published
patches:
  # ...
```

A new release is a new `../upstream`. Every local change is in `patches`, and nothing else differs from what the project ships.

## Deleting objects: `$patch: delete`

`patches` takes two kinds of patch. A *strategic merge patch* looks like a piece of the object, and Kubernetes' [strategic merge patch](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-api-machinery/strategic-merge-patch.md) adds directives to it: `$patch: delete` "indicates that the element that contains it should be deleted". At the top of a patch, the element is the whole object, so the object is removed from the output. Kustomize's own [`loadHttp` example](https://github.com/kubernetes-sigs/kustomize/blob/master/examples/loadHttp/kustomization.yaml) removes a RoleBinding that way.

A `target` makes one patch apply to every object it selects, by group, version, kind, name, namespace, label or annotation:

```yaml
patches:
  - target:
      labelSelector: app.kubernetes.io/name=prometheus-adapter
    patch: &delete |-
      $patch: delete
      apiVersion: v1
      kind: Any
      metadata:
        name: any
  - target:
      labelSelector: app.kubernetes.io/name=blackbox-exporter
    patch: *delete
  - target:
      name: grafana(-config|-datasources|-dashboards|-rules)?
    patch: *delete
  - target:
      kind: ConfigMap
      name: grafana-dashboard-.*
    patch: *delete
  - target:
      kind: ServiceMonitor
      name: kube-scheduler|kube-controller-manager|coredns
    patch: *delete
  - target:
      kind: PodDisruptionBudget
    patch: *delete
```

Four things make this work:

- **The patch's own kind and name don't matter.** Per the [patches reference](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/), the target selects, and by default "the patch will leave the kind and name of the resource untouched". `kind: Any` and `name: any` are placeholders for a patch that has to look like an object.
- **Names are regular expressions, anchored.** The same reference: "The name and namespace fields of the patch target selector are automatically anchored regular expressions". `grafana(-config|-datasources|-dashboards|-rules)?` matches `grafana` and four other names exactly, of any kind: the Deployment, Service, ServiceAccount, NetworkPolicy and ServiceMonitor called `grafana`, the Secrets `grafana-config` and `grafana-datasources`, the ConfigMap `grafana-dashboards` (where Grafana finds its dashboards) and the PrometheusRule `grafana-rules`. It doesn't match `grafana-dashboard-nodes`: the 33 dashboards need their own pattern.
- **A label selects a whole component.** Every object of prometheus-adapter carries `app.kubernetes.io/name=prometheus-adapter`, including its cluster-wide RBAC and its `APIService`, which would otherwise take `kubectl top` over from RKE2's metrics-server.
- **One patch, written once.** `&delete` and `*delete` are a plain YAML anchor and alias: the same text, reused.

## Changing a custom resource: JSON patches

The other kind is a *JSON patch* ([RFC 6902](https://www.rfc-editor.org/rfc/rfc6902)): a list of operations on paths. The patches reference notes that strategic merge patches "may require additional configuration" for custom resources, while "JSON6902 patch usage is the same for built-in and custom resources". `Prometheus` is a custom resource, so its changes are JSON operations:

```yaml
  - target:
      kind: Prometheus
      name: k8s
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
      - op: add
        path: /spec/retention
        value: 7d
      - op: add
        path: /spec/retentionSize
        value: 2GB
      - op: replace
        path: /spec/resources
        value:
          requests:
            memory: 400Mi
          limits:
            memory: 2Gi
      - op: add
        path: /spec/storage
        value:
          volumeClaimTemplate:
            spec:
              storageClassName: local-path
              accessModes: [ReadWriteOnce]
              resources:
                requests:
                  storage: 4Gi
```

`replace` needs the field to exist: upstream sets `replicas: 2` and a 400Mi memory request. `add` creates it: upstream has no `retention` (the CRD's default is "24h" when no retention setting is given) and no `storage`. Alertmanager gets the same `replace` of its `replicas`, 3 upstream.

## Removing list items by position, safely

JSON paths address list items by index. The overlay drops two groups of alert rules for the scheduler and controller manager, whose targets don't exist on RKE2:

```yaml
  - target:
      kind: PrometheusRule
      name: kubernetes-monitoring-rules
    patch: |-
      - op: test
        path: /spec/groups/8/name
        value: kubernetes-system-controller-manager
      - op: remove
        path: /spec/groups/8
      - op: test
        path: /spec/groups/7/name
        value: kubernetes-system-scheduler
      - op: remove
        path: /spec/groups/7
```

Two details:

- **Each `remove` is guarded by a `test`.** If a later release reorders the groups, index 8 is another group, and a bare `remove` would delete it without a word. `test` compares the value at the path, and per RFC 6902 a failing operation ends the whole patch. With a wrong expected value, the render stops:

  ```
  Error: testing value /spec/groups/8/name failed: test failed
  ```

- **The higher index goes first.** Operations run in order. Removing group 7 first would shift the controller manager's group from 8 to 7, and the next test would fail.

## Checking what the overlay did

`kubectl kustomize` doesn't need a cluster. Counting the objects and their kinds, before and after:

```bash
kubectl kustomize upstream | grep -c '^kind:'     # 131
kubectl kustomize overlay  | grep -c '^kind:'     # 62

diff <(kubectl kustomize upstream | grep '^kind:' | sort | uniq -c) \
     <(kubectl kustomize overlay  | grep '^kind:' | sort | uniq -c)
```

The `diff` shows, for example, all 36 ConfigMaps going away (the 33 dashboards, `grafana-dashboards`, and prometheus-adapter's and blackbox-exporter's configuration), the one `APIService`, the three PodDisruptionBudgets, and 13 ServiceMonitors becoming 7. For the names of what went away, this lists each object as `Kind/name` and keeps those only in the first render:

```bash
names() { kubectl kustomize "$1" |
  awk '/^---/{k="";m=0} /^kind:/{k=$2} /^metadata:/{m=1} m&&/^  name:/{print k"/"$2; m=0}' | sort; }
comm -23 <(names upstream) <(names overlay)
```

The second check needs the cluster: `kubectl apply --server-side --dry-run=server -k overlay` has the API server validate every object without storing anything, once the CRDs it uses exist.

The renders and the failing `test` ran with kubectl v1.37.1 in a Linux cloud container; the same counts came out on the owner's workstation, and the overlay was then applied to the homelab's RKE2 cluster.

## Sources

- Kustomize: [Kustomization reference](https://kubectl.docs.kubernetes.io/references/kustomize/), [`patches`](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/) (targets, anchored regular expressions, kind and name left untouched, custom resources), [`examples/loadHttp`](https://github.com/kubernetes-sigs/kustomize/blob/master/examples/loadHttp/kustomization.yaml) and [`examples/inlinePatch.md`](https://github.com/kubernetes-sigs/kustomize/blob/master/examples/inlinePatch.md) (`$patch: delete`).
- Kubernetes: [Strategic merge patch](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-api-machinery/strategic-merge-patch.md) (the `delete` directive).
- [RFC 6902](https://www.rfc-editor.org/rfc/rfc6902), JavaScript Object Notation (JSON) Patch: `add`, `replace`, `remove`, `test`, and errors ending the patch.
- kube-prometheus v0.19.0: [`kustomization.yaml`](https://github.com/prometheus-operator/kube-prometheus/blob/v0.19.0/kustomization.yaml), [Customizing Kube-Prometheus](https://github.com/prometheus-operator/kube-prometheus/blob/v0.19.0/docs/customizing.md) (jsonnet), `manifests/prometheus-prometheus.yaml` and `manifests/alertmanager-alertmanager.yaml` (replicas, resources), and the `Prometheus` CRD (`retention` default).
