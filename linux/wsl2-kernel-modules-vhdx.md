# Loadable modules for a custom WSL2 kernel: a `modules.vhdx` and one `.wslconfig` line


A custom WSL2 kernel built as in [Building a custom WSL2 kernel on GitHub Actions](wsl2-kernel-on-github-actions.md) boots fine, but **every feature its config marks `=m` is missing**. `modprobe wireguard` answers `Module wireguard not found in directory /lib/modules/6.18.54.1-wsl2-x86_64-v3+`. Microsoft's `config-wsl` has 744 such options, among them the ones Kubernetes, VMs and VPNs need.

Some terms first:
- **Built in (`=y`)**: compiled into the `bzImage` itself; always there.
- **Module (`=m`)**: compiled into a separate `.ko` file that `modprobe` loads on demand from `/lib/modules/<release>/`, where `<release>` is exactly what `uname -r` prints.
- **`bzImage`**: the compressed kernel file that `.wslconfig` `kernel=` points to. It carries no modules.
- **VHDX**: the Hyper-V virtual disk format. WSL can attach one to its VM read-only, next to the distro disks.

A WSL2 VM runs **one kernel for every distro**. The modules have to be there for that exact build in each distro, without writing into each distro's `/lib/modules`.

## Two ways out

| | Everything `=y` | Modules in a VHDX |
|---|---|---|
| Change to the build | `sed -i 's/=m$/=y/' .config` before `make olddefconfig` | `make modules_install`, then package |
| Size (x86-64-v3) | `bzImage` 33 MB (6.18.54.1), 0 options left `=m` | `bzImage` 16 MB + `modules.vhdx` 143 MB (6.18.58.1, 748 modules, debug info stripped) |
| `.wslconfig` | `kernel=` only | `kernel=` and `kernelModules=` |
| Loaded at boot | all 2,591 options, used or not | only what something asks for |
| Must match | nothing | the VHDX belongs to one build: same `uname -r`, same compile |

Both work for every distro at once. The rest of this entry is the VHDX route.

## How WSL uses the VHDX

`kernelModules=` in the `[wsl2]` section of `%UserProfile%\.wslconfig` takes "an absolute Windows path to a custom Linux kernel modules VHD" ([wsl-config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)). WSL's own init (`src/linux/init/main.cpp` in [microsoft/WSL](https://github.com/microsoft/WSL)) then:

<figure>
<img src="wsl2-kernel-modules-vhdx.svg" alt="On the Windows host, .wslconfig points kernel= to a bzImage and kernelModules= to modules.vhdx. In the WSL2 virtual machine, the bzImage boots as the one Linux kernel, and the VHDX is attached and mounted read-only at /modules. Each distro, here Ubuntu 26.04 and NixOS, gets an overlay on /lib/modules/release: a writable upper layer in the distro over the read-only modules from /modules. A module loaded with modprobe in Ubuntu shows up in lsmod in NixOS, because both share the kernel." width="860" height="500" loading="lazy">
<figcaption>One <code>.wslconfig</code> line attaches the VHDX to the VM (as a SCSI disk). WSL mounts it once, then gives every distro an overlay on top of it.</figcaption>
</figure>

- The VHDX lays its files out as `<release>/modules` and `<release>/linux-headers`. WSL also accepts the older flat layout (the modules tree at the disk's root), with a warning that support for it is going away.
- On top of the read-only disk sits a writable overlay. The only thing written to a distro's own disk is the empty mountpoint directory `/usr/lib/modules/<release>/` (4 KB). NixOS gets the same overlay at `/lib/modules/<release>`.
- There is one kernel, so a module loaded from one distro is loaded for all of them: `/proc/modules` in NixOS lists the `wireguard` that Ubuntu loaded.
- WSL then loads `tun`, `ip_tables` and `br_netfilter` (`loadDefaultKernelModules=true`), plus any comma-separated list in `loadKernelModules=`.
- If `<release>` in the VHDX doesn't match `uname -r`, WSL logs "kernel modules VHD does not contain modules for …" and carries on without them.

## The workflow

Microsoft's repository ships the packaging script: `Microsoft/scripts/gen_artifacts_vhdx.sh <modules dir> <headers dir> <perf dir> <kernelrelease> <output>`. Older guides call it `gen_modules_vhdx.sh`; it was renamed on 2026-07-31, when it started bundling headers and perf. It uses `mke2fs -d` (e2fsprogs) to build an ext4 image and `qemu-img convert -O vhdx` (qemu-utils) to convert it.

Added to the build of the previous entry (full file: [`build-wsl2-kernel-modules.yml`](https://github.com/abdelhousni/WSL2-Linux-Kernel/blob/modules-vhdx/.github/workflows/build-wsl2-kernel-modules.yml) on the `modules-vhdx` branch of abdelhousni/WSL2-Linux-Kernel):

```yaml
      - run: sudo apt-get install -y qemu-utils e2fsprogs kmod cpio

      # after: make -j"$(nproc)" KCFLAGS="-march=x86-64-v3"   (no target: kernel + modules)
      - name: Package modules.vhdx
        run: |
          KREL=$(make -s kernelrelease)
          make INSTALL_MOD_PATH="$PWD/out/modules" INSTALL_MOD_STRIP=1 modules_install
          make headers_install INSTALL_HDR_PATH="$PWD/out/headers"
          mkdir -p out/perf     # left empty, see below
          ./Microsoft/scripts/gen_artifacts_vhdx.sh \
            out/modules out/headers out/perf "$KREL" modules.vhdx
```

Upload `arch/x86/boot/bzImage` **and** `modules.vhdx` from the same run: a VHDX from one build doesn't fit a `bzImage` from another, even from the same source.

The perf directory stays empty on purpose. WSL 3.0.5 removed its bundled perf integration ([microsoft/WSL#41904](https://github.com/microsoft/WSL/pull/41904)), but the script still requires the argument.

## Using it

```ini
[wsl2]
kernel=G:\\wsl\\kernels\\20261110b-bzImage-wsl2-x86_64-v3
kernelModules=G:\\wsl\\kernels\\20261110b-modules-wsl2-x86_64-v3.vhdx
# optional: load these at every boot
# loadKernelModules=wireguard,kvm_amd
```

Then `wsl --shutdown` (it stops every distro) and, in any distro:

```console
$ uname -r
6.18.58.1-wsl2-x86_64-v3+
$ mount | grep /lib/modules
none on /usr/lib/modules/6.18.58.1-wsl2-x86_64-v3+ type overlay (rw,nosuid,nodev,noatime,lowerdir=/modules/6.18.58.1-wsl2-x86_64-v3+/modules,upperdir=/lib/modules/6.18.58.1-wsl2-x86_64-v3+/rw/upper,workdir=/lib/modules/6.18.58.1-wsl2-x86_64-v3+/rw/work,uuid=on)
$ lsmod | grep br_netfilter      # loaded by WSL at boot
br_netfilter           32768  0
$ sudo modprobe -a wireguard kvm_amd vhost_net ip_vs macvlan ipvlan nfs cifs nft_ct erofs && echo ok
ok
$ ls -l /dev/kvm; cat /proc/sys/net/bridge/bridge-nf-call-iptables
crw-rw---- 1 root kvm 10, 232 Nov 10 09:18 /dev/kvm
1
```

Use `kvm_intel` on an Intel CPU. On a Ryzen 7 5700X, `kvm_amd` loads and `/dev/kvm` appears.

## Pitfalls

- **Strip the modules.** Without `INSTALL_MOD_STRIP=1`, `modules_install` copies each `.ko` with its debug info, and the VHDX came out at 1.1 GB. With it (`strip --strip-debug` on each module, per `Documentation/kbuild/kbuild.rst`), the same 748 modules fit in 143 MB and still load.
- **Tag names.** Microsoft's merge commits say `rolling-lts/wsl/6.18.58.1`, but the git tag is `linux-msft-wsl-6.18.58.1`. Check with `git ls-remote --tags https://github.com/microsoft/WSL2-Linux-Kernel`.
- **The trailing `+` in `uname -r`.** It comes from building a checkout that isn't exactly on a tag. The VHDX must carry the same string, which it does when `KREL` comes from `make -s kernelrelease` in the same tree.
- **`workflow_dispatch` only sees the default branch.** `gh workflow run x.yml --ref my-branch` answers `HTTP 404: workflow x.yml not found on the default branch` when the file exists only on `my-branch`. Either merge the file into the default branch first, or add `on: push: branches: [my-branch]` and fall back to a default ref (`${{ inputs.ref || 'linux-msft-wsl-6.18.58.1' }}`), since a push event has no inputs.
- **The nested layout needs a recent WSL.** It came in with [microsoft/WSL#41267](https://github.com/microsoft/WSL/pull/41267) (August 2026), and WSL 2.9.13 and later have it. `wsl --version` shows yours.

## Sources

- `Documentation/kbuild/kbuild.rst` in the kernel tree (`INSTALL_MOD_STRIP`).
- Microsoft Learn: [Advanced settings configuration in WSL](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) (`kernelModules`, `loadDefaultKernelModules`, `loadKernelModules`).
- [microsoft/WSL2-Linux-Kernel](https://github.com/microsoft/WSL2-Linux-Kernel) at `linux-msft-wsl-6.18.58.1`: `README.md` (build and VHDX steps), `Microsoft/scripts/gen_artifacts_vhdx.sh`.
- [microsoft/WSL](https://github.com/microsoft/WSL) at `0ef985e`: `src/linux/init/main.cpp` (mount, overlay, layout fallback). Pull requests #41267, #41400 and #41904.
- Configs compared by extracting the embedded `.config` (`CONFIG_IKCONFIG`) from both 6.18.54.1 `bzImage`s.

_The build ran on a GitHub-hosted `ubuntu-latest` runner (about 35 minutes, 32 of them compiling); the boot and `modprobe` checks ran in WSL 3.0.5 on Windows 11, in Ubuntu 26.04 and NixOS._
