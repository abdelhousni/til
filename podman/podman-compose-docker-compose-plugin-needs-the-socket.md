# `podman compose` fails because it handed the job to docker-compose, which needs the Podman socket

*Compose* starts a set of containers described in a `compose.yaml` file. Take this one:

```yaml
services:
  web:
    image: docker.io/library/nginx:latest
    ports:
      - "8080:80"
```

`podman compose up -d` can fail with an error about not reaching the Docker daemon, and the message names `/usr/libexec/docker/cli-plugins/docker-compose`.

## Why docker-compose ran

`podman compose` doesn't implement Compose itself. It's a wrapper that runs an external *provider*: either `docker-compose` (Docker's Compose v2 plugin) or `podman-compose` (a Python reimplementation that calls the `podman` command). When both are installed, it prefers `docker-compose`.

`docker-compose` doesn't call `podman`. It talks to the *Docker API*, an HTTP API served on a Unix socket. Docker's daemon always serves it. Podman has no daemon, so it serves the same API only through a separate service, `podman.socket`, which is off until you enable it. For a *rootless* Podman (run as your own user, see [Root vs rootless Podman](root-vs-rootless-rhel10-ubuntu2604.md)), that socket is `/run/user/<uid>/podman/podman.sock`, for example `/run/user/1000/podman/podman.sock`. No socket, nothing for docker-compose to connect to.

## Fix 1: start the user socket

```sh
systemctl --user enable --now podman.socket
systemctl --user status podman.socket
ls -l /run/user/1000/podman/podman.sock
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
podman compose up -d
```

- `systemctl --user` manages your own systemd services, not the system's.
- `DOCKER_HOST` tells Docker API clients, docker-compose included, which socket to use. `$XDG_RUNTIME_DIR` is your per-user runtime directory, `/run/user/<uid>`.
- To keep the export, add it to your shell's startup file (`~/.bashrc` or `~/.zshrc`).
- User services stop when you log out. To keep the socket across logout and reboots, run `loginctl enable-linger $USER` (*lingering* lets your user services run without an open session).
- Without systemd, start the API by hand and point `DOCKER_HOST` at it:

  ```sh
  podman system service --time=0 unix:///tmp/podman.sock &
  export DOCKER_HOST=unix:///tmp/podman.sock
  ```

## Fix 2: use podman-compose and skip the socket

Install it (`dnf install podman-compose`; on RHEL it comes from EPEL), then pick it as the provider in `~/.config/containers/containers.conf`:

```toml
[engine]
compose_providers = ["/usr/bin/podman-compose"]
compose_warning_logs = false
```

`compose_warning_logs = false` hides the banner `podman compose` prints about running an external provider. To hide only that banner without changing the provider, `export PODMAN_COMPOSE_WARNING_LOGS=false`.

## If it still fails

- **Rootful and rootless mixed**: if you once started the socket with `sudo`, disable the root one (`sudo systemctl disable --now podman.socket`) so the two don't conflict.
- **SELinux**: if `getenforce` prints `Enforcing`, `sudo journalctl -t audit` shows whether it blocks the socket.
- **Unit not found**: if `systemctl --user status podman.socket` says the unit doesn't exist, install the full `podman` package.
- **Image pull**: once the socket works, `podman compose up -d` pulls `nginx` from Docker Hub, and `curl localhost:8080` returns the nginx welcome page.

## Is `docker` real Docker?

The `podman-docker` package installs a `docker` command that just runs `podman`. To see which one you have, and where Podman's API socket is:

```sh
type docker
podman info --format '{{.Host.RemoteSocket.Path}}'
```
