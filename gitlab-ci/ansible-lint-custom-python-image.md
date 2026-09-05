# A simple GitLab CI pipeline for ansible-lint on a custom Python image

Installing `ansible-lint` with `pip` inside every single pipeline run works, but it's slow and re-downloads the same packages on every commit. Building a small custom image once — based on the official `python` image, nothing fancier — and reusing it is barely more setup and considerably faster.

## The image

```dockerfile
# Dockerfile
FROM python:3.13-slim
RUN pip install --no-cache-dir ansible-core ansible-lint
```

That's the whole image: the official Python base plus the two packages actually needed.

## The pipeline

```yaml
stages:
  - build
  - lint

build-image:
  stage: build
  image: docker:24.0.5-dind
  services:
    - docker:24.0.5-dind
  rules:
    - changes:
        - Dockerfile
  before_script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
  script:
    - docker build -t "$CI_REGISTRY_IMAGE/ansible-lint:latest" .
    - docker push "$CI_REGISTRY_IMAGE/ansible-lint:latest"

lint:
  stage: lint
  image: "$CI_REGISTRY_IMAGE/ansible-lint:latest"
  script:
    - ansible-lint .
```

Two things doing the actual work:

- **`rules: changes: [Dockerfile]`** on the build job means it only rebuilds and re-pushes when the Dockerfile itself changes — every other commit skips straight to `lint`, which just pulls the already-built image (fast, and it's exactly the same image every time, not rebuilt-and-maybe-slightly-different).
- **`$CI_REGISTRY_IMAGE`, `$CI_REGISTRY_USER`, `$CI_REGISTRY_PASSWORD`, `$CI_REGISTRY`** are all predefined GitLab CI variables — nothing to configure in project settings, they're populated automatically per-job and scoped to that project's own Container Registry.

The very first pipeline run still has to build the image (no `Dockerfile` diff to compare against yet), so it'll run both jobs once regardless.

## The honest caveat

`docker:dind` needs the runner configured for **privileged mode**, which is a real security tradeoff on a shared runner (a privileged container can potentially interact with the host). Fine on a personal or trusted-team runner; GitLab's own docs currently point at BuildKit or Buildah as ways to build without privileged mode if that matters for your setup — outside the scope of "simple," but worth knowing it exists before wiring this into anything shared.
