# Podman equivalents to Docker's Dive image-layer explorer

There's no single Podman subcommand that reproduces [Dive](https://github.com/wagoodman/dive)'s interactive layer browser and wasted-space score. But Dive itself already speaks Podman natively, and Podman's own commands cover most of what Dive shows — just split across a few of them instead of one UI.

## Dive already supports Podman directly

Per [Dive's own README](https://github.com/wagoodman/dive#readme), `--source` isn't Docker-only:

```sh
dive <your-image> --source podman
# or, equivalently
dive podman://<your-image>
```

Same interactive layer/efficiency UI as the Docker workflow, just pointed at Podman's image store instead of the Docker daemon.

One thing worth being precise about: `dive build -t <tag> .` (Dive's "build then immediately analyze" shortcut) is documented as a wrapper around a Docker build, not Podman — there's no mention of it driving `podman build`. For a Podman workflow, build with `podman build` first and analyze the result with `dive <tag> --source podman` as a second step.

## The native Podman commands, split by what each one shows

### `podman image tree` — the layer hierarchy

```sh
podman image tree docker.io/library/wordpress
```

Prints every layer with its ID and size in a tree, and marks which tag sits at the top of each branch. Add `--whatrequires` to flip the question around — given a layer or image ID, show every image built on top of it:

```sh
podman image tree ae96a4ad4f3f --whatrequires
```

### `podman history` — what command produced each layer

```sh
podman history --no-trunc --human=false <image-name>
```

`--human` is `true` by default (sizes and dates in a readable format); `--no-trunc` stops the `CreatedBy` column from being cut off. `--format` takes a Go template over the same fields — `.ID`, `.Created`, `.CreatedBy`, `.Size`, `.Comment`, `.Tags` — for scripting:

```sh
podman history --format "{{.ID}} {{.Created}} {{.CreatedBy}}" <image-name>
```

### `podman image diff` — what files each layer actually changed

```sh
podman image diff <image-name>
```

Compares the image to its parent layer (or to a second image given explicitly) and prefixes each path with `A`/`D`/`C` (added/deleted/changed). Per [the podman-image-diff manual](https://docs.podman.io/en/latest/markdown/podman-image-diff.1.html), `json` is the *only* other output `--format` accepts here — it's not a general Go-template flag like `history`'s:

```sh
podman image diff --format json redis:old redis:alpine
```

### `podman image inspect` — the full metadata, including raw layer IDs

```sh
podman image inspect --format "{{.RootFS.Layers}}" <image-name>
```

`RootFS` is one of the documented top-level fields; its `Layers` list is the same diff-ID list from the image's OCI config, in build order.

## Beyond Podman itself

- **Skopeo** inspects an image straight from a registry, no pull required: `skopeo inspect docker://registry.access.redhat.com/ubi8/ubi`. (Older writeups mention a `skopeo layers` subcommand for dumping layer tarballs — it's gone from current Skopeo; [the current command list](https://github.com/containers/skopeo/blob/main/docs/skopeo.1.md#commands) has no `layers` entry. To get layer blobs onto disk today, `skopeo copy docker://image dir:/path/to/output` and read them out of the resulting directory.)
- **Syft** and **Grype** both understand a Podman source directly — `podman:` is a documented scheme, not just `docker:`/`registry:` ([syft](https://github.com/anchore/syft/blob/main/cmd/syft/internal/commands/scan.go), [grype](https://github.com/anchore/grype/blob/main/cmd/grype/cli/commands/root.go) both list it in their own `--help` text):
  ```sh
  syft podman:yourrepo/yourimage:tag
  grype podman:yourrepo/yourimage:tag --scope all-layers
  ```
  `--scope all-layers` (default is squashed — only the final merged filesystem) makes Grype match vulnerabilities against packages that exist in an intermediate layer even if a later layer deleted them.
- **[Podman Desktop's Image Layers Explorer extension](https://github.com/containers/podman-desktop-extension-layers-explorer)** adds a "Files" tab to an image's details page in the GUI, if a terminal-based tool isn't what you want.

## What Dive gives you that none of the above do

The one thing genuinely missing from the native commands: Dive's wasted-space *score* — an estimate of how much of an image's size comes from files duplicated or shadowed across layers, not just a per-layer size list. `podman history` tells you how big each layer is; it doesn't tell you how much of that is redundant with another layer. That's the actual reason to reach for Dive specifically instead of stitching together `image tree` + `history` + `image diff`.
