# Connection variables: ansible_host, ansible_port, ansible_user and ansible_connection, with ssh, docker and local

Fourth entry in the Ansible inventory from scratch series. The inventory so far, from [item 1](inventory-hosts-groups-all-ungrouped.md) to [item 3](inventory-ini-or-yaml-hosts-file.md), named hosts and groups and connected to all of them on the local machine. This entry reaches three hosts three different ways, and looks at the four variables that decide how: `ansible_connection`, `ansible_host`, `ansible_port` and `ansible_user`. Everything below ran with ansible-core 2.21.4 and community.docker 5.3.0.

## Three hosts, three connection plugins

A *connection plugin* is the part of Ansible that carries tasks to a host and runs them there. `ansible_connection` picks it, per host, and defaults to `ssh`:
- **`ssh`** logs in over SSH, the usual way to reach a server.
- **`community.docker.docker`**, from the community.docker *collection* (a package of extra plugins and modules, installed with `ansible-galaxy`), runs commands inside a *container*, an isolated process with its own filesystem, through Docker, with no SSH at all.
- **`local`** runs on the *controller*, the machine running `ansible-playbook`.

The example gave each host its settings in `host_vars/<host>/ansible.yml`, item 2's layout for one host, and kept the hosts file free of variables:

```yaml
# host_vars/db1/ansible.yml
ansible_connection: ssh
ansible_host: 127.0.0.1
ansible_port: 2222
ansible_user: dbadmin

# host_vars/app1/ansible.yml
ansible_connection: community.docker.docker
ansible_host: inv04-app1
ansible_user: appuser

# host_vars/jump1/ansible.yml
ansible_connection: local
```

db1 was an SSH server in a container, published on the controller's port 2222; app1 a second container, named `inv04-app1`. A playbook gathered, from inside each host, the user it ran as and the machine's name:

```
app1:   community.docker.docker  →  appuser on app1-container
db1:    ssh                      →  dbadmin on db1-container
jump1:  local                    →  the controller's own user, on the controller
```

## The same variable means something different per plugin

Each connection plugin maps these variables to options of its own, and its documentation says what they mean:

| Variable | `ssh` | `community.docker.docker` | `local` |
|---|---|---|---|
| `ansible_host` | the name or address to connect to | the container's name | not used |
| `ansible_port` | the SSH port | not used | not used |
| `ansible_user` | the user to log in as | the user to run as inside the container | ignored |

- **`ansible_host` defaults to the host's inventory name** in both `ssh` and `docker`. The name in the hosts file is a label; `ansible_host` is where the connection goes, so the inventory can say `db1` while SSH connects to `127.0.0.1`.
- **`ansible_port` has no default in Ansible.** Unset, the `ssh` plugin passes no port, and SSH uses its own default, 22, or what `~/.ssh/config` says for that host.
- **`local` ignores `ansible_user`.** Its documentation says so: *"The remote user is ignored, the user with which the ansible CLI was executed is used instead."* With `-e ansible_user=nobody`, `id -un` on jump1 still printed the controller's user. Running a task as another user is the job of `become`, Ansible's switch to another user once connected (with sudo or su), not the connection's.

The older names, `ansible_ssh_host`, `ansible_ssh_port` and `ansible_ssh_user`, still work with `ssh`, and `ansible_docker_host` and `ansible_docker_user` with `docker`; the plugins' documentation lists them next to the generic ones.

## When ansible_host is missing

The example left `ansible_host` at its default, the inventory name, for each container host:
- **db1 over SSH** failed clearly: *"Could not resolve hostname db1: Name or service not known"*, and the host was marked unreachable.
- **app1 through Docker** failed misleadingly: *"Failed to create temporary directory. In some cases, you may have been able to authenticate and did not have permissions on the target directory."* There was no container called `app1`, and nothing said so; even at `-vvv`, the only clue was the command Ansible ran, `docker exec -u appuser -i app1 …`, with the container name it tried.

So when a docker host is unreachable with a permissions message, check `ansible_host` against `docker ps` first.

## In short

- **`ansible_connection`** picks the plugin per host; `ssh` if unset.
- **`ansible_host`** is where to connect, the inventory name if unset; for docker, a container name.
- **`ansible_port` and `ansible_user`** only mean something to plugins that use them; `local` ignores both.
- **Put them in `host_vars/<host>/ansible.yml`**, or in `group_vars/<group>/ansible.yml` when a whole group connects the same way.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/04-connection-variables), holds this inventory and the image behind db1 and app1. `run.sh` needs Docker and an SSH client: it starts both containers, generates a key pair for the run, runs `whoami.yml`, which writes where each connection landed to its `out/` directory, then repeats the three mistakes above. Its CI runs it on every push and compares the output with the expected one.

## Sources

- ansible-core 2.21.4: the documentation of `plugins/connection/ssh.py` (`host`, `port`, `remote_user` and their variables) and `plugins/connection/local.py` (the ignored remote user).
- [community.docker](https://github.com/ansible-collections/community.docker) 5.3.0: the documentation of `plugins/connection/docker.py` (`remote_addr`, the container's name, and `remote_user`).
- Every result above came from ansible-core 2.21.4 and community.docker 5.3.0 on 2026-10-03, with Docker 29.6.2 and containers from `python:3.12-slim`, on the local machine.
