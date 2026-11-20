# Homebrew, Nix and pkgx: the same CLI tools on Ubuntu, Fedora and Arch

Third entry in the Portable environments series. [The second entry](apt-dnf-pacman-side-by-side-ubuntu-fedora-arch.md) showed three different commands for the same job. This one covers the layer above, from [the map](portable-environment-map-package-managers-to-images.md): tools that install your CLI programs in their own directory, independently of the distribution, so the same command and the same version work everywhere. Homebrew, Nix and pkgx were each installed with their official command on Ubuntu 26.04.1, Fedora 45 and Arch, as a normal user with `sudo`, and all three gave the same version of every tool on all three distributions.

| Tool | Version measured | Installs into | Its declarative file |
|---|---|---|---|
| Homebrew | 7.0.12 | `/home/linuxbrew/.linuxbrew` | `Brewfile` |
| Nix | 2.35.4 | `/nix/store`, linked from `~/.nix-profile` | `flake.nix` and `flake.lock` |
| pkgx | 2.11.0 | `~/.pkgx` | `pkgx.yaml` |

`ripgrep` 15.2.0 and `jq` 1.8.2 came out of all three, the same versions Fedora and Arch ship (see the second entry), and newer than Ubuntu's ripgrep 15.1.0.

## Homebrew

Homebrew's vocabulary: a **formula** is the recipe for one program, a **bottle** is that program prebuilt for a platform, a **tap** is a third-party repository of formulae, and a **cask** installs a graphical application (on macOS). Everything lives under one *prefix*, `/home/linuxbrew/.linuxbrew`.

The install command is the one on [brew.sh](https://brew.sh/), which says it works in "the macOS Terminal, a Linux shell or WSL":

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"   # in ~/.bashrc or ~/.zshrc
brew install ripgrep jq
```

The installer uses `sudo` to create `/home/linuxbrew`, then gives it to your user (`stat` showed the prefix owned by `dev`, the test user), and nothing after that needs root. [Homebrew on Linux](https://docs.brew.sh/Homebrew-on-Linux) asks for a working C compiler and the usual development tools on the host. Installing `ripgrep` and `jq` from bottles took under 10 seconds. `ldd` shows the mix: `rg` loads `libpcre2` from Homebrew's prefix, but `libc` and `libgcc_s` from the distribution. Homebrew uses the host's glibc and gcc when they are recent enough, and installs its own otherwise.

Run as root in a container, the installer and `brew install` both worked too, and the prefix was then owned by root.

### The Brewfile

A `Brewfile` lists what should be installed, and `brew bundle` applies it ([Brew Bundle and Brewfile](https://docs.brew.sh/Brew-Bundle-and-Brewfile)):

```ruby
brew "ripgrep"
brew "jq"
brew "tree"
```

| Command | What it did here |
|---|---|
| `brew bundle check` | exit status 1 and "can't satisfy your Brewfile's dependencies" while `tree` was missing, 0 after |
| `brew bundle install` | installed `tree` |
| `brew bundle dump --file=Brewfile.dumped` | wrote all three back, each with its description as a comment |
| `brew bundle cleanup` | with `tree` removed from the `Brewfile`: listed "Would uninstall formulae: tree" |
| `brew bundle cleanup --force` | uninstalled it |

`cleanup` is what apt, dnf and pacman don't have: removing a line from the file removes the program from the machine. A `Brewfile` also accepts `cask`, `tap`, `vscode`, `go`, `cargo`, `uv`, `flatpak` and `npm` lines, among others.

**No lockfile, and no older versions.** The Homebrew docs say `brew bundle` "does not and will not have a concept of a 'Brewfile lock file'". Older versions of its README described a `Brewfile.lock.json`; none was written here. Homebrew is a *rolling release*: it installs the current version of each formula, not an arbitrary older one. `brew pin jq` (or `pin: true` on a `Brewfile` line) only stops later upgrades of what's already installed.

## Nix

Nix builds every package into its own directory under `/nix/store`, named after a hash of everything that went into the build: `/nix/store/yn2n603bacr51pigr0d9ldx7bcd51vlh-ripgrep-15.2.0`. Two versions of a library never overwrite each other, because they live in different directories. Prebuilt results come from a *binary cache*, `cache.nixos.org`. A **profile** is the set of packages linked into your `PATH`, from `~/.nix-profile/bin`. [The NixOS first-steps entry](../nixos/first-steps-configuration-generations-rollback.md) covers the same ideas on a NixOS machine.

[The download page](https://nixos.org/download/) gives two installs. The *multi-user* one (`--daemon`) runs a `nix-daemon` service and is the one it recommends on Linux with systemd; on WSL it needs systemd enabled. These containers have no systemd, so this test used the *single-user* one:

```bash
curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install | sh -s -- --no-daemon
. ~/.nix-profile/etc/profile.d/nix.sh
```

It used `sudo` once, to create `/nix`, owned by the user afterwards. Sourcing `nix.sh` did nothing until `USER` was set: `docker run` doesn't set it, and the script needs it.

The `nix` command and flakes are still **experimental features** in Nix 2.35 ([the manual's list](https://nix.dev/manual/nix/2.35/development/experimental-features)), so they have to be switched on:

```bash
echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
nix profile add nixpkgs#ripgrep nixpkgs#jq   # 17 seconds, from the binary cache
nix profile remove jq
nix profile rollback                          # "switching profile from version 3 to 2": jq is back
nix run nixpkgs#hello                         # runs it without adding it to the profile
```

Every change to a profile is a numbered version, and `nix profile history` lists them. That rollback is the undo that Homebrew and pacman lack. `ldd` on `rg` showed only `/nix/store` paths, down to `gcc-16.2.0-lib`: unlike Homebrew, Nix takes nothing from the distribution.

### A flake pins everything

A **flake** is a directory with a `flake.nix` that declares its inputs, here the NixOS 26.05 package set, and what it provides, here a development shell with three tools. The first use writes a `flake.lock` that pins each input to an exact release and content hash:

```nix
{
  inputs.nixpkgs.url = "https://channels.nixos.org/nixos-26.05/nixexprs.tar.xz";
  outputs = { nixpkgs, ... }:
    let pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in {
      devShells.x86_64-linux.default = pkgs.mkShell {
        packages = [ pkgs.ripgrep pkgs.jq pkgs.tree ];
      };
    };
}
```

`nix develop -c tree --version` printed `tree v2.3.2` after 20 seconds, and `flake.lock` recorded:

```json
"locked": {
  "narHash": "sha256-4D+5oPvxkOa6tTCWXi4jwRfmWhDXGRSrX4+eOTItLh0=",
  "rev": "c56a87d8e41ce69bd2af57eb35dcc117a9dfca33",
  "type": "tarball",
  "url": "https://releases.nixos.org/nixos/26.05/nixos-26.05.13627.c56a87d8e41c/nixexprs.tar.xz"
}
```

Commit both files, and another machine using the same `flake.lock` gets the same package set. In a Git repository, Nix only reads tracked files: before `git add flake.nix`, it stopped with `Path 'flake.nix' in the repository "/home/dev/p" is not tracked by Git.` The usual input is `github:NixOS/nixpkgs/nixos-26.05`; the channel tarball was used here because that form goes through GitHub's API, which the test environment's proxy refused. [The standalone Home Manager entry](../nixos/home-manager-standalone-wsl-uv-ansible-opentofu.md) uses a flake like this one to manage a whole user environment on WSL2.

## pkgx

pkgx runs a program without installing it: it downloads the package into `~/.pkgx` on first use and runs it from there, without touching your `PATH`.

```bash
curl -fsS https://pkgx.sh | sh     # puts a 10 MB pkgx binary in /usr/local/bin
pkgx rg --version                  # ripgrep 15.2.0, under 1 second
pkgx rg@14 --version               # ripgrep 14.1.1, side by side
pkgx +jq +tree -- bash             # a shell with both on PATH
```

After those commands, `command -v rg jq` found nothing: the packages were in `~/.pkgx/crates.io/ripgrep/v15.2.0/` and so on, only reachable through `pkgx`. Packages are named by their project's home, such as `crates.io/ripgrep` or `stedolan.github.io/jq`.

Two companion tools come with the installer ([docs.pkgx.sh](https://docs.pkgx.sh/)):

- **`pkgm`** installs packages for good. Run as the normal user, `pkgm install jq` put `jq` in `~/.local/bin`, not in `/usr/local` as the docs describe for it.
- **`dev`** gives a project its own tools, from a `pkgx.yaml` ([dev's README](https://github.com/pkgxdev/dev)):

```yaml
dependencies:
  stedolan.github.io/jq: ~1.7
  crates.io/ripgrep: ^14
```

In that directory, `eval "$(pkgx dev)"` put `jq` 1.7.1 and `ripgrep` 14.1.1 on the `PATH`. Version ranges in the file are honoured, but no lockfile records what they resolved to. `dev` is a Deno program, so its first run downloaded its own dependencies from `jsr.io`, `registry.npmjs.org` and `raw.githubusercontent.com`.

## Side by side

| | Homebrew | Nix | pkgx |
|---|---|---|---|
| Root needed | to create `/home/linuxbrew` once | to create `/nix` once (single-user); the daemon install runs a root service | to put `pkgx` in `/usr/local/bin` once |
| Programs on your `PATH` | yes, from the prefix | yes, from the profile | no, unless you use `pkgm` or `dev` |
| Libraries from the distribution | glibc and gcc, when recent enough | none | not checked |
| Declarative file | `Brewfile` | `flake.nix` | `pkgx.yaml` |
| Lockfile | none, by design | `flake.lock` | none |
| Older versions | no | by pointing the input at an older release (not tested here) | yes, `pkgx rg@14` |
| Remove what's no longer listed | `brew bundle cleanup` | a dev shell only ever contains what `flake.nix` lists | nothing to remove: nothing was installed |
| Undo | no | `nix profile rollback` | not needed |
| Experimental parts | none | the `nix` command and flakes | none |

## Sources and where this ran

Versions were measured, not taken from articles: the coverage found for Homebrew stopped at 5.1, and the installer gave 7.0.12. Documentation used: [brew.sh](https://brew.sh/), [Homebrew on Linux](https://docs.brew.sh/Homebrew-on-Linux), [Brew Bundle and Brewfile](https://docs.brew.sh/Brew-Bundle-and-Brewfile), [nixos.org/download](https://nixos.org/download/), [Nix experimental features](https://nix.dev/manual/nix/2.35/development/experimental-features), [docs.pkgx.sh](https://docs.pkgx.sh/) and [pkgxdev/dev](https://github.com/pkgxdev/dev), all read on 8 November 2026.

Everything ran under Docker in a Linux cloud container, on 8 November 2026, in the official Ubuntu 26.04, Fedora 45 and Arch images with a `dev` user added. Nothing ran in WSL or on macOS, and the Nix multi-user install wasn't tested, because the containers have no systemd.
