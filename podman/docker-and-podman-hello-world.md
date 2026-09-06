# Sanity-checking a fresh Docker or Podman install with each engine's own hello-world

After installing either engine, the fastest way to confirm pull + run + registry access all actually work end-to-end is each project's own tiny smoke-test image — no Dockerfile, no app code, just "did this work."

## Docker

```sh
docker run hello-world
```

Pulls the official `hello-world` image from Docker Hub, runs it, and prints its own explanation of what just happened:

```
Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent
    it to your terminal.
```

That's genuinely useful as a checklist — if any of those four steps fail, the error tells you exactly which layer broke (client-to-daemon socket, registry pull, container runtime, or the stream back to your terminal).

## Podman

```sh
podman run quay.io/podman/hello
```

Podman's own version lives on Quay, not Docker Hub, and confirms the same four steps work for Podman's architecture specifically (no daemon at all for Podman — the client *is* the runtime, so a working pull+run here also rules out the whole daemon-vs-daemonless distinction as a source of confusion):

```
!... Hello Podman World ...!

         .--"--.
       / -     - \
      / (O)   (O) \
   ~~~| -=(,Y,)=- |
```
(ASCII art, then project links.)

## They're not actually locked to their own registries

Both are just standard OCI images on public registries, so either engine can pull either image:

```sh
podman run docker.io/library/hello-world
docker run quay.io/podman/hello
```

Handy for confirming a specific engine's *registry access* works, independent of which vendor happens to host the test image.

## They don't clean up after themselves

Both leave a stopped, exited container sitting around afterward — visible in `docker ps -a` / `podman ps -a` — since neither passes `--rm`. Fine for a one-off check; add `--rm` if running this repeatedly (e.g., scripted into a health check) to avoid accumulating exited containers:

```sh
podman run --rm quay.io/podman/hello
```
