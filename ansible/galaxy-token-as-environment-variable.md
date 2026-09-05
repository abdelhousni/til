# Storing an Ansible Galaxy token as an environment variable, not in ansible.cfg

`ansible-galaxy` needs a token to install from or publish to anything other than the fully public Galaxy — a private Automation Hub, a self-hosted galaxy_ng, or even the public Galaxy for publishing your own collections. The token can live directly in `ansible.cfg`, but that's exactly the kind of file that gets committed to a repo without a second thought.

## The config, minus the secret

```ini
[galaxy]
server_list = release_galaxy

[galaxy_server.release_galaxy]
url = https://galaxy.ansible.com/
```

No `token =` line at all — `ansible.cfg` stays safe to commit as-is.

## The env var that fills it in

Ansible defines a predictable naming pattern for overriding any `[galaxy_server.{id}]` setting: `ANSIBLE_GALAXY_SERVER_{ID}_{KEY}`, where `{id}` is the server's identifier from `server_list`, uppercased, and `{key}` is the config key (`token`, `username`, `password`, `url`, ...). For the `release_galaxy` server above:

```sh
export ANSIBLE_GALAXY_SERVER_RELEASE_GALAXY_TOKEN=my_token
ansible-galaxy collection install some.namespace.collection
```

Environment variables win over whatever's in `ansible.cfg`, so this composes cleanly: commit the file with everything *except* the secret, and every environment (a laptop, CI, a colleague's machine) supplies the token its own way — a local `export`, a CI/CD secret variable, a secrets manager injecting it at runtime — without anyone touching the checked-in config.

## Multiple servers, same pattern

Nothing special about having more than one — each identifier in `server_list` gets its own set of env vars:

```ini
[galaxy]
server_list = release_galaxy, my_org_hub

[galaxy_server.release_galaxy]
url = https://galaxy.ansible.com/

[galaxy_server.my_org_hub]
url = https://automation.my-org.example/
```

```sh
export ANSIBLE_GALAXY_SERVER_RELEASE_GALAXY_TOKEN=my_public_token
export ANSIBLE_GALAXY_SERVER_MY_ORG_HUB_TOKEN=my_private_hub_token
```

(Based on [oneuptime.com's writeup on Galaxy token authentication](https://oneuptime.com/blog/post/2026-02-21-how-to-use-ansible-galaxy-token-authentication/), cross-checked against the [official `server_list` docs](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_installing.html#configuring-the-ansible-galaxy-client), which spell out the exact `ANSIBLE_GALAXY_SERVER_{{ id }}_{{ key }}` pattern.)
