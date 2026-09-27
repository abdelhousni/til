# Home Manager as a NixOS module: dotfiles in the same rebuild, and the file that's in the way

[Home Manager](https://nix-community.github.io/home-manager/) does for a user's home directory what `configuration.nix` does for the system: packages, `~/.config` files and program settings, declared in Nix. It runs either standalone, with its own `home-manager switch`, or as a NixOS module, where `nixos-rebuild` builds and activates it with the rest of the machine. This entry is about the module, on one machine you administer. It was checked against Home Manager `release-26.05` (commit `a663110`) and nixpkgs `nixos-26.05`, in a VM test that boots the configuration and then deliberately breaks it.

## The short version

Add the channel as root, on the same release as your NixOS channel:

```sh
sudo nix-channel --add https://github.com/nix-community/home-manager/archive/release-26.05.tar.gz home-manager
sudo nix-channel --update
```

Then, in `configuration.nix` or a file it imports:

```nix
{ ... }:
{
  imports = [ <home-manager/nixos> ];

  home-manager = {
    useGlobalPkgs = true;           # the system's nixpkgs, not a second copy
    useUserPackages = true;         # packages in /etc/profiles/per-user/<user>
    backupFileExtension = "backup"; # see "The file that's in the way"

    users.demo = { pkgs, ... }: {
      home.stateVersion = "26.05";  # like system.stateVersion: set once, leave it
      home.packages = [ pkgs.ripgrep ];
      programs.git = {
        enable = true;
        settings.user = { name = "Demo"; email = "demo@example.invalid"; };
      };
      xdg.configFile."dar-nixos/hello.txt".text = "Managed by Home Manager.\n";
    };
  };
}
```

`sudo nixos-rebuild switch` now also writes `~demo/.config/git/config` and `~demo/.config/dar-nixos/hello.txt`, and puts `rg` on `demo`'s PATH. The user must exist in `users.users` as well; Home Manager configures homes, it doesn't create accounts.

## What `nixos-rebuild` does with it

Each user in `home-manager.users` becomes part of the system closure, plus one systemd unit, `home-manager-<user>.service`. The unit is a oneshot that runs the user's activation script **as that user**. It is wanted by `multi-user.target` and ordered **before `systemd-user-sessions.service`**, the unit that allows logins. So at boot the dotfiles are in place before anyone can log in. On `switch` the unit is restarted whenever that user's configuration changed.

Some consequences:

- **Managed files are symlinks into the Nix store.** `readlink -f ~/.config/git/config` ends in `/nix/store/...-home-manager-files/...`. Editing them in place fails, which is the point. Edit the Nix file and rebuild.
- **There is no `home-manager` command.** Nothing installs it, and `home-manager switch` isn't how this setup is applied. `nixos-rebuild` is the only entry point, for every user.
- **Rollback covers the dotfiles.** `sudo nixos-rebuild switch --rollback`, or picking an older generation at boot, brings back that generation's unit, and with it that generation's files.
- **Output goes to the journal.** When a rebuild doesn't produce the files you expect, the manual's advice is `systemctl status home-manager-demo.service`, and `journalctl -u home-manager-demo.service` has the full activation log.

## `useGlobalPkgs` and `useUserPackages`

Both default to `false`. Both are set in the manual's flake example, and there's little reason to leave them off on a NixOS machine.

**`useGlobalPkgs`** makes Home Manager use the system's `pkgs`, with its overlays and `nixpkgs.config` (such as `allowUnfree`). Otherwise each user gets a private nixpkgs, configured separately through `home-manager.users.<name>.nixpkgs.*`, and imported from `<nixpkgs>` in `NIX_PATH`. The manual says the option "saves an extra Nixpkgs evaluation, adds consistency, and removes the dependency on `NIX_PATH`". That last part matters in a flake, whose pure evaluation has no `NIX_PATH`. With the option on, the per-user `nixpkgs.*` options are disabled, so overlays go on the system.

**`useUserPackages`** installs `home.packages` through `users.users.<name>.packages`. They end up in `/etc/profiles/per-user/<user>`, which NixOS already puts on that user's PATH. Without it they go to `~/.nix-profile`, and the manual notes this option "is necessary if, for example, you wish to use `nixos-rebuild build-vm`". The VM test checks that `command -v rg` answers `/etc/profiles/per-user/demo/bin/rg`, and that there's no `rg` in `~/.nix-profile`.

## The file that's in the way

Home Manager won't replace a file it doesn't own. Suppose `~/.config/git/config` existed before Home Manager did, or someone replaced the `hello.txt` symlink with a copy to edit it. The next activation stops with:

```text
Existing file '/home/demo/.config/dar-nixos/hello.txt' would be clobbered
```

It stops before changing anything, and lists three ways out:

- **`home-manager.backupFileExtension = "backup";`** renames the file to `hello.txt.backup` and links the managed one in its place.
- **`home-manager.backupCommand`** runs a command of yours on the file instead, for example moving it to the trash.
- **`force = true`** on one file option, such as `xdg.configFile."dar-nixos/hello.txt".force = true;`, overwrites that one file without a backup.

**The backup works once.** The next time a file is in the way, `hello.txt.backup` already exists, and activation fails again, differently:

```text
Existing file '/home/demo/.config/dar-nixos/hello.txt.backup' would be clobbered by backing up '/home/demo/.config/dar-nixos/hello.txt'
```

Deal with the old backup and rebuild, or set `home-manager.overwriteBackup = true;` to let each backup replace the previous one. Some programs rewrite their own config files, which puts a file in the way on every run. Those are the usual cases for `force = true`, or for leaving that file out of Home Manager.

**The system switches anyway.** The collision fails the user's unit, not the build. `nixos-rebuild switch` finishes activating the new system and then reports:

```text
warning: the following units failed: home-manager-demo.service
```

It exits with status 4. The new generation is running and is the boot default. Only that user's files are still the old ones. The VM test reproduces both collisions and checks the journal for the second message.

## Keep the two releases together

The channel name carries the release: `release-26.05` for `nixos-26.05`. When NixOS moves to the next release, move the `home-manager` channel with it. A mismatch fails in one of two ways.

If `home.stateVersion` names a release the older Home Manager doesn't know, evaluation fails. Home Manager `release-25.11` against a `26.05` configuration:

```text
error: A definition for option `home-manager.users.demo.home.stateVersion' is not of type `one of "18.09", ..., "25.05", "25.11"'.
```

Otherwise it's **only a warning**. The system builds, and `nixos-rebuild` prints it:

```text
evaluation warning: demo profile: You are using

  Home Manager version 25.11 and
  Nixpkgs version 26.05.

Using mismatched versions is likely to cause errors and unexpected
behavior. [...]

  home.enableNixpkgsReleaseCheck = false;
```

The last line is how to silence it, not a fix.

In the companion repo, CI reads `config.warnings` and fails on that message, because a warning in a CI log goes unread.

`home.stateVersion` is Home Manager's counterpart of `system.stateVersion`: the release this user's configuration was first written for. Its comment in the manual says, "You should not change this value, even if you update Home Manager." Updating is the channel's job.

Releases also rename options. Home Manager 25.11 moved `programs.git.userName` and `userEmail` to `programs.git.settings.user.name` and `.email`. The old names still evaluate, with a warning, so snippets from older blog posts keep working and keep warning.

## Session variables need a managed shell

`home.sessionVariables` and `home.sessionPath` are written to `hm-session-vars.sh`, and only a shell configured by Home Manager sources it. Nothing on the NixOS side does. If Zsh stays at system level, as in [the Oh My Zsh entry](zsh-oh-my-zsh-declarative.md), the manual says to source it yourself, from the per-user profile when `useUserPackages` is on:

```bash
. "/etc/profiles/per-user/$USER/etc/profile.d/hm-session-vars.sh"
```

The alternative is `programs.zsh.enable = true` inside `home-manager.users.demo`, which writes `~/.zshrc`. Keep `programs.zsh.enable` at system level either way; the Zsh entry explains why, and why Oh My Zsh belongs in only one of the two layers.

## Without a channel

`<home-manager/nixos>` resolves through root's channels, so it depends on state outside the repo. The manual also shows a `builtins.fetchTarball` of the release branch, which moves on every fetch. To make the import reproducible, pin a commit and its hash:

```nix
let
  home-manager = builtins.fetchTarball {
    url = "https://github.com/nix-community/home-manager/archive/<commit>.tar.gz";
    sha256 = "<hash>";
  };
in
{ imports = [ "${home-manager}/nixos" ]; }
```

With the hash, `fetchTarball` is also allowed in pure evaluation, so the same file works when a flake imports it. That's what the companion repo does: its [`proxmox/`](../proxmox/nixos-on-demand-opentofu-nixos-anywhere-sops.md) flake imports the root `configuration.nix` unchanged. A configuration that is a flake from the start would instead add `home-manager.nixosModules.home-manager` to its modules, from a `home-manager` input, as in the manual's flake example. Point that input at `release-26.05` too, and add `home-manager.inputs.nixpkgs.follows = "nixpkgs"` so it doesn't bring its own nixpkgs.

## Checked in CI

The companion repo [dar-nixos](https://github.com/abdelhousni/dar-nixos) carries this setup as [`home.nix`](https://github.com/abdelhousni/dar-nixos/blob/main/home.nix). Its evaluation job fails on a release-mismatch warning and reads the generated git config. Its VM test covers the rest:

- the unit's ordering and its `User=`;
- the store symlinks, and `git config user.name`;
- `rg` from the per-user profile;
- a file in the way, backed up on the first collision and blocking activation on the second.

How those jobs run is covered in [the GitHub Actions entry](nixos-config-tests-github-actions.md) and [the GitLab CE entry](nixos-config-tests-gitlab-ce.md).

## Sources

- The Home Manager manual, [NixOS module](https://nix-community.github.io/home-manager/#sec-install-nixos-module) and [flake setup](https://nix-community.github.io/home-manager/#sec-flakes-nixos-module).
- Home Manager `release-26.05` source:
  - `nixos/default.nix` (the unit) and `nixos/common.nix` (`useGlobalPkgs`, `useUserPackages`);
  - `modules/files/check-link-targets.sh` and `modules/files.nix` (collisions and backups);
  - `modules/home-environment.nix` (release check, session variables);
  - `modules/programs/git.nix` (the renamed options).
- nixpkgs `nixos-26.05`: `switch-to-configuration-ng`, for the failed-unit warning and exit status 4.
