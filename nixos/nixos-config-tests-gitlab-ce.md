# Testing a NixOS configuration on self-managed GitLab CE: the eval job runs anywhere, the VM test needs a runner you prepare

This is the GitLab counterpart of [the GitHub Actions entry](nixos-config-tests-github-actions.md), with the same two levels and the same repo, [dar-nixos](https://github.com/abdelhousni/dar-nixos). The evaluation job needs nothing from the runner. The VM test needs `/dev/kvm` inside the job container, with permissions the Nix build users can use. On GitHub an action sets that up for you. On-prem it's your runner host, so it's your job.

The pipeline below ran on a fresh **GitLab CE 19.4.1** with **gitlab-runner 19.4.1**, using the Docker executor and the `nixos/nix:2.34.8` image. The `eval` job passed in 74 seconds. The VM job couldn't run there, because that host has no KVM. The failure messages quoted below are the real ones from that setup. The permission behavior was checked with a stand-in device node. The full boot was confirmed on GitHub-hosted runners, not on GitLab.

## The pipeline

```yaml
default:
  image: nixos/nix:2.34.8

variables:
  NIX_PATH: "nixpkgs=channel:nixos-26.05"

stages: [eval, test]

eval:
  stage: eval
  script:
    - ./ci/eval-checks.sh

vm-test:
  stage: test
  tags: [kvm]
  script:
    - test -e /dev/kvm || { echo "No /dev/kvm in this job container"; exit 1; }
    - nix --extra-experimental-features nix-command config show system-features
    - nix-build test.nix
```

[`ci/eval-checks.sh`](https://github.com/abdelhousni/dar-nixos/blob/main/ci/eval-checks.sh) and [`test.nix`](https://github.com/abdelhousni/dar-nixos/blob/main/test.nix) are the same files the GitHub workflow runs. The GitHub entry explains what they check.

## Four things about the `nixos/nix` image

- **Its channel is `nixpkgs-unstable`.** The image's `/root/.nix-channels` points at `https://channels.nixos.org/nixpkgs-unstable`. Without the `NIX_PATH` variable, `<nixpkgs>` is whatever unstable was when the image was built, not the release your machines run.
- **`nix-command` isn't enabled.** Its `nix.conf` holds only `build-users-group = nixbld`, `sandbox = false` and the cache key. Commands like `nix config show` need `--extra-experimental-features nix-command`. The classic `nix-instantiate` and `nix-build` don't.
- **Builds run as `nixbld` users, not root.** That's what `build-users-group = nixbld` means. It matters for `/dev/kvm`, below.
- **It's minimal.** `bash`, `grep`, `git`, `curl` and `tar` are there. `awk`, `sed`, `jq` and `python3` aren't. That's why `eval-checks.sh` uses only `bash` and `grep`, with `nix-instantiate --eval --raw` to get plain text instead of JSON.

## The runner: a tag and a device

Register a second runner, or a second `[[runners]]` entry, for the VM test. It only takes tagged jobs and passes the KVM device through:

```toml
[[runners]]
  name = "docker-kvm"
  url = "https://gitlab.example.com"
  token = "glrt-…"            # from Admin > CI/CD > Runners, created with tag "kvm"
  executor = "docker"
  [runners.docker]
    image = "nixos/nix:2.34.8"
    devices = ["/dev/kvm"]
```

Create the runner with the tag `kvm` and "Run untagged jobs" off. Then `vm-test` lands only there, and other jobs never use it. `devices` is the documented [`[runners.docker]` option](https://docs.gitlab.com/runner/configuration/advanced-configuration/) to "share additional host devices with the container". `privileged = true` is not needed.

## Three host prerequisites, and how each one fails

**1. The runner host has a `/dev/kvm`.** On bare metal that means VT-x/AMD-V enabled in the firmware. On-prem runners are usually VMs themselves, which needs nested virtualization. On Proxmox, [enable the `nested` parameter of `kvm_intel`/`kvm_amd`](https://pve.proxmox.com/wiki/Nested_Virtualization) on the host and set the runner VM's CPU type to `host`. On vSphere, tick [*Expose hardware assisted virtualization to the guest OS*](https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere/7-0/vsphere-virtual-machine-administration/configuring-virtual-machine-hardwarevm-admin/virtual-cpu-configuration-and-limitationsvm-admin/expose-hardware-assisted-virtualizationvm-admin.html) in the VM's CPU settings. The same page warns that VMware "does not support running third-party hypervisors on ESXi", Hyper-V for VBS excepted, so a KVM runner inside an ESXi VM is outside VMware support. A bare-metal runner, or a Proxmox/KVM host, avoids the question. Without it, Docker can't create the job container at all, and the job ends as a runner system failure:

```text
ERROR: Job failed (system failure): prepare environment: Error response from daemon:
error gathering device information while adding custom device "/dev/kvm": no such file or directory
```

**2. The Nix build users can open it.** Docker recreates the device inside the container with the host's mode and group ID. A stand-in node made `0660`, group 36 on the host showed up in the container as `crw-rw---- 1 0 36`. There, `nixbld1` is only in group `nixbld`, so it can't open the device. Distributions differ on the mode:

- Debian and Ubuntu build systemd with `-Ddev-kvm-mode=0660`.
- CentOS Stream 10 builds it with `0666`, which is also systemd's upstream default.

On a Debian or Ubuntu runner host, add the same udev rule `install-nix-action` uses on GitHub, then run `udevadm control --reload-rules && udevadm trigger --name-match=kvm`:

```text
# /etc/udev/rules.d/99-kvm-nix.rules
KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"
```

This is the dangerous failure. The job runs as root, so Nix sees an accessible `/dev/kvm` and advertises the `kvm` feature. The build users then can't open it, and QEMU (`accel=kvm:tcg`) silently falls back to software emulation. dar-nixos sets `qemu.forceAccel = true` in `test.nix` so that this case fails instead: *"forceAccel is enabled but /dev/kvm is not accessible (permission denied)"*.

**3. Nix advertises `kvm`.** This is automatic once the first two hold: Nix adds `kvm` when `/dev/kvm` is accessible. The `system-features` line in the job log shows it. If it's missing, the build stops before any VM starts:

```text
Reason: missing system features
Required features: {kvm, nixos-test}
Available features: {benchmark, big-parallel, nixos-test}
```

## Behind a corporate proxy

On-prem runners often reach the internet through a TLS-intercepting proxy, and Nix downloads from `channels.nixos.org` and `cache.nixos.org`. Nix uses the standard proxy variables. It reads its CA bundle from `NIX_SSL_CERT_FILE`, then `SSL_CERT_FILE` ([Nix manual, `ssl-cert-file`](https://nix.dev/manual/nix/2.34/command-ref/conf-file.html)). Set both on the runner, not in every `.gitlab-ci.yml`:

```toml
[[runners]]
  environment = ["https_proxy=http://proxy.example.com:3128",
                 "http_proxy=http://proxy.example.com:3128",
                 "NIX_SSL_CERT_FILE=/etc/ssl/corp-ca-bundle.crt"]
  [runners.docker]
    volumes = ["/etc/ssl/corp-ca-bundle.crt:/etc/ssl/corp-ca-bundle.crt:ro"]
```

The test pipeline ran this way, through the sandbox's own intercepting proxy. `NIX_SSL_CERT_FILE` replaces Nix's default bundle rather than adding to it, so the file must include every CA Nix needs to trust, not just the proxy's.

Not covered here: caching. Each job starts from an empty store and downloads nixpkgs and its dependencies again. On GitHub that's cheap. On-prem, a local binary cache or a caching proxy for `cache.nixos.org` is the next thing to set up.
