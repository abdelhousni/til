# Deploying a Podman Quadlet stack on RHEL9 with linux-system-roles

Earlier I [hand-wrote Quadlet files for Caddy + PHP-FPM](../podman/caddy-php-fpm-automatic-https.md) directly on the host. The `linux-system-roles.podman` role turns that into something declarative: instead of writing `.container`/`.network` unit files as text, you describe them as nested YAML matching each unit's own `[Section]` layout, and the role generates and manages the actual files. Paired with `linux-system-roles.network` for the host's own networking, one playbook takes a bare RHEL9 box to a running container stack.

## Host networking first

```yaml
- name: Configure the host's network
  hosts: rhel9_hosts
  roles:
    - linux-system-roles.network
  vars:
    network_connections:
      - name: eth0
        type: ethernet
        ip:
          dhcp4: false
          address:
            - 192.168.20.51/24
          gateway4: 192.168.20.1
          dns:
            - 192.168.20.1
```

A stable, known IP before anything gets deployed on top of it — ordinary NetworkManager connection profile management, nothing container-specific yet.

## The Quadlet stack: Caddy + Adminer + PHP

```yaml
- name: Deploy the container stack
  hosts: rhel9_hosts
  roles:
    - linux-system-roles.podman
  vars:
    podman_quadlet_specs:
      - name: appnet
        type: network
        Network: {}

      - name: php
        type: container
        Install:
          WantedBy: default.target
        Container:
          Image: docker.io/library/php:8.3-fpm-alpine
          ContainerName: php
          Network: appnet.network
          Volume: /srv/app:/srv:ro

      - name: adminer
        type: container
        Install:
          WantedBy: default.target
        Container:
          Image: docker.io/library/adminer:latest
          ContainerName: adminer
          Network: appnet.network

      - name: caddy
        type: container
        Install:
          WantedBy: default.target
        Container:
          Image: docker.io/library/caddy:2-alpine
          ContainerName: caddy
          Network: appnet.network
          PublishPort: "80:80"
          Volume: /srv/Caddyfile:/etc/caddy/Caddyfile:ro
          Volume: /srv/app:/srv:ro
```

Every piece here maps directly onto the raw Quadlet syntax from the manual version — `Network: appnet.network` is exactly the `Network=appnet.network` line from a hand-written `.container` file, just expressed as a YAML key. `type: network` with an empty `Network: {}` produces the equivalent of the plain `podman network create` step from before.

## Ordering isn't cosmetic

The spec list order **is** the dependency order the role applies things in — `appnet` has to come before anything that references `Network: appnet.network`, exactly like a hand-written `.network` file has to exist before a `.container` file that points at it. Get the order backwards and the role will try to wire a container to a network unit that doesn't exist yet on that same run.

## Why bother with this over raw Quadlet files

Three things the manual version doesn't give you for free: `restarts`/`restarts_on` on a quadlet spec to automatically restart a service when a dependency file changes (a mounted config, a secret) without touching the unit file itself; `podman_secrets` for managing Podman secrets from the same variable structure; and ordinary Ansible idempotency — rerunning the playbook against a host that already has this stack just confirms nothing drifted, the same guarantee any other Ansible-managed config gets.
