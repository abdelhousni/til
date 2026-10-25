# A simple GitLab CI pipeline for ansible-lint on a custom Python image

Installing `ansible-lint` with `pip` inside every single pipeline run works, but it's slow and re-downloads the same packages on every commit. Building a small custom image once — based on the official `python` image, nothing fancier — and reusing it is barely more setup and considerably faster.

The GitLab terms used below, as [GitLab's CI/CD docs](https://docs.gitlab.com/ci/) use them: a *pipeline* is made up of *stages* and *jobs* and starts whenever something triggers it, such as a commit; a *job* is the task performed in a stage; a *runner* is the agent that runs your jobs, and its *executor* decides how (Docker, Kubernetes, shell…). An *image* here is a container image: each job runs inside one. The *Container Registry* is the store for container images that every GitLab project has, and `docker:dind` (Docker-in-Docker) is an image that runs its own Docker engine inside the job, which is what lets a job build images.

## The image

```dockerfile
# Dockerfile
FROM python:3.13-slim
RUN pip install --no-cache-dir ansible-core ansible-lint
```

That's the whole image: the official Python base plus the two packages actually needed.

## The pipeline

This version assumes a runner with the **Docker executor** in privileged mode (see the caveat below for the other cases):

```yaml
stages:
  - build
  - lint

build-image:
  stage: build
  image: docker:24.0.5
  services:
    - docker:24.0.5-dind
  timeout: 20m
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
    - changes:
        - Dockerfile
        - .gitlab-ci.yml
  before_script:
    - echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"
  script:
    - docker build -t "$CI_REGISTRY_IMAGE/ansible-lint:latest" .
    - docker push "$CI_REGISTRY_IMAGE/ansible-lint:latest"

lint:
  stage: lint
  image: "$CI_REGISTRY_IMAGE/ansible-lint:latest"
  script:
    - ansible-lint .
```

The things doing the actual work:

- **`rules: changes:`** on the build job means it only rebuilds and re-pushes when the `Dockerfile` or the pipeline definition changes — every other commit skips straight to `lint`, which just pulls the already-built image.
- **`$CI_REGISTRY_IMAGE`, `$CI_REGISTRY_USER`, `$CI_REGISTRY_PASSWORD`, `$CI_REGISTRY`** are all predefined GitLab CI variables — nothing to configure in project settings, they're populated automatically per-job and scoped to that project's own Container Registry. The password goes in through `--password-stdin` rather than `-p`, so it never sits on a command line.
- **The job image is plain `docker`** (just the CLI); only the service needs `-dind`, since that's where the engine runs.

## Bootstrapping the image

On a push, `changes:` compares against the previous commit. So if you add this pipeline to an existing repository and the push doesn't touch the `Dockerfile` or `.gitlab-ci.yml`, the build is skipped, and `lint` fails with `ImagePullBackOff` / `not found` because the image doesn't exist yet. (A brand-new branch has nothing to compare against, so there `changes:` matches and both jobs run.)

That's what the `if: $CI_PIPELINE_SOURCE == "web"` rule is for: start a pipeline by hand from **Build > Pipelines > Run pipeline**, and it always builds. Do that once to create the image, and again whenever you want to pick up newer `ansible-lint` releases.

Two related things worth knowing:

- **"Same image every time" only holds between rebuilds.** `:latest` is overwritten on every build, and the unpinned `pip install` can pull newer versions each time. If you want reproducible lint results, pin the versions (`ansible-lint==X.Y.Z`) or also tag the image with `$CI_COMMIT_SHORT_SHA`.
- **A green `lint` job doesn't prove anything was linted.** On a repository with no Ansible content yet, `ansible-lint .` passes with "0 files processed". Check that line in the job log once you've added real content.

## The honest caveat

`docker:dind` needs the runner configured for **privileged mode**, which is a real security tradeoff on a shared runner (a privileged container can potentially interact with the host). Fine on a personal or trusted-team runner.

If the runner *doesn't* allow it, the job doesn't fail cleanly: the dind service never starts, and anything waiting for the engine hangs until the job times out — an hour by default. That's why the build job above sets `timeout: 20m`.

The snippet also depends on the executor:

- **Docker executor:** works as written, as long as the runner shares the TLS certificates that `docker:24` dind generates by default (`volumes = ["/certs/client"]` in the runner's `config.toml`).
- **Kubernetes executor:** services run in the same pod as the job, so the engine is on `localhost`, not on the `docker` hostname. Add `DOCKER_HOST: tcp://localhost:2375` and `DOCKER_TLS_CERTDIR: ""` under `variables:`, and wait for the engine before logging in: `until docker info >/dev/null 2>&1; do sleep 1; done`. It still needs privileged pods.

### Building without privileged mode

[Kaniko](https://github.com/GoogleContainerTools/kaniko) builds images from a Dockerfile without a Docker engine, so it runs as an ordinary unprivileged job on any executor. It replaces the build job like this:

```yaml
build-image:
  stage: build
  image:
    name: martizih/kaniko:v1.28.5-debug
    entrypoint: [""]
  timeout: 20m
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
    - changes:
        - Dockerfile
        - .gitlab-ci.yml
  script:
    - |
      cat > /kaniko/.docker/config.json <<EOF
      {"auths":{"$CI_REGISTRY":{"auth":"$(printf '%s:%s' "$CI_REGISTRY_USER" "$CI_REGISTRY_PASSWORD" | base64 | tr -d '\n')"}}}
      EOF
    - /kaniko/executor
        --context "$CI_PROJECT_DIR"
        --dockerfile "$CI_PROJECT_DIR/Dockerfile"
        --destination "$CI_REGISTRY_IMAGE/ansible-lint:latest"
```

The `-debug` variant is needed because it ships a shell for `script:`, and the empty `entrypoint` stops Kaniko from running before the script does. Upstream Kaniko (`gcr.io/kaniko-project/executor`) was archived in 2025; it still works, but `martizih/kaniko` is a maintained fork. GitLab's own docs also point at BuildKit (rootless) and Buildah.

These pipelines were run on a GitLab runner on a private RKE2 (Kubernetes) node, not in the Linux cloud container where this entry was drafted.
