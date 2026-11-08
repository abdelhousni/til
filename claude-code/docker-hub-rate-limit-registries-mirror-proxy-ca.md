# Docker Hub said 429: pulling base images from the distributions' own registries and a Docker Hub mirror, then trusting the proxy inside the containers

While testing [the apt, dnf and pacman cheat sheet](../package-managers/apt-dnf-pacman-side-by-side-ubuntu-fedora-arch.md) in a Claude Code cloud session, the very first `docker pull` failed. Getting three distribution images took four registries and one daemon setting. Then the containers couldn't download packages over HTTPS, and fixing that took a second workaround. This entry records both, with what each registry documents about its limits.

A **registry** is a server that stores container images, and an image name starts with the registry it comes from: `quay.io/fedora/fedora:45` is the `fedora/fedora` repository on `quay.io`, tag `45`. A name without a registry, such as `ubuntu:26.04`, means Docker Hub (`docker.io/library/ubuntu:26.04`). [Docker and Podman hello world](../podman/docker-and-podman-hello-world.md) explains images and containers.

## The error

```text
$ docker pull ubuntu:26.04
Error response from daemon: unknown: failed to resolve reference "docker.io/library/ubuntu:26.04":
unexpected status from HEAD request to https://registry-1.docker.io/v2/library/ubuntu/manifests/26.04:
429 Too Many Requests
```

The same came back for `fedora:45` and `archlinux:latest`. HTTP 429 means the server is rate-limiting the client. Docker Hub's [usage page](https://docs.docker.com/docker-hub/usage/) gives the limit for pulls without an account: **100 pulls per 6 hours, per IPv4 address or IPv6 /64 subnet**. A Docker Hub account raises it to 200. This session had pulled nothing yet, so the limit was already spent on its outbound address: a cloud session most likely shares that address with other workloads, whose pulls count against the same 100.

## What worked, registry by registry

| Image | Tried | Result |
|---|---|---|
| Ubuntu 26.04 | `docker.io/library/ubuntu:26.04` | 429 |
| | `public.ecr.aws/ubuntu/ubuntu:26.04` | `Error from registry: Data limit exceeded` |
| | `mirror.gcr.io/library/ubuntu:26.04` | pulled |
| Fedora 45 | `quay.io/fedora/fedora:45` | pulled |
| Arch | `ghcr.io/archlinux/archlinux:latest` | pulled |

**Amazon ECR Public** (`public.ecr.aws`) hosts official Ubuntu images. Its [quotas page](https://docs.aws.amazon.com/AmazonECR/latest/public/public-service-quotas.html) allows unauthenticated clients up to 500 GB of data per month and 1 unauthenticated pull per second, and neither is adjustable. "Data limit exceeded" means the shared address had used up the 500 GB.

**`mirror.gcr.io`** is Google's cache of Docker Hub. Google's [page on it](https://docs.cloud.google.com/artifact-registry/docs/pull-cached-dockerhub-images) says it holds *frequently accessed* public Docker Hub images, and removes images nobody requests any more. It also says that pulls from it don't count against Docker Hub's rate limits. A popular image like `ubuntu:26.04` is in it. A rarely pulled one may not be.

**The distributions' own registries** don't go through Docker Hub at all:

- Fedora releases its `fedora` and `fedora-minimal` base images to its own `registry.fedoraproject.org` and to `quay.io` ([Fedora release engineering](https://pagure.io/releng/issue/11006)).
- Arch publishes its images daily to `docker.io/archlinux/archlinux`, `quay.io/archlinux/archlinux` and `ghcr.io/archlinux/archlinux`, and the weekly official `docker.io/library/archlinux`. The three daily ones are signed with cosign, a tool that signs and verifies container images, with the identity and command given in the [archlinux-docker README](https://github.com/archlinux/archlinux-docker). The signature wasn't checked here, because cosign isn't installed in the session.

## The mirror as a daemon setting

Google's page supports `mirror.gcr.io` as a *registry mirror* rather than as a name to pull from. It's a setting of the Docker daemon (`dockerd`, the background service that pulls and runs containers), in `/etc/docker/daemon.json`:

```json
{ "registry-mirrors": ["https://mirror.gcr.io"] }
```

After restarting `dockerd`, `docker info` showed `[https://mirror.gcr.io/]` under the mirrors. A plain `docker pull ubuntu:24.04` and `docker pull debian:13` then succeeded with no 429, and the images keep their Docker Hub names. That's the better fix. Dockerfiles and scripts don't change, and any image the mirror doesn't hold falls back to Docker Hub. Pulling `mirror.gcr.io/library/ubuntu:26.04` by name worked too, but the image then carries the mirror's name.

## Second problem: HTTPS inside the containers

With the images pulled, Ubuntu's `apt update` worked, and Fedora and Arch failed:

```text
Curl error (60): SSL peer certificate or SSH remote key was not OK for
https://mirrors.fedoraproject.org/metalink?repo=updates-released-f45&arch=x86_64
[SSL certificate OpenSSL verify result: self-signed certificate in certificate chain (19)]
```

A cloud session sends its outbound HTTPS through a proxy that inspects the traffic, and presents its own certificate authority (CA). The session's own tools are set up to trust that CA, but a container starts from its image's trust store, which doesn't contain it. Ubuntu got away with it because its repositories are configured over plain `http://` (the packages are still checked against the GPG keys named in `Signed-By`). Fedora's metalink and Arch's mirrors use HTTPS.

The README the environment ships for its proxy describes the fix, and it has three parts. The containers share the host's network, so they can reach the proxy listening on `127.0.0.1`. They get the proxy variables. And each one gets the CA in its own trust store directory, then rebuilds that store:

```bash
CA=/path/to/the/session-ca-bundle.crt   # the proxy README gives the path

# Fedora
docker run --rm --network host -e HTTPS_PROXY -e https_proxy \
  -v "$CA":/etc/pki/ca-trust/source/anchors/session-proxy.crt:ro \
  quay.io/fedora/fedora:45 bash -c 'update-ca-trust && dnf -q makecache'

# Arch
docker run --rm --network host -e HTTPS_PROXY -e https_proxy \
  -v "$CA":/etc/ca-certificates/trust-source/anchors/session-proxy.crt:ro \
  ghcr.io/archlinux/archlinux:latest bash -c 'update-ca-trust && pacman -Syu --noconfirm'

# Ubuntu, for HTTPS sources such as snapshot.ubuntu.com
docker run --rm --network host -e HTTPS_PROXY -e https_proxy \
  -v "$CA":/usr/local/share/ca-certificates/session-proxy.crt:ro \
  ubuntu:26.04 bash -c 'apt-get update && apt-get install -y ca-certificates && update-ca-certificates'
```

`-e HTTPS_PROXY` with no value passes the variable from the calling shell. After this, `dnf` built its cache and `pacman -Syu` succeeded, and so did everything in the cheat sheet. For `docker build`, the same README says to copy the CA into the build context and install it in an early layer.

## In short

- Docker Hub without an account: 100 pulls per 6 hours per address, and a shared address may have none left.
- A distribution's own registry (`quay.io/fedora`, `ghcr.io/archlinux`) avoids Docker Hub completely.
- `registry-mirrors: ["https://mirror.gcr.io"]` keeps Docker Hub names and skips its limit for popular images.
- ECR Public has its own monthly data cap for anonymous pulls.
- Behind an inspecting proxy, containers need the proxy's CA in their own trust store, plus the host network and the proxy variables.

Everything here ran in a Claude Code cloud session with Docker 29.9.2, on 7 and 8 November 2026. The proxy and its CA are specific to that environment. On a workstation or a CI runner, the registry part applies but the CA part usually doesn't.
