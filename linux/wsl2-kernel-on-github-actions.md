# Building a custom WSL2 kernel on GitHub Actions: `KCFLAGS`, not `CFLAGS`

A custom WSL2 kernel is one `bzImage` file and one line in `.wslconfig`. Compiling it takes a full Linux toolchain and a quarter of an hour of four cores. GitHub Actions provides both. Standard runners are **free for public repositories**, with 4 CPUs and 16 GB of RAM. Private repositories get 2 CPUs, and 2,000 free minutes a month on the Free plan. Each job may run for up to 6 hours.

Checked by building `linux-msft-wsl-6.18.40.1` with GCC 15 on 4 cores: about 17 minutes, `uname -r` of `6.18.40.1-wsl2-x86_64-v3+`.

## The workflow

In any repository of yours, as `.github/workflows/wsl2-kernel.yml`:

```yaml
name: wsl2-kernel

on:
  workflow_dispatch:
    inputs:
      ref:
        description: Branch or tag of microsoft/WSL2-Linux-Kernel
        default: linux-msft-wsl-6.18.y

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          repository: microsoft/WSL2-Linux-Kernel
          ref: ${{ inputs.ref }}
          persist-credentials: false

      - run: |
          sudo apt-get update
          sudo apt-get install -y build-essential flex bison bc libssl-dev libelf-dev dwarves

      - run: |
          cp Microsoft/config-wsl .config
          ./scripts/config --set-str LOCALVERSION -wsl2-x86_64-v3
          make olddefconfig
          make -j"$(nproc)" KCFLAGS="-march=x86-64-v3" bzImage

      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: bzImage
          path: arch/x86/boot/bzImage
```

To use it:
1. Run the workflow from the *Actions* tab.
2. Download the `bzImage` artifact and unzip it on Windows.
3. Point `%UserProfile%\.wslconfig` at it:

   ```ini
   [wsl2]
   kernel=C:\\wsl-kernels\\bzImage
   ```

4. Run `wsl --shutdown`, reopen the distro, and check `uname -r`.

Microsoft's branches are `linux-msft-wsl-6.18.y`, `6.6.y`, `6.1.y`, and so on. Tags such as `linux-msft-wsl-6.18.40.1` pin one release. `git ls-remote --heads https://github.com/microsoft/WSL2-Linux-Kernel` lists them.

## `CFLAGS=` breaks the build; `KCFLAGS=` doesn't

The obvious command fails early:

```sh
make -j4 CFLAGS="-march=x86-64-v3 -O2 -pipe"
```

```text
exec-cmd.c:2:10: fatal error: linux/compiler.h: No such file or directory
make[5]: *** [tools/build/Makefile.build:86: tools/objtool/libsubcmd/exec-cmd.o] Error 1
```

The kernel itself ignores `CFLAGS`; its own flags live in `KBUILD_CFLAGS`. But a variable set on the `make` command line overrides every assignment of the same name in the sub-makes. `tools/objtool` builds with its own `CFLAGS`, including the `-I` paths to the kernel's headers. The command-line value replaces them, so `libsubcmd` can't find `linux/compiler.h`.

Running `make prepare` first, the usual advice for this error, doesn't help. The error comes from building `objtool`, and `prepare` builds it too. **`KCFLAGS` is the documented variable for extra compiler flags.** The top-level `Makefile` appends it to `KBUILD_CFLAGS`, and the same build then completes.

Two more traps from older guides:
- **`CONFIG_GENERIC_CPU` and `CONFIG_MCORE2` don't exist on x86-64 in 6.18.** Editing them does nothing.
- **`CONFIG_X86_NATIVE_CPU` builds with `-march=native`.** On a CI runner, that means the runner's CPU, not yours.

## Footnote: what x86-64-v3 buys in a kernel

x86-64-v3 is the microarchitecture level that adds AVX, AVX2, BMI1/2, FMA, LZCNT and MOVBE: Intel Haswell and AMD Excavator or later. The kernel, though, compiles with `-mno-sse -mno-sse2 -mno-avx` (`arch/x86/Makefile`), because it doesn't save vector registers on every entry. So `-march=x86-64-v3` only enables the scalar extensions.

Compiling `kernel/sched/fair.o` both ways showed the effect. The v3 build contained 11 BMI/LZCNT/MOVBE instructions, against none in the generic build. Neither build used an AVX register, and the code size was the same. Hand-written AVX code, such as `crypto/` and RAID6, already chooses its code path at runtime in the stock kernel. Expect a small gain, if any; the real v3 gains are in user space, such as Ubuntu's `amd64v3` package variants or RHEL 10's v3 baseline.

A v3 kernel also won't boot on a CPU without those instructions. `/lib64/ld-linux-x86-64.so.2 --help | grep x86-64-v3` shows whether a machine qualifies (`supported, searched`).

## Sources

- GitHub Docs: [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) and [limits](https://docs.github.com/en/actions/reference/limits).
- [microsoft/WSL2-Linux-Kernel](https://github.com/microsoft/WSL2-Linux-Kernel) at `linux-msft-wsl-6.18.40.1`:
  - `Documentation/kbuild/kbuild.rst` (`KCFLAGS`);
  - `arch/x86/Makefile` (`-mno-avx`, `-march`);
  - `arch/x86/Kconfig.cpu` (`X86_NATIVE_CPU`).
- Microsoft Learn: [the `kernel` setting in .wslconfig](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).
- The build and both failures above were reproduced locally with GCC 15.3.
