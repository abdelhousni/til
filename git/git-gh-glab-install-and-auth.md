# Installing git, gh, and glab, and the auth each one actually needs

Three separate tools, three separate installs, and — the part that isn't obvious until it bites you — three separate credential stores. `git` itself doesn't know about GitHub or GitLab; `gh` and `glab` each keep their own token; and only one of them bridges that token into plain `git push`/`git clone` for free.

## 1. Install git and set the config that actually matters

```sh
sudo dnf install git      # RHEL / Rocky / Alma / Fedora
sudo apt install git      # Debian / Ubuntu
git --version
```

Right after install, two config values are effectively required and one is worth setting deliberately:

```sh
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

Without `user.name`/`user.email`, the first `git commit` fails outright with "Please tell me who you are" — not a warning, a hard stop. `init.defaultBranch` only changes what `git init` calls the first branch of a *new local* repo; it has no effect on repos already created, and no effect on what GitHub or GitLab names the default branch for a repo created through their own UI or API.

## 2. GitHub CLI (`gh`): install, then authenticate

```sh
# RHEL/Fedora with dnf5
sudo dnf install dnf5-plugins
sudo dnf config-manager addrepo --from-repofile=https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install gh

# Debian/Ubuntu
(type -p wget >/dev/null || sudo apt install wget -y) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && wget -nv -O/tmp/githubcli.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && sudo cp /tmp/githubcli.gpg /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
     | sudo tee /etc/apt/sources.list.d/github-cli.list \
  && sudo apt update && sudo apt install gh -y
```

(RHEL/CentOS on the older DNF4 use `sudo dnf config-manager --add-repo ...` instead of `addrepo --from-repofile=...` — the flag changed between DNF4 and DNF5.)

```sh
gh auth login          # interactive: pick github.com or a GHES hostname, HTTPS or SSH, browser or token
gh auth setup-git       # <- the important one, see below
gh auth status          # confirm
```

`gh auth setup-git` configures git itself to use `gh` as a credential helper for every host you're authenticated with. After running it, plain `git clone https://github.com/...` and `git push` just work — no PAT to paste, no separate `credential.helper` to configure.

## 3. GitLab CLI (`glab`): install, then authenticate

Homebrew is GitLab's own officially-supported install path on Linux (not just macOS); Fedora also carries `glab` directly. RHEL/Rocky/Alma don't ship it in the default repos, so Homebrew or a downloaded binary from the [releases page](https://gitlab.com/gitlab-org/cli/-/releases) are the reliable options there.

```sh
brew install glab        # officially supported on Linux and macOS
sudo dnf install glab    # Fedora only
```

```sh
glab auth login                                                    # gitlab.com, interactive
glab auth login --hostname gitlab.example.com --stdin < token.txt   # self-managed, non-interactive
glab auth status
```

The personal access token needs at least the `api` and `write_repository` scopes. For a self-managed OAuth app instead of a PAT, the client ID has to be registered first: `glab config set client_id <CLIENT_ID> --host gitlab.example.com`.

## 4. The gotcha: `glab` does not do what `gh auth setup-git` does

This is the one that's easy to assume works by analogy and doesn't. `gh` bridges its stored token into git's own HTTPS auth; `glab` has no equivalent command. Its token lives in the OS keyring (or the config file, in CI) purely for `glab`'s own API calls — issues, MRs, pipelines, releases. A plain `git clone`/`git push` against `https://gitlab.com/...` never touches it: `glab`'s command list has a `docker-helper` for container-registry auth, but nothing that plugs into git's `credential.helper` for the base git protocol.

So after `glab auth login`, `git push` to a GitLab remote over HTTPS still prompts for its own credentials, separately. Two ways to actually fix that:

- **Use SSH instead** — `glab ssh-key add ~/.ssh/id_ed25519.pub` registers a key with GitLab, then clone/push over `git@gitlab.com:...` remotes, which don't need any HTTPS credential helper at all.
- **Or configure git's HTTPS credential storage yourself** — `git config --global credential.helper store` (or your OS keychain's helper), then enter the same personal access token as the password the first time git asks. It's a manual step either way; `glab` doesn't do it for you.

## Sanity-check both at once

```sh
gh auth status && glab auth status
```

If either one reports logged out, that tool's git operations for that host will fail or fall back to an interactive password prompt — worth checking before assuming a script or CI job will run non-interactively.
