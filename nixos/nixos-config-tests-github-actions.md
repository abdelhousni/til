# Testing a NixOS configuration on GitHub Actions: evaluate on every push, boot it where KVM is

A NixOS configuration can be tested in CI at two levels. The first evaluates it: nothing is built and nothing boots, so it runs on any runner. The second boots the machine in QEMU and checks it from inside, and that needs KVM. GitHub-hosted Linux runners have KVM, but only one setting makes it usable. Everything here runs in the companion repo [dar-nixos](https://github.com/abdelhousni/dar-nixos). Its checks cover the [Oh My Zsh entry](zsh-oh-my-zsh-declarative.md): one `compinit`, a theme set, and the NixOS `gc` alias overriding the git plugin's. The same two levels on a self-managed GitLab are in [the GitLab CE entry](nixos-config-tests-gitlab-ce.md).

## Level 1: evaluate, and read the generated files

NixOS assertions fire at evaluation time, for example *"users.users.demo.shell is set to zsh, but programs.zsh.enable is not true"*. Instantiating the system is enough to trigger them:

```sh
nix-instantiate '<nixpkgs/nixos>' -A vm -I nixos-config=./configuration.nix
```

The attribute is `vm`, not `system`, because the repo has no `hardware-configuration.nix`. The real system then fails its own assertion, *"The ‘fileSystems’ option does not specify your root file system"*. The VM variant brings its own disk.

The same evaluation can also return any generated file as plain text, without building it. `--raw` prints the string as is:

```sh
nix-instantiate --eval --strict --raw -E \
  '(import <nixpkgs/nixos> { configuration = ./configuration.nix; }).config.environment.etc.zshrc.text'
```

From there it's `grep`. [`ci/eval-checks.sh`](https://github.com/abdelhousni/dar-nixos/blob/main/ci/eval-checks.sh) fails if `/etc/zshrc` contains `autoload -U compinit`, if `ZSH_THEME` is empty, or if the `alias -- gc=` line comes before `source $ZSH/oh-my-zsh.sh`. Each check was tested by breaking the configuration on purpose:

| Change | Result |
|---|---|
| `enableGlobalCompInit = true` | `FAIL: /etc/zshrc runs compinit before Oh My Zsh does` |
| `theme = ""` | `FAIL: no Oh My Zsh theme set` |
| `programs.zsh.enable = false` | The NixOS assertion, for `demo` **and** `root` (via `users.defaultUserShell`) |

This job took 37 seconds on `ubuntu-latest`, most of it downloading the nixpkgs channel.

## Level 2: boot it with `runNixOSTest`

[`test.nix`](https://github.com/abdelhousni/dar-nixos/blob/main/test.nix) uses `pkgs.testers.runNixOSTest`. It boots the configuration in QEMU and drives it from a Python script, so it can check what only a running system knows:

```python
gc = machine.succeed("su -l demo -c \"zsh -ic 'alias gc'\" 2>&1")
assert "nix-collect-garbage" in gc, gc
startup = machine.succeed("su -l demo -c \"zsh -ic exit\" 2>&1")
assert "[oh-my-zsh]" not in startup, startup
machine.fail("test -e /home/demo/.zcompdump")   # NixOS's compinit dump: absent
```

The test derivation declares `requiredSystemFeatures = [ "kvm" "nixos-test" ]`. On a machine without `kvm`, Nix won't even start it:

```text
error: Cannot build '/nix/store/…-vm-test-run-dar-nixos.drv'.
       Reason: missing system features
       Required features: {kvm, nixos-test}
       Available features: {benchmark, big-parallel, nixos-test}
```

## What makes KVM work on a hosted runner

The [Nix manual](https://nix.dev/manual/nix/2.34/command-ref/conf-file.html) says Nix adds `kvm` to its system features on Linux "if /dev/kvm is accessible". But builds don't run as the runner's user, and Ubuntu builds its systemd with `-Ddev-kvm-mode=0660`, so by default `/dev/kvm` is only usable by the `kvm` group.

[`cachix/install-nix-action`](https://github.com/cachix/install-nix-action) handles this with its `enable_kvm` input, which defaults to `true`. Its install script writes this udev rule, then reloads udev:

```text
KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"
```

After that, `kvm` shows up in `nix config show system-features` with nothing else to configure. The action's README suggests also setting `system-features = nixos-test benchmark big-parallel kvm` in `extra_nix_config`, but with `/dev/kvm` accessible Nix detects it without that. The workflow prints the feature list, so you can see it in the log.

## Make "no KVM" fail loudly: `qemu.forceAccel`

The failure worth guarding against is not "no KVM", which Nix refuses clearly. It's "Nix thinks there's KVM, but QEMU can't use it". That happens when `kvm` was added to `system-features` by hand, or when the Nix build users can't open `/dev/kvm`. NixOS starts QEMU with `-machine accel=kvm:tcg`, so it silently falls back to software emulation. The test still passes eventually, but slowly enough to hit a CI timeout, and nothing in the log says why.

The test driver has an option for this, which dar-nixos sets in `test.nix`:

```nix
qemu.forceAccel = true;
```

Without usable KVM, the VM then refuses to start:

```text
forceAccel is enabled but /dev/kvm does not exist.
Hardware-accelerated virtualisation (KVM) is not available on this system.
```

When the device exists but can't be opened, it prints *"…is not accessible (permission denied)"* instead, and suggests checking the build user's `kvm` group membership.

## The workflow

```yaml
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: cachix/install-nix-action@13d8dd58da0234aa297dedd986986ccb8e7f3e24 # v31.11.1
        with:
          nix_path: nixpkgs=channel:nixos-26.05
          enable_kvm: false
      - run: ./ci/eval-checks.sh

  vm-test:
    needs: eval
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: cachix/install-nix-action@13d8dd58da0234aa297dedd986986ccb8e7f3e24 # v31.11.1
        with:
          nix_path: nixpkgs=channel:nixos-26.05
          enable_kvm: true
      - run: nix --extra-experimental-features nix-command config show system-features
      - run: nix-build test.nix
```

`needs: eval` means a configuration that doesn't evaluate never reaches the VM job. The actions are pinned to commit SHAs, with the version in a comment.

`nixpkgs=channel:nixos-26.05` follows the release branch, so a later run can pick up a newer nixpkgs than the one that last passed. For a run that's reproducible bit for bit, point `nix_path` at a fixed commit tarball, or use a flake and its lock file. The [nix.dev pinning guide](https://nix.dev/tutorials/towards-reproducibility-pinning-nixpkgs) covers both.

## Result

On the pull request that added these checks ([dar-nixos#1](https://github.com/abdelhousni/dar-nixos/pull/1)), both jobs passed on `ubuntu-latest`. The `vm-test` log shows the whole chain:

```text
##[group]Enabling KVM support
KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"
Enabled KVM
…
benchmark big-parallel kvm nixos-test uid-range
…
machine # [    0.000000] Hypervisor detected: KVM
machine: (finished: waiting for the VM to finish booting, in 14.84 seconds)
…
machine: (finished: must fail: test -e /home/demo/.zcompdump, in 0.02 seconds)
test script finished in 34.72s
```

The whole `vm-test` job took 1 minute 26 seconds, and `eval` took 37 seconds. The slowest single check was the first `zsh -ic`, at 8 seconds, because it builds the completion dump. The next shell started in about a second.
