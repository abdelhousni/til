# Running Linux containers on Windows with wslc, the container CLI built into WSL

WSL 2 (*Windows Subsystem for Linux*) runs a real Linux kernel in a lightweight virtual machine on Windows. A newer WSL release adds `wslc.exe`, a container command line that ships with WSL itself: no Docker Desktop or separate engine to install. A *container* is a process isolated from the rest of the system, started from an *image*, a packaged filesystem with an app and what it needs. Commands below are from Microsoft Learn (*Get started with containers on WSL*) and run in PowerShell. They weren't run here, since this environment has no Windows.

## Install and verify

`wslc` needs WSL 2.9.3 or higher:

```powershell
wsl --update
wsl --version        # 2.9.3 or higher
wslc version
wslc run --rm hello-world
```

`wslc run` pulls the image if it isn't local, like `docker run` ([the same smoke test](../podman/docker-and-podman-hello-world.md) with Docker or Podman).

## Run containers

```powershell
wslc run --rm -it ubuntu:latest bash -c "echo hello"   # throwaway container
wslc run -d --rm -p 8080:80 --name web nginx           # background, host port 8080 to container port 80
curl localhost:8080
wslc container list                                    # add --all for stopped ones
wslc exec web cat /etc/os-release                      # run a command inside
wslc container stop web                                # --rm removes it once stopped
```

The port is published to Windows, so `localhost:8080` works from a Windows browser.

## Build your own image

Put a `Containerfile` (Docker's `Dockerfile`) at the project root, keep the project on the Linux file system rather than under `/mnt/c` (Microsoft's note: much faster file access), then:

```powershell
wslc build -t myapp .
wslc image list
wslc run -d --rm -p 8000:8000 --name myapp myapp
wslc container logs myapp
wslc exec myapp uname        # Linux
wslc container stop myapp
```

## Inspect and clean up

```powershell
wslc container inspect <id>
wslc container logs <id>
wslc image inspect <image>
wslc stats                   # resource use of running containers
wslc container prune         # remove stopped containers
wslc image prune             # remove unused images
```

`wslc --help` and `wslc <command> --help` list the rest. The commands mirror Docker's: `run`, `exec`, `build`, with `container` and `image` subcommands.

## Sources

- Microsoft Learn: [Get started with containers on WSL](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers), from [MicrosoftDocs/wsl](https://github.com/MicrosoftDocs/wsl), fetched 2026-10-06.
- Not tested: the commands come from that page, and `wslc` isn't available on Linux.
