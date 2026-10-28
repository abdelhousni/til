# Reuse one ssh-agent across shells with keychain

`ssh-agent` is a background process that holds your decrypted private SSH keys in memory, so you type a key's passphrase once (with `ssh-add`) instead of on every `ssh`, `git push` or Ansible run. Programs find the agent through two environment variables: `SSH_AUTH_SOCK` (the path of the agent's socket) and `SSH_AGENT_PID` (its process ID).

The catch is that those variables live only in the shell that started the agent. Open a second terminal, or log in again over SSH, and it knows nothing about the first agent: you either start another one and type the passphrase again, or end up with a pile of orphaned agents.

[keychain](https://github.com/funtoo/keychain) (no relation to the macOS Keychain) is a small shell script that fixes this. On each run it looks for an agent it already started; if there is one, it reuses it, and if not, it starts one. It then loads the keys you name, asking for passphrases only for keys the agent doesn't hold yet.

## Install and hook into your shell

```sh
sudo apt install keychain      # Debian/Ubuntu; dnf install keychain on Fedora
```

Add one line to `~/.bashrc` (or `~/.zshrc`):

```sh
eval "$(keychain --eval --quiet id_ed25519)"
```

- `id_ed25519` is the key file name, looked up in `~/.ssh/`. List several to load several.
- `--eval` prints the `export` commands for `SSH_AUTH_SOCK` and `SSH_AGENT_PID`, and `eval` runs them in the current shell.
- `--quiet` hides keychain's status messages, but not the passphrase prompt.

What `--eval` prints:

```
SSH_AUTH_SOCK=/tmp/ssh-eC9qAKnEukqo/agent.1232; export SSH_AUTH_SOCK;
SSH_AGENT_PID=1233; export SSH_AGENT_PID;
```

keychain also writes the same lines to `~/.keychain/<hostname>-sh` (plus `-csh` and `-fish` variants), which is how the next shell finds the agent. A cron job or script can pick it up the same way:

```sh
. ~/.keychain/"$(hostname)"-sh
```

## Check and manage it

The first shell asks for the passphrase. Every later shell prints the same `SSH_AUTH_SOCK`, and keychain reports the key as already loaded (`Known ssh key: ~/.ssh/id_ed25519`), without asking.

```sh
ssh-add -l             # keys the agent holds, by fingerprint
keychain --list        # same, through keychain
keychain --clear       # remove all keys from the agent; the agent keeps running
keychain -k all        # kill the agent(s)
```

`--clear` can also go in the `.bashrc` line itself (`keychain --eval --quiet --clear id_ed25519`). Then every new login asks for the passphrase again, so someone who gets into your account without it can't use keys an earlier session left in memory, while a cron job that sources `~/.keychain/<hostname>-sh` still finds the agent.

The agent lasts until it is killed or the machine reboots; after a reboot, the first shell asks for the passphrase again.
