# A minimal IaC toolbox on WSL2 with standalone Home Manager: Nix owns Python and OpenTofu, uv owns Ansible

WSL2 (*Windows Subsystem for Linux*) runs a real Linux in a lightweight virtual machine on Windows. This entry builds a small admin and IaC (*infrastructure as code*) toolbox inside it, from one Git repository: a system Python 3, [OpenTofu](../terraform/what-is-terraform-opentofu-and-how-it-works.md), `uv`, and Ansible with `ansible-lint`. **Home Manager** installs it. It's a tool that declares a user's packages and dotfiles in the Nix language (see [the NixOS-module entry](home-manager-nixos-module.md) for how it works inside `nixos-rebuild`). **`uv`** is a fast Python package and project manager that replaces `pip`, `venv`, `pipx` and `pyenv`.

Built and activated with Home Manager `release-26.05`, nixpkgs `nixos-26.05`, `uv` 0.11 and `ansible-core` 2.20 on x86_64 Linux. WSL itself wasn't available here: the activation ran in a plain Linux container with Nix installed, in a scratch home directory. The one NixOS-only failure, below, is from the documentation and wasn't reproduced.

## Why standalone, and why two tools

[The other entry](home-manager-nixos-module.md) uses Home Manager *as a NixOS module*, which only works on a NixOS machine. **Standalone** Home Manager is a `home-manager` command that manages one user's home and needs only Nix. So the same file works on [NixOS-WSL](nixos-wsl-admin-runbook.md) and on an Ubuntu or Debian WSL distribution with Nix installed. That is handy when work gives you Ubuntu and the homelab runs NixOS.

The split is by who updates what:

| Tool | Installed by | Why |
|---|---|---|
| Python 3, OpenTofu, Git, `uv` | Home Manager (Nix) | Pinned by the flake lock, rolled back with a generation |
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

Dev Containers are the other way to get a reproducible tool set, [with ADT in a container](../ansible/ansible-dev-container-with-adt.md), and the comparison of where to run it is in [the Ansible environment entry](../ansible/where-to-run-an-ansible-dev-environment.md). Home Manager is lighter: no container runtime, and the tools run directly in the WSL distribution. It reaches only your own user, and a Dev Container carries the setup to anyone who opens the repository.

## Keep it in Git

Put `flake.nix`, `flake.lock` and `home.nix` in a repository under your WSL home (on the Linux side, not `/mnt/c`, which is much slower). `nix flake update` moves every pin, `git diff flake.lock` shows what changed, and `home-manager generations` lists the generations you can go back to.

## Sources

- Home Manager manual: [standalone installation](https://nix-community.github.io/home-manager/#sec-flakes-standalone) and [`home.activation`](https://nix-community.github.io/home-manager/options.xhtml#opt-home.activation).
- Home Manager `release-26.05`: `modules/programs/uv.nix`.
- uv documentation: [tools](https://docs.astral.sh/uv/concepts/tools/) (`--with-executables-from`) and [Python versions](https://docs.astral.sh/uv/concepts/python-versions/) (`python-downloads`, `python-preference`).
