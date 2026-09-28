# A user's PATH on NixOS: declare packages, and know which settings reach services

The usual advice on NixOS is right. Declare packages instead of adding `/nix/store/...` directories to `PATH`, and add your own script directory through Home Manager or a shell profile. The details matter, though: some of those settings only reach certain shells, and none of them reach systemd user services.

Checked in a NixOS 26.05 VM with Home Manager `release-26.05` as a NixOS module. It had three users:
- `alice`: bash, with Home Manager installing packages but not managing her shell;
- `carol`: Home Manager managing bash;
- `bob`: zsh.

`alice` also had a lingering systemd user manager.

## What a login shell already has

```text
$ su -l alice -c 'echo $PATH'
/run/wrappers/bin:/home/alice/.nix-profile/bin:/nix/profile/bin:/home/alice/.local/state/nix/profile/bin:/etc/profiles/per-user/alice/bin:/nix/var/nix/profiles/default/bin:/run/current-system/sw/bin
```

Apart from `/run/wrappers/bin`, every entry is a profile's `bin`:
- `~/.nix-profile` and `~/.local/state/nix/profile`: packages installed with `nix-env` or `nix profile`;
- `/etc/profiles/per-user/alice`: packages declared for this user;
- the default profile, and the system itself.

So a package only has to land in one of those profiles to be on `PATH`.

## Packages for one user

Either in `configuration.nix`:

```nix
users.users.alice.packages = with pkgs; [ ripgrep ];
```

or with Home Manager, where `useUserPackages = true` puts them in the same per-user profile:

```nix
home-manager.users.alice = { pkgs, ... }: {
  home.packages = with pkgs; [ jq ];
};
```

Both are applied by `sudo nixos-rebuild switch`. `home-manager switch` is for standalone Home Manager; the NixOS module installs no `home-manager` command. In the VM, `command -v jq rg` answered `/etc/profiles/per-user/alice/bin/jq` and `.../rg`.

## A directory of your own scripts

Pick one of these, depending on who it's for and which shells must see it.

- **For every user, every shell**: `environment.localBinInPath = true;` adds `~/.local/bin`, and `environment.homeBinInPath = true;` adds `~/bin`. Both are off by default. They go into `/etc/set-environment`, which NixOS shells source.
- **`home.sessionPath`**, only if Home Manager manages the shell. With `home.sessionPath = [ "$HOME/hm-bin" ]` on both users, `alice`'s `PATH` didn't change. `carol`'s, with `programs.bash.enable = true` in her Home Manager config, started with `/home/carol/hm-bin`. Otherwise, source `hm-session-vars.sh` yourself, as described in [the Home Manager entry](home-manager-nixos-module.md).
- **A shell profile**: `export PATH="$HOME/.local/bin:$PATH"` in `~/.bash_profile` for bash, or `~/.zprofile` for zsh. Both put `~/.local/bin` first for a login shell, and an interactive shell started from that login inherited it. Bash reads only the first of `~/.bash_profile`, `~/.bash_login` and `~/.profile` that exists.
- **Fish**: `fish_add_path ~/.local/bin` saves the directory in a universal variable, in `~/.config/fish/fish_variables`, which later shells load without any config line. That's state outside your config files. For a declarative setup, put `fish_add_path -g ~/.local/bin` in `config.fish` instead (tested with fish 4.7.1).

## systemd user services read none of it

The user manager gets its `PATH` from a file NixOS generates from the same profile list:

```text
$ cat /etc/environment.d/50-systemd-path.conf
PATH="/run/wrappers/bin:$HOME/.nix-profile/bin:${XDG_STATE_HOME}/nix/profile/bin:$HOME/.local/state/nix/profile/bin:/etc/profiles/per-user/$USER/bin:/nix/var/nix/profiles/default/bin:/run/current-system/sw/bin"
```

Declared packages are there. `~/.local/bin`, `home.sessionPath` and anything from `~/.bash_profile` are not. To give one service its own `PATH`:

```nix
# NixOS module
systemd.user.services.my-job = {
  path = [ pkgs.yq-go ];
  serviceConfig.Type = "oneshot";
  script = "yq --version";
};
```

```nix
# Home Manager: there is no path option; set the variable
systemd.user.services.my-job = {
  Service.Environment = [ "PATH=${lib.makeBinPath [ pkgs.yq-go pkgs.coreutils ]}" ];
  # ...
};
```

Both **replace** the default `PATH` rather than extending it. The NixOS `path` option also adds coreutils, findutils, grep, sed and systemd (`enableDefaultPath`). The Home Manager version gets exactly the packages listed. For a single command, `${pkgs.jq}/bin/jq` in `ExecStart` needs no `PATH` at all.

**`Service.Path` is not a thing.** Home Manager passes unknown keys through, so this builds:

```nix
Service.Path = [ pkgs.jq pkgs.coreutils ];
```

systemd then ignores it:

```text
pasted-job.service:3: Unknown key 'Path' in section [Service], ignoring.
```

In the VM the service still found `jq`, through the per-user profile, so it worked by accident. It would break once the package leaves that profile.

## Rule of thumb

| Need | Mechanism | Reaches user services |
|---|---|---|
| CLI tools for one user | `users.users.<name>.packages` or `home.packages` | Yes, through the per-user profile |
| Tools for everyone | `environment.systemPackages` | Yes |
| `~/.local/bin` for everyone | `environment.localBinInPath` | No |
| Your own script directory | `home.sessionPath` (Home Manager-managed shell), or `~/.bash_profile` / `~/.zprofile` | No |
| A command in a user service | NixOS `path`, Home Manager `Environment=PATH=`, or an absolute store path | That service only |
| A temporary tool | `nix shell nixpkgs#jq`, or a project's `nix develop` | No |

## Sources

- nixpkgs `nixos-26.05`:
  - `nixos/modules/config/shells-environment.nix` (`localBinInPath`, `homeBinInPath`, `/etc/set-environment`);
  - `config/users-groups.nix` (the profile list) and `config/system-environment.nix` (`environment.d/50-systemd-path.conf`);
  - `nixos/lib/systemd-lib.nix` and `systemd-unit-options.nix` (`path`, `enableDefaultPath`).
- Home Manager `release-26.05`: `modules/home-environment.nix` (`home.sessionPath`) and `modules/systemd.nix`.
- [environment.d(5)](https://www.freedesktop.org/software/systemd/man/latest/environment.d.html), and the fish documentation for [fish_add_path](https://fishshell.com/docs/current/cmds/fish_add_path.html).
