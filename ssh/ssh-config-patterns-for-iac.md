# Useful ~/.ssh/config patterns for IaC-provisioned hosts

Plain default SSH behavior assumes a small, stable set of hosts you connect to by hand. IaC (Terraform/OpenTofu, Ansible) breaks that assumption constantly: hosts get created and destroyed, the same private IP gets reused by a completely different VM a week later, and half the fleet sits behind a bastion. A few `~/.ssh/config` options exist specifically for this.

## The ephemeral-host-key problem

Two bad defaults show up in copy-pasted configs:

- `StrictHostKeyChecking yes` refuses to connect to any host it hasn't seen before — unworkable when Terraform hands you a brand-new IP every run.
- `StrictHostKeyChecking no` accepts *anything*, including a genuinely changed key on a host that's been MITM'd, silently defeating the check entirely.

`StrictHostKeyChecking accept-new` is the middle ground built for exactly this: it auto-accepts a host key it has never seen, but still refuses a connection if a *known* host's key changes. New IaC-provisioned host → seamless first connection. Existing host with a suddenly different key → still stops you, per [the OpenSSH `ssh_config` manual](https://man.openbsd.org/ssh_config.5#StrictHostKeyChecking).

```
Host *.lab.internal
    StrictHostKeyChecking accept-new
    UserKnownHostsFile ~/.ssh/known_hosts.d/lab.known_hosts
```

The second line matters as much as the first. When a destroyed-and-recreated VM gets the same IP a different host used last month, your permanent `~/.ssh/known_hosts` still has *that* host's key on file — `accept-new` won't save you there, because from ssh's point of view the key genuinely changed. Pointing `UserKnownHostsFile` at a separate, per-environment file means wiping that one file (or letting it get rebuilt every cycle) doesn't touch the known-hosts entries for anything that isn't ephemeral.

## ProxyJump for hosts behind a bastion

```
Host bastion
    HostName bastion.example.com
    User ops

Host 10.0.1.*
    ProxyJump bastion
    User ops
```

`ProxyJump` makes ssh open a connection to `bastion` first, then tunnel the real connection to the target through it — one config block instead of a hand-rolled `ssh -J` on every invocation, and it also makes `scp`, `rsync -e ssh`, and Ansible's own ssh connections go through the bastion automatically, since they all read this same file.

## Reusing connections: ControlMaster + ControlPersist

```
Host *.lab.internal
    ControlMaster auto
    ControlPath ~/.ssh/control/%r@%h:%p
    ControlPersist 10m
```

The first connection to a host opens a real TCP+SSH handshake and keeps it alive in the background for 10 minutes after you disconnect; every connection after that reuses that same socket instead of renegotiating SSH from scratch. Ansible cares enough about this that it's not just a tip — [`ansible-core`'s own `ssh` connection plugin](https://github.com/ansible/ansible/blob/devel/lib/ansible/plugins/connection/ssh.py) defaults `ssh_args` to `-C -o ControlMaster=auto -o ControlPersist=60s`, baking the same reuse into every playbook run whether or not `~/.ssh/config` says anything. Setting it here too gets you the identical speedup for everything *else* that shells out to `ssh` against the same fleet — a plain manual `ssh`, `scp`, `rsync -e ssh`, `git` over an `ssh://` remote — and lets you push the persistence window past Ansible's 60-second default for a long series of ad hoc commands.

## Include: per-environment config Terraform/Ansible can own

```
# top of ~/.ssh/config
Include ~/.ssh/config.d/*.conf

Host *
    ForwardAgent no
```

`Include` pulls in every matching file, expanded and processed in lexical order, with relative filenames resolved against `~/.ssh`. That makes it a clean handoff point: a `terraform output` or an Ansible inventory-generation step writes `~/.ssh/config.d/staging.conf` for one environment without ever touching the file you edit by hand — tear an environment down, delete its one generated file, done. The one rule that matters: for any option, **the first match wins**, so `Include` needs to come before a catch-all `Host *` block, not after it — a value already set by an earlier block is never overwritten by a later one.

## IdentitiesOnly, so automation doesn't get locked out

```
Host *.lab.internal
    IdentityFile ~/.ssh/id_lab_ed25519
    IdentitiesOnly yes
```

A dev workstation's `ssh-agent` often ends up holding a handful of keys for different systems. Without `IdentitiesOnly yes`, ssh offers *all* of them to the server before falling back to `IdentityFile`, and a hardened `sshd` with a low `MaxAuthTries` can reject the connection for too many failed attempts before it ever gets to the one key that would've worked. Pinning the exact key for automation-facing hosts makes the connection deterministic instead of order-of-keys-in-agent-dependent.

## Ansible layers its own SSH settings on top

Ansible's default connection plugin shells out to the system `ssh` binary, so everything above still applies underneath — but [`ansible-core`'s `ssh` connection plugin](https://github.com/ansible/ansible/blob/devel/lib/ansible/plugins/connection/ssh.py) also has its own settings, each independently useful:

- **`host_key_checking`** (default `True`) — Ansible's own layer on top of `StrictHostKeyChecking`. Turning this off is the equivalent of `StrictHostKeyChecking no` for every play, with the same downside; prefer fixing it at the `~/.ssh/config` level with `accept-new` as above rather than disabling it Ansible-wide.
- **`control_path_dir`** (default `~/.ansible/cp`) — Ansible keeps its own `ControlPersist` sockets separate from anything in `~/.ssh/config`. This exists partly to dodge a classic failure: a raw `%h-%p-%r` control path can exceed the ~104-byte limit on a Unix domain socket path once the hostname is long enough, and Ansible has auto-hashed the generated path since version 2.3 specifically to avoid it — a hand-written `ControlPath` template doesn't get that protection for free.
- **`ssh_transfer_method`** (default `smart`, tries sftp then scp then a piped `dd`) — worth knowing because OpenSSH 9.0 deprecated the legacy `scp` protocol; if `smart` ends up falling back to `scp` against a newer OpenSSH server, it needs `scp_extra_args="-O"` to keep working.
- **`pipelining`** (default `False`) — reduces the number of SSH operations per module execution, but per Ansible's own config docs it's disabled by default because it "conflicts with privilege escalation (become)" unless `requiretty` is disabled in `/etc/sudoers` on every managed host first.
- **`reconnection_retries`** (default `0`) — only retries when SSH itself returns exit code 255; any other exit code means the remote command ran and failed, which retrying won't fix.

## The four places to set an Ansible SSH setting, and which one wins

Every setting above can be set as an `ansible.cfg` key, an environment variable, an inventory/host variable, or (for a couple of them) a command-line flag — and which one wins if more than one is set is fixed and, in one place, genuinely counter-intuitive.

```ini
# ansible.cfg
[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
control_path_dir = ~/.ansible/cp
pipelining = True
```

```sh
# environment variable
export ANSIBLE_SSH_ARGS="-o ControlMaster=auto -o ControlPersist=60s"
```

```yaml
# group_vars/lab.yml — inventory variable
ansible_ssh_common_args: "-o ProxyJump=bastion"
ansible_user: ops
```

Per [Ansible's own precedence documentation](https://docs.ansible.com/projects/ansible/latest/reference_appendices/general_precedence.html), the four categories rank, lowest to highest: **configuration settings** (`ansible.cfg`, with an environment variable outranking a same-named `ansible.cfg` entry) → **command-line options** → **playbook keywords** → **variables** (inventory, `group_vars`/`host_vars`, `-e`). The surprising part: an inventory variable like `ansible_ssh_common_args` set on a single host **outranks a `--ssh-common-args` flag passed on the command line** — the flag only overrides `ansible.cfg`, nothing set as a variable. Debugging "why is my `--ssh-common-args` being ignored on this one host" almost always ends at a `group_vars`/`host_vars` file setting the same thing.
