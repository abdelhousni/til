# Building GitLab CI images on a flaky network

A pipeline that builds its own image — like the [ansible-lint custom Python image](ansible-lint-custom-python-image.md) — pulls the base image from Docker Hub and packages from PyPI on every build. On a restricted or flaky network, that fails at random with errors like:

```text
failed to resolve reference "docker.io/library/python:3.13-slim": dial tcp 34.204.126.254:443: i/o timeout
```

## Check which addresses actually answer

Docker Hub sits behind many IPv4 addresses, and DNS hands out a different one each time. If some of them are blocked somewhere upstream, pulls work or fail depending on which address you land on. A quick test from the affected host:

```sh
for ip in $(getent ahostsv4 registry-1.docker.io | awk '{print $1}' | sort -u); do
  printf '%-16s ' "$ip"; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 \
    --resolve registry-1.docker.io:443:$ip https://registry-1.docker.io/v2/ || echo timeout
done
```

`401` means reachable (that's Docker Hub's normal answer to an anonymous request); `timeout` means that address is dropped. A mix of both points at a firewall, router or ISP, not at the CI configuration. Pinning the good addresses in `/etc/hosts` is tempting, but which ones answer can change from minute to minute, so it doesn't hold up.

## Mirror the base image

Copy the base image into the project's own Container Registry once, from a machine that can reach Docker Hub:

```sh
podman pull docker.io/library/python:3.13-slim
podman tag docker.io/library/python:3.13-slim registry.example.com/group/project/python:3.13-slim
podman push registry.example.com/group/project/python:3.13-slim
```

(`docker` works the same way.) Then build from it, keeping a way back to Docker Hub for local builds:

```dockerfile
ARG BASE_IMAGE=registry.example.com/group/project/python:3.13-slim
FROM ${BASE_IMAGE}
RUN pip install --no-cache-dir ansible-core ansible-lint
```

```sh
docker build --build-arg BASE_IMAGE=docker.io/library/python:3.13-slim -t ansible-lint:local .
```

The build job already logs in to `$CI_REGISTRY`, so it can pull the mirrored image without extra setup. Refresh the mirror when you want a newer base.

## Retry the build job

```yaml
build-image:
  retry: 2
```

Rebuilding and pushing the same tag is harmless, so retrying costs nothing but time. It covers the occasional timeout during `pip install`, which the mirror doesn't.

## The real fix

Both of these are workarounds. If the network can't be fixed, the durable option is a pull-through cache (a registry mirror) on a host that can reach Docker Hub, configured as a mirror for the cluster's container runtime and for the image builder.

These commands were run against a GitLab runner on a private RKE2 (Kubernetes) node, not in the Linux cloud container where this entry was drafted.
