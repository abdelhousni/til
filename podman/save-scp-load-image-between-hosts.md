# Moving a container image between hosts with podman save + scp + load, no registry

Sometimes the easiest way to get an image onto another machine isn't pushing it to a registry — especially for a one-off image, or a homelab box with no registry set up at all. `podman save` / `podman load` round-trips an image through a plain tar file, and `scp` is the only thing in between.

## Save it on the source host

```sh
podman save -o myimage.tar myimage:latest
```

`-o` writes to a file instead of stdout. The default archive format is `docker-archive` (a tar interoperable with `docker load`, not just Podman), so the image is portable to Docker on the other end too if needed.

Worth compressing before it goes anywhere over the network:

```sh
podman save myimage:latest | gzip > myimage.tar.gz
```

## Copy it across

```sh
scp myimage.tar.gz user@remote-host:/tmp/
```

Nothing Podman-specific here — it's just a file.

## Load it on the destination host

```sh
podman load -i myimage.tar.gz
```

No need to `gunzip` first — `podman load` auto-detects a compressed archive and handles it directly. `-i` reads from that file; leave it off entirely and `podman load` reads from stdin instead, which also means this works as one piped command across `ssh` without an intermediate file at all:

```sh
podman save myimage:latest | gzip | ssh user@remote-host 'podman load'
```

Confirm it landed:

```sh
podman images
```

## Saving more than one image at once

`-m`/`--multi-image-archive` bundles multiple images (or multiple tags of the same image) into a single tar, as long as the format stays `docker-archive` (the default):

```sh
podman save -m -o bundle.tar myimage:latest myimage:v1.2 otherimage:latest
```

`podman load` then restores all of them from that one file in one go.
