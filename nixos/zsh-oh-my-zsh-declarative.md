# Oh My Zsh on NixOS: the plugin list installs nothing, and NixOS aliases win

NixOS can configure Zsh and Oh My Zsh from `configuration.nix`, with no `~/.zshrc` to back up. The module writes everything into a generated `/etc/zshrc`, and the order of that file explains most of the surprises. This entry comes from evaluating a real configuration against nixpkgs `nixos-26.05`, then starting Zsh 5.9.1 on the resulting `/etc/zshrc` with the packaged Oh My Zsh (`2026-02-19`). It applies to any NixOS, including [NixOS on WSL](nixos-wsl-admin-runbook.md).

## The short version

```nix
{ pkgs, ... }:
{
  programs.zsh = {
    enable = true;                  # not optional, see below
    enableGlobalCompInit = false;   # Oh My Zsh runs compinit itself
    autosuggestions.enable = true;
    syntaxHighlighting.enable = true;
    ohMyZsh = {
      enable = true;
      theme = "robbyrussell";       # the default is "", which means no theme
      plugins = [ "git" "sudo" "kubectl" ];
    };
  };
  users.defaultUserShell = pkgs.zsh;

  # Tools the plugins expect: install them, don't just name them
  programs.fzf.keybindings = true;  # also adds "fzf" to the Oh My Zsh plugins
  programs.zoxide.enable = true;    # runs `zoxide init zsh`; don't list the zoxide plugin too
  environment.systemPackages = [ pkgs.kubectl ];
}
```

Rebuild with `sudo nixos-rebuild switch`, then open a new terminal.

## `programs.zsh.enable` is not optional

Setting a user's shell to `pkgs.zsh` is not enough. NixOS checks, and fails the build with:

> users.users.nixos.shell is set to zsh, but programs.zsh.enable is not true. This will cause the zsh shell to lack the basic nix directories in its PATH and might make logging in as that user impossible.

`programs.zsh.enable` is what generates `/etc/zshenv`, `/etc/zprofile` and `/etc/zshrc`. It also adds Zsh to `/etc/shells`, and links `/share/zsh` from every installed package, so completions shipped by packages are found. `users.defaultUserShell` then applies to `root` and to every `isNormalUser` account, which gets `useDefaultShell = true` by default. System users keep their own shell.

## What `/etc/zshrc` runs, in order

This is the generated file for the configuration above, with the default `enableGlobalCompInit`. Comments and blank lines are removed:

1. `setopt`, history settings, `/etc/zinputrc` key bindings
2. `autoload -U compinit && compinit`, **NixOS's completion init**
3. `zsh-autosuggestions`
4. Oh My Zsh: `plugins=(...)`, `ZSH_THEME`, `ZSH_CACHE_DIR`, then `source $ZSH/oh-my-zsh.sh`, **which runs `compinit` again**
5. `zsh-syntax-highlighting`, placed last with `mkAfter`, as its README requires
6. `dircolors`
7. **`alias` lines from NixOS**
8. The prompt init, which the Oh My Zsh module empties so the NixOS prompt doesn't override the theme

Three consequences follow.

### NixOS aliases override Oh My Zsh's

The aliases come after Oh My Zsh, so any name defined on both sides goes to NixOS. The `git` plugin defines `gc='git commit --verbose'`. Many configurations, including the article this entry started from, also define a `gc` alias for garbage collection:

```nix
programs.zsh.shellAliases.gc = "sudo nix-collect-garbage -d";
```

In the running shell, `alias gc` prints `gc='sudo nix-collect-garbage -d'`. Oh My Zsh's `git commit` shortcut is gone, and nothing warns about it. Commit with `git commit --verbose` directly, or pick another name.

The same happens without any aliases of your own, because NixOS ships three by default in `environment.shellAliases`. They replace Oh My Zsh's `l='ls -lah'` and `ll='ls -lh'` with `l='ls -alh'` and `ll='ls -l'`. To give a name back to Oh My Zsh, set it to `null`, which the module filters out:

```nix
programs.zsh.shellAliases = { l = null; ll = null; };
```

After that, the shell reports `l='ls -lah'` and `ll='ls -lh'` again.

### `compinit` runs twice

With the defaults, completion is initialized once by NixOS (step 2) and once by Oh My Zsh (step 4). Profiling with `zprof` shows `compinit` called twice, and two dump files appear in `$HOME`: `.zcompdump` and `.zcompdump-<host>-5.9.1`. Home Manager's zsh module avoids this on its own side, and its source says why:

> Oh-My-Zsh/Prezto calls compinit during initialization, calling it twice causes slight start up slowdown as all $fpath entries will be traversed again.

The NixOS module doesn't avoid it, so do it yourself with `programs.zsh.enableGlobalCompInit = false;`. Completion keeps working, because Oh My Zsh still calls `compinit`. In the test setup, 30 starts of `zsh -i -c exit` averaged about 105 ms with the default and about 89 ms without it, across three rounds. The saving is small but consistent, and it's paid by every new shell.

### No theme unless you set one

`ohMyZsh.theme` defaults to `""`, and Oh My Zsh only loads a theme when `ZSH_THEME` is non-empty. The module also empties NixOS's own prompt init, so that it doesn't override the theme. Enable Oh My Zsh without a theme and you get Zsh's bare default prompt. Set `theme` explicitly.

## The plugin list loads code, it doesn't install anything

`ohMyZsh.plugins` is a list of names written into `plugins=(...)`. The plugins then look for their tool on `$PATH`, and they handle a missing tool in different ways. With `fzf`, `zoxide` and `kubectl` listed and none of them installed, a new shell prints:

```text
[oh-my-zsh] fzf plugin: Cannot find fzf installation directory.
Please add `export FZF_BASE=/path/to/fzf/install/dir` to your .zshrc
[oh-my-zsh] zoxide not found, please install it from https://github.com/ajeetdsouza/zoxide
```

The advice points to `.zshrc` and an upstream install page, neither of which is how you fix it on NixOS. `kubectl` is worse: its plugin starts with `if (( ! $+commands[kubectl] )); then return`, so its aliases (`k`, `kgp`, …) are silently absent.

NixOS has modules for several of these tools. They install the package and wire it into Zsh:

| Tool | NixOS option | What it does with Oh My Zsh enabled |
|---|---|---|
| fzf | `programs.fzf.keybindings`, `programs.fzf.fuzzyCompletion` | Installs fzf and appends `"fzf"` to `ohMyZsh.plugins` itself, instead of sourcing the key bindings directly |
| zoxide | `programs.zoxide.enable` | Installs zoxide and adds `eval "$(zoxide init zsh)"` (Zsh integration defaults to on). The Oh My Zsh `zoxide` plugin runs the same init, so list one or the other. |
| starship, direnv | `programs.starship.enable`, `programs.direnv.enable` | Same pattern: installed and hooked into Zsh. starship's init goes into the prompt init, which runs last, so its prompt replaces the Oh My Zsh theme. |

For tools without a module, such as `kubectl`, add the package to `environment.systemPackages`. The same applies to alias targets: `cat = "bat"` only works if `bat` is installed (`programs.bat.enable`, or the package).

## State lives in `$HOME`, updates come from nixpkgs

Oh My Zsh itself sits read-only in `/nix/store`. The module points `ZSH_CACHE_DIR` at `$HOME/.cache/oh-my-zsh` and creates it at startup. The option's own description notes that without it, the cache "would default to the read-only nix store". The completion dump goes to `$HOME/.zcompdump-<host>-<zsh version>`.

Oh My Zsh's automatic update check returns early when `$ZSH` isn't writable or isn't a Git checkout, and in the store it's neither. So there is no update prompt, and `omz update` is not how you update. The version moves with your nixpkgs channel or flake input. NixOS 26.05 ships `oh-my-zsh-2026-02-19`.

## System module or Home Manager

The same setup exists per user in [Home Manager](https://nix-community.github.io/home-manager/), with a different option name:

| | NixOS | Home Manager |
|---|---|---|
| Option | `programs.zsh.ohMyZsh` | `programs.zsh.oh-my-zsh` |
| Written to | `/etc/zshrc`, for every user | `~/.zshrc`, for one user |
| Double `compinit` | Yes, unless `enableGlobalCompInit = false` | Skips its own `compinit` when Oh My Zsh is on |
| Cache | `$HOME/.cache/oh-my-zsh` | `$XDG_CACHE_HOME/oh-my-zsh` |

NixOS still accepts `programs.zsh.oh-my-zsh.*` as a renamed alias of `ohMyZsh`, so a Home Manager snippet pasted into `configuration.nix` evaluates, with a warning.

Even with Home Manager, keep `programs.zsh.enable = true` at system level. The shell check above requires it, and Home Manager's `enableCompletion` description asks for `environment.pathsToLink = [ "/share/zsh" ]` for system package completions, which the NixOS module already sets. But enable Oh My Zsh in one layer only. `/etc/zshrc` runs before `~/.zshrc`, so enabling it in both loads it twice.

## Sources

- nixpkgs `nixos-26.05`: `nixos/modules/programs/zsh/zsh.nix`, `oh-my-zsh.nix` and its [manual section](https://nixos.org/manual/nixos/stable/#module-programs-zsh-ohmyzsh), `zsh-syntax-highlighting.nix`, `programs/fzf.nix`, `programs/zoxide.nix`, and the shell assertion in `config/users-groups.nix`.
- Home Manager `release-26.05`: `modules/programs/zsh/default.nix` and `plugins/oh-my-zsh.nix`.
- Oh My Zsh 2026-02-19: `oh-my-zsh.sh`, `tools/check_for_upgrade.sh`, and the `git`, `fzf`, `zoxide` and `kubectl` plugins.
- The [NixOS wiki Zsh page](https://wiki.nixos.org/wiki/Zsh), for the system and Home Manager plugin options.
- Stéphane Robert's [NixOS dans WSL : environnement complet](https://blog.stephane-robert.info/docs/securiser/os-immuable/nixos/installation-wsl/) (in French), whose Zsh module was the starting point for this entry.
