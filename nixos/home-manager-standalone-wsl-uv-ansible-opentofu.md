# A minimal IaC toolbox on WSL2 with standalone Home Manager: Nix owns Python and OpenTofu, uv owns Ansible

WSL2 (*Windows Subsystem for Linux*) runs a real Linux in a lightweight virtual machine on Windows. This entry builds a small admin and IaC (*infrastructure as code*) toolbox inside it, from one Git repository: a system Python 3, [OpenTofu](../terraform/what-is-terraform-opentofu-and-how-it-works.md), `uv`, and Ansible with `ansible-lint`. **Home Manager** installs it. It's a tool that declares a user's packages and dotfiles in the Nix language (see [the NixOS-module entry](home-manager-nixos-module.md) for how it works inside `nixos-rebuild`). **`uv`** is a fast Python package and project manager that replaces `pip`, `venv`, `pipx` and `pyenv`.

The same flake then drives a [`.devcontainer`](#the-same-toolbox-as-a-devcontainer), for projects that should carry their own environment. Built and activated with Home Manager `release-26.05`, nixpkgs `nixos-26.05`, `uv` 0.11 and `ansible-core` 2.20 on x86_64 Linux. WSL itself wasn't available here: the activation ran in a plain Linux container with Nix installed, in a scratch home directory. The one NixOS-only failure, below, is from the documentation and wasn't reproduced.

## Why standalone, and why two tools

[The other entry](home-manager-nixos-module.md) uses Home Manager *as a NixOS module*, which only works on a NixOS machine. **Standalone** Home Manager is a `home-manager` command that manages one user's home and needs only Nix. So the same file works on [NixOS-WSL](nixos-wsl-admin-runbook.md) and on an Ubuntu or Debian WSL distribution with Nix installed. That is handy when work gives you Ubuntu and the homelab runs NixOS.

The split is by who updates what:

| Tool | Installed by | Why |
|---|---|---|
| Python 3, OpenTofu, Git, `uv` | Home Manager (Nix) | Pinned by `flake.lock` (explained below), rolled back with a *generation*, one saved state of the profile |
| `ansible-core`, `ansible-lint` | `uv tool install` | They're Python packages, and Ansible releases move faster than nixpkgs |
| Project libraries (`jinja2`, `netaddr`…) | `uv add` in each project | Per-project, locked in `uv.lock` |

## The flake

A *flake* is a Git repository with a `flake.nix` that declares its inputs and outputs, and a `flake.lock` that pins every input to a commit. Both Home Manager and nixpkgs sit on the same release:

```nix
{
  inputs = {
    nixpkgs.url = "git+https://github.com/NixOS/nixpkgs?ref=nixos-26.05&shallow=1";
    home-manager = {
      url = "git+https://github.com/nix-community/home-manager?ref=release-26.05&shallow=1";
      inputs.nixpkgs.follows = "nixpkgs";   # one nixpkgs, not two
    };
  };

  outputs = { nixpkgs, home-manager, ... }: {
    homeConfigurations."nixos@wsl" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [ ./home.nix ];
    };
  };
}
```

## `home.nix`

```nix
{ config, lib, pkgs, ... }:
{
  home.username = "nixos";            # `whoami` inside WSL
  home.homeDirectory = "/home/nixos";
  home.stateVersion = "26.05";        # set once, leave it
  home.sessionPath = [ "${config.home.homeDirectory}/.local/bin" ];  # where uv puts tools

  home.packages = with pkgs; [ python3 opentofu git ];

  programs.uv = {
    enable = true;
    settings = {
      python-downloads = "never";       # never fetch a Python of its own
      python-preference = "only-system"; # use the one on PATH: Nix's
    };
  };

  # Ansible from PyPI, after the packages (and so uv) are in the profile.
  home.activation.uvTools = lib.hm.dag.entryAfter [ "installPackages" ] ''
    export PATH="${config.home.profileDirectory}/bin:$PATH"
    run uv tool install "ansible-core==2.20.*" --with-executables-from ansible-lint
  '';
}
```

`programs.uv.settings` writes `~/.config/uv/uv.toml`. I confirmed the file holds exactly those two lines. `home.activation` entries run as shell during `home-manager switch`; `entryAfter [ "installPackages" ]` orders it after the profile is built, and `run` skips the command on a dry run.

## Activate it

First time, with no `home-manager` command yet:

```sh
nix run home-manager/release-26.05 -- switch --flake .#nixos@wsl
```

After that, `home-manager switch --flake .#nixos@wsl`. The result in my test:

```text
$ tofu version        # OpenTofu v1.11.14
$ uv tool list
ansible-core v2.20.10
- ansible
- ansible-config
- ansible-lint
- ansible-playbook
...
$ ansible-lint --version
ansible-lint 26.9.0 using ansible-core:2.20.10 ...
```

`ansible-core` and `ansible-lint` share one environment, so the linter always runs against the Ansible you run.

## Pitfalls I hit

- **`uv tool install pkg --with other` hides `other`'s commands.** `--with` only adds a library to the tool's environment. To also get its executables, use `--with-executables-from ansible-lint`. My first run installed the ten `ansible-*` commands and no `ansible-lint`.
- **Re-running it doesn't reinstall.** uv answers ``ansible-core==2.20.* is already installed`` in milliseconds, so the activation step costs nothing on later switches. It also means changing the spec (or adding `--with-executables-from`) needs `--force` to take effect, because the same spec is a no-op.
- **`uv` picks the Python it finds, and the project follows.** With `only-system`, `uv init` wrote `requires-python = ">=3.13"` after Nix's Python 3.13, and `uv python pin 3.12` then failed: *The requested Python version `3.12` is incompatible with the project `requires-python` value*. For another minor version, add `python312` to `home.packages` and use `uv venv --python 3.12`, or edit `requires-python` first.
- **The tool environments point into `/nix/store`.** `~/.local/share/uv/tools/ansible-core/bin/python` is a symlink to the Nix Python. After a nixpkgs bump and a garbage collection removes the old store path, the symlink dangles and `ansible` stops working. Run `uv tool upgrade --reinstall ansible-core` (not run here) to rebuild it on the new Python.
- **`~/.local/bin` has to be on `PATH`.** uv warns about it, and `home.sessionPath` fixes it for shells Home Manager manages. In a Bash or Zsh you configured yourself, source `hm-session-vars.sh` as [the other entry](home-manager-nixos-module.md#session-variables-need-a-managed-shell) explains.

## Why `python-downloads = "never"` matters on NixOS

By default uv downloads prebuilt Python builds when none matches. NixOS has no standard dynamic loader at `/lib64/ld-linux-x86-64.so.2`, so these binaries refuse to start with a *Could not start dynamically linked executable* message from NixOS's `stub-ld`. I did not reproduce that here, since the container isn't NixOS. Telling uv to only use the Nix-provided Python avoids the problem. The cost: Python versions come from nixpkgs, not from uv. On an Ubuntu WSL distribution, the setting is optional, but it keeps both machines behaving the same.

## A project on top

```sh
mkdir lab && cd lab
uv init --no-workspace
uv add netaddr jinja2         # recorded in pyproject.toml and locked in uv.lock
uv run python -c "import jinja2"
```

Commit `pyproject.toml` and `uv.lock`; `.venv/` stays out of Git. A clone anywhere does `uv sync`. In my test `uv run` used `.venv/bin/python3` created from the Nix Python.

## The same toolbox as a `.devcontainer`

A *Dev Container* is a container that VS Code (through the Dev Containers extension) or the `@devcontainers/cli` opens a project in. The editor server and every tool run inside it, and the configuration is a `devcontainer.json` file in the repository. [The ADT Dev Container entry](../ansible/ansible-dev-container-with-adt.md) uses a ready-made Ansible image. Here the image is a plain Ubuntu one, and the toolbox above is installed into it by the same Home Manager flake, so the container and the WSL distribution can't drift apart. On WSL2 the container engine is Docker Desktop with its WSL 2 backend, or Docker Engine or Podman inside the distribution ([Podman setting](../ansible/ansible-dev-container-with-adt.md#with-podman-instead-of-docker)).

Three files, under `.devcontainer/`:

```text
.devcontainer/
├── devcontainer.json
└── home/
    ├── flake.nix      # the flake from above, with username "vscode"
    ├── flake.lock     # created by the first run; commit it
    └── home.nix       # the home.nix from above, with home.username = "vscode"
```

```json
{
  "name": "iac-toolbox",
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu-24.04",
  "features": {
    "ghcr.io/devcontainers/features/nix:1": {
      "extraNixConfig": "experimental-features = nix-command flakes"
    }
  },
  "remoteUser": "vscode",
  "postCreateCommand": "USER=$(id -un) nix run \"git+https://github.com/nix-community/home-manager?ref=release-26.05&shallow=1\" -- switch --flake .devcontainer/home#vscode -b backup",
  "customizations": {
    "vscode": {
      "extensions": ["redhat.ansible", "ms-python.python", "charliermarsh.ruff", "opentofu.vscode-opentofu"]
    }
  }
}
```

- A **Dev Container Feature** is a reusable install step. `ghcr.io/devcontainers/features/nix` installs Nix, and `extraNixConfig` turns on flakes.
- `postCreateCommand` runs once, after the container is created, as `remoteUser`. It does the first Home Manager switch, with `-b backup` renaming any file in the way, as [the NixOS-module entry](home-manager-nixos-module.md#the-file-thats-in-the-way) explains.

I ran it with `@devcontainers/cli` 0.89.0 on Docker 29.8.2. After `devcontainer up`, a plain `devcontainer exec` shell found `tofu` (OpenTofu 1.11.14), `uv` 0.11.21, `ansible` 2.20.10 and `ansible-lint` on the `PATH`. The extensions list wasn't exercised, because there was no VS Code. In this sandbox I had to add the proxy's CA certificate to a copy of the base image so that the Nix feature could clone from GitHub; on a normal network the file above works as written.

Three things failed on the way, and each has an easy fix:

- **`github:` flake URLs hit the GitHub API.** `github:nix-community/home-manager/release-26.05` (and `nix run home-manager/release-26.05`, which resolves the same way) fetches from `api.github.com`, and the container got `HTTP error 403 … API rate limit exceeded`. Unauthenticated requests are limited per IP address, so a shared office or VPN address runs out fast. `git+https://github.com/...?ref=...&shallow=1` URLs, used above, clone with Git and don't count against it.
- **`USER` isn't set in `postCreateCommand`.** `home-manager` stopped with `USER: unbound variable`, the same message as in my first activation outside a login shell. Setting `USER=$(id -un)` in front of the command fixes it.
- **The workspace must belong to the container user.** With a bind-mounted folder owned by another user, Nix refused with `repository path '/workspaces/dc' is not owned by current user`, and then with `Permission denied` on `flake.lock`. On WSL2 your first user is normally UID 1000, like the image's `vscode` user, so this shouldn't happen when the repository is on the Linux filesystem. Opening a folder from `/mnt/c` is where it shows up, and it's also the slow place to work.

Home Manager in a container costs more on the first build than a ready-made image: Nix evaluates and downloads the closure (the packages and everything they depend on) once. In return, the Python, OpenTofu and `uv` versions come from the lock file, not from an image tag.

## Keep it in Git

Put `flake.nix`, `flake.lock` and `home.nix` in a repository under your WSL home (on the Linux side, not `/mnt/c`, which is much slower). `nix flake update` moves every pin, `git diff flake.lock` shows what changed, and `home-manager generations` lists the generations you can go back to.

## Sources

- Home Manager manual: [standalone installation](https://nix-community.github.io/home-manager/#sec-flakes-standalone) and [`home.activation`](https://nix-community.github.io/home-manager/options.xhtml#opt-home.activation).
- Home Manager `release-26.05`: `modules/programs/uv.nix`.
- uv documentation: [tools](https://docs.astral.sh/uv/concepts/tools/) (`--with-executables-from`) and [Python versions](https://docs.astral.sh/uv/concepts/python-versions/) (`python-downloads`, `python-preference`).
