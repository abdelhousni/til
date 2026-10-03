# Today I Learned

Things I've learned, collected in [abdelhousni/til](https://github.com/abdelhousni/til). Site pattern and tooling adapted from [simonw/til](https://github.com/simonw/til).

[![Linkedin Badge](https://img.shields.io/badge/abdelhousni-0A66C2?style=flat&logo=Linkedin&logoColor=white&labelColor=0A66C2&link=https://www.linkedin.com/in/abdelhousni/)](https://www.linkedin.com/in/abdelhousni/)

Browse these TILs at https://til.housni.eu/

<!-- count starts -->109<!-- count ends --> TILs so far. <a href="https://til.housni.eu/feed.atom">Atom feed here</a>.

<!-- index starts -->
## ansible

* [Starting an Ansible role project with uv for the venv](https://til.housni.eu/ansible/starting-a-role-with-uv-venv.html) - 2026-09-05
* [Using the Foreman/Satellite dynamic inventory plugin](https://til.housni.eu/ansible/foreman-dynamic-inventory-plugin.html) - 2026-09-05
* [Targeting hosts the same way, whether the inventory is static or dynamic](https://til.housni.eu/ansible/targeting-hosts-static-and-dynamic-inventory.html) - 2026-09-05
* [Storing an Ansible Galaxy token as an environment variable, not in ansible.cfg](https://til.housni.eu/ansible/galaxy-token-as-environment-variable.html) - 2026-09-05
* [git tag basics, grounded in how Ansible collection releases actually use them](https://til.housni.eu/ansible/git-tag-basics-collection-releases.html) - 2026-09-12
* [Deploying a Podman Quadlet stack on RHEL9 with linux-system-roles](https://til.housni.eu/ansible/podman-quadlet-caddy-adminer-php-linux-system-roles.html) - 2026-09-16
* [Ansible Vault encrypts the secret in git; Podman's default driver stores it in plaintext](https://til.housni.eu/ansible/ansible-vault-podman-secrets.html) - 2026-09-20
* [What Ansible Vault actually encrypts, and where that protection stops](https://til.housni.eu/ansible/what-ansible-vault-actually-encrypts.html) - 2026-09-24
* [Handling deployment failures with Ansible's block/rescue/always](https://til.housni.eu/ansible/block-rescue-always-error-handling.html) - 2026-09-29
* [Locking an Ansible development environment: pip, venv, pip-tools, uv or an execution environment](https://til.housni.eu/ansible/locking-an-ansible-dev-environment-pip-to-ee.html) - 2026-09-29
* [Pinning ansible-core with pip-tools, uv and Poetry](https://til.housni.eu/ansible/pinning-ansible-core-pip-tools-uv-poetry.html) - 2026-09-29
* [Building an Ansible execution environment from a locked requirements file](https://til.housni.eu/ansible/execution-environment-from-a-locked-requirements-file.html) - 2026-09-29
* [Where to run an Ansible development environment: venv, Dev Container, Remote-SSH, code-server or Dev Spaces](https://til.housni.eu/ansible/where-to-run-an-ansible-dev-environment.html) - 2026-09-29
* [Ansible Development Tools (ADT): one install, and the Python version decides what you get](https://til.housni.eu/ansible/ansible-development-tools-adt.html) - 2026-09-29
* [Committing the VS Code Ansible settings with the repository](https://til.housni.eu/ansible/vscode-ansible-settings-per-repository.html) - 2026-09-29
* [Running playbooks locally in the execution environment production uses](https://til.housni.eu/ansible/develop-against-the-production-execution-environment.html) - 2026-09-30
* [An Ansible Dev Container: choosing the scaffolded config, Podman, and the EE navigator falls back to](https://til.housni.eu/ansible/ansible-dev-container-with-adt.html) - 2026-09-30
* [A shared Ansible dev server for VS Code Remote-SSH, built with Ansible](https://til.housni.eu/ansible/shared-dev-server-for-vscode-remote-ssh.html) - 2026-09-30
* [Linting Ansible before it reaches Git: `--fix` in the editor, the same ansible-lint in CI](https://til.housni.eu/ansible/ansible-lint-fix-in-the-editor-and-in-ci.html) - 2026-09-30
* [Scaffolding with ansible-creator: roles inside a collection, and what to change in the output](https://til.housni.eu/ansible/scaffolding-with-ansible-creator.html) - 2026-09-30
* [A collection-aware venv with ansible-dev-environment (ade): what it installs, what it edits, and how to pin it](https://til.housni.eu/ansible/collection-venv-with-ansible-dev-environment.html) - 2026-09-30
* [One sudoers line per command with community.general.dict_kv: building a list of dicts from a list of values](https://til.housni.eu/ansible/readable-sudoers-with-dict-kv.html) - 2026-10-01
* [Lists and dicts back and forth: dict2items, items2dict and zip on role, Foreman and Proxmox data](https://til.housni.eu/ansible/lists-and-dicts-dict2items-items2dict-zip.html) - 2026-10-01
* [Merging dicts with combine: PostgreSQL settings in layers, Quadlet units from a base](https://til.housni.eu/ansible/combine-recursive-list-merge-postgresql-quadlets.html) - 2026-10-01
* [Picking from a list of dicts: selectattr, rejectattr and map on Proxmox guests and host facts](https://til.housni.eu/ansible/selectattr-rejectattr-map-proxmox-guests-and-facts.html) - 2026-10-02
* [subelements versus product: Quadlet volume directories and PostgreSQL pg_hba rules](https://til.housni.eu/ansible/subelements-versus-product-quadlet-volumes-pg-hba.html) - 2026-10-02
* [Set operations on lists: declared Proxmox guests against the cluster, and why the order changes between runs](https://til.housni.eu/ansible/set-operations-union-difference-proxmox-drift.html) - 2026-10-02
* [Strings into structures: df with split and regex_findall, findmnt with from_json](https://til.housni.eu/ansible/strings-into-structures-df-findmnt-from-json.html) - 2026-10-02
* [default, default(omit), mandatory and ternary: sudo rules that don't set every field](https://til.housni.eu/ansible/default-omit-mandatory-ternary-sudo-rules.html) - 2026-10-02
* [Forcing types: extra vars arrive as strings, and ansible-core 2.19 stopped guessing](https://til.housni.eu/ansible/forcing-types-extra-vars-conditionals.html) - 2026-10-02
* [Writing data out: a Caddy JSON configuration with to_nice_json, sort_keys and indent](https://til.housni.eu/ansible/writing-data-out-to-nice-json-caddy.html) - 2026-10-03
* [Data from other hosts: pg_hba rules from the app servers' facts, with hostvars and extract](https://til.housni.eu/ansible/data-from-other-hosts-extract-hostvars-pg-hba.html) - 2026-10-03
* [groupby, groupby_as_dict and lists_mergeby: Proxmox guests by node, and joined to what the team declares](https://til.housni.eu/ansible/groupby-lists-mergeby-proxmox-guests.html) - 2026-10-03
* [json_query or native filters: part 4's Proxmox selections written in JMESPath](https://til.housni.eu/ansible/json-query-jmespath-versus-native-filters.html) - 2026-10-03
* [Network data with ansible.utils: checking pg_hba subnets and numbering Proxmox guests](https://til.housni.eu/ansible/ansible-utils-ipaddr-pg-hba-subnets-proxmox.html) - 2026-10-03
* [set_fact in a loop or one expression: part 11's pg_hba rules, built both ways](https://til.housni.eu/ansible/set-fact-loop-or-one-expression-pg-hba.html) - 2026-10-03
* [Text on lists: building a systemd ExecStart line with regex_replace, join and replace](https://til.housni.eu/ansible/execstart-lines-regex-replace-join-systemd.html) - 2026-10-03
* [Hosts and groups: the two groups every inventory has, all and ungrouped](https://til.housni.eu/ansible/inventory-hosts-groups-all-ungrouped.html) - 2026-10-03
* [An inventory as a directory: a hosts file without variables, and group_vars per role](https://til.housni.eu/ansible/inventory-directory-group-vars-per-role.html) - 2026-10-03

## github-pages

* [Publishing a TIL collection as a static GitHub Pages site](https://til.housni.eu/github-pages/static-site-instead-of-datasette.html) - 2026-09-05
* [Adding an Atom feed and syntax highlighting to a static site build script](https://til.housni.eu/github-pages/atom-feed-and-syntax-highlighting.html) - 2026-09-05
* [Rendering Mermaid diagrams in a Python-Markdown static site](https://til.housni.eu/github-pages/mermaid-diagrams-in-markdown.html) - 2026-09-12

## gitlab-ci

* [A simple GitLab CI pipeline for ansible-lint on a custom Python image](https://til.housni.eu/gitlab-ci/ansible-lint-custom-python-image.html) - 2026-09-05

## http

* [Getting a remote file's properties with curl, without downloading it](https://til.housni.eu/http/curl-remote-file-properties-without-downloading.html) - 2026-09-05

## podman

* [Hosting a simple PHP page with Podman + Caddy, with automatic HTTPS](https://til.housni.eu/podman/caddy-php-fpm-automatic-https.html) - 2026-09-05
* [Moving a container image between hosts with podman save + scp + load, no registry](https://til.housni.eu/podman/save-scp-load-image-between-hosts.html) - 2026-09-05
* [Sanity-checking a fresh Docker or Podman install with each engine's own hello-world](https://til.housni.eu/podman/docker-and-podman-hello-world.html) - 2026-09-06
* [Podman equivalents to Docker's Dive image-layer explorer](https://til.housni.eu/podman/podman-equivalent-to-docker-dive.html) - 2026-09-12
* [Root vs rootless Podman on RHEL 10 and Ubuntu 26.04](https://til.housni.eu/podman/root-vs-rootless-rhel10-ubuntu2604.html) - 2026-09-13
* [Auto-updating the Caddy/Adminer/PHP Quadlet stack needs more than one AutoUpdate key](https://til.housni.eu/podman/quadlet-autoupdate-caddy-adminer-php.html) - 2026-09-21
* [Pointing Podman at an Artifactory mirror without editing a single image name](https://til.housni.eu/podman/artifactory-as-a-pull-through-mirror.html) - 2026-09-21

## proxmox

* [Installing a RIPE Atlas software probe in a Proxmox LXC](https://til.housni.eu/proxmox/ripe-atlas-software-probe-lxc.html) - 2026-09-05
* [Injecting qemu-guest-agent into an Ubuntu cloud template, from the CLI](https://til.housni.eu/proxmox/inject-qemu-guest-agent-ubuntu-template.html) - 2026-09-07
* [A libvirt RHEL Kickstart example ported to Proxmox, minus the one flag with no equivalent](https://til.housni.eu/proxmox/rhel-kickstart-libvirt-example-ported.html) - 2026-09-20
* [Debugging a Proxmox VM whose cloud-init config didn't apply](https://til.housni.eu/proxmox/debugging-cloud-init-on-first-boot.html) - 2026-09-20
* [A Proxmox VM on demand, NixOS from Git: OpenTofu builds a skeleton, nixos-anywhere replaces it, and the host key exists before the VM](https://til.housni.eu/proxmox/nixos-on-demand-opentofu-nixos-anywhere-sops.html) - 2026-09-27

## python

* [A regex link checker breaks on the exact HTML it was meant to check](https://til.housni.eu/python/regex-vs-htmlparser-for-dead-links.html) - 2026-09-05
* [Getting a newer Python on RHEL without touching the system python3](https://til.housni.eu/python/newer-python-with-uv-without-touching-system-python-rhel.html) - 2026-09-29

## seo

* [Don't hand-write a sitemap.xml, generate it from data you already have](https://til.housni.eu/seo/generating-a-sitemap-from-existing-data.html) - 2026-09-05
* [robots.txt for a small static site is basically a pointer to the sitemap](https://til.housni.eu/seo/robots-txt-is-mostly-just-pointing-at-the-sitemap.html) - 2026-09-05
* [A schema.org Person block is what actually helps you rank for your own name](https://til.housni.eu/seo/schema-org-person-for-name-search.html) - 2026-09-05
* [Verifying a GitHub Pages site with Bing Webmaster Tools (no DNS needed)](https://til.housni.eu/seo/verifying-a-github-pages-site-with-bing.html) - 2026-09-05

## tls

* [Checking a TLS certificate's dates, issuer, and SANs with openssl](https://til.housni.eu/tls/openssl-checking-cert-dates-and-details.html) - 2026-09-05
* [Splitting a .pfx into a certificate, key, and CA chain with openssl](https://til.housni.eu/tls/splitting-pfx-into-pem-crt-and-ca-chain.html) - 2026-09-05
* [Adding a certificate to a Java keystore/truststore with keytool](https://til.housni.eu/tls/keytool-import-certificate-java-truststore.html) - 2026-09-05

## cloud-init

* [Layering extra cloud-init config without fighting Terraform/OpenTofu's auto-generated user-data](https://til.housni.eu/cloud-init/vendor-data-alongside-terraform-user-data.html) - 2026-09-07

## git

* [Installing git, gh, and glab, and the auth each one actually needs](https://til.housni.eu/git/git-gh-glab-install-and-auth.html) - 2026-09-12
* [Syncing a diverged fork: take the pipeline fixes, not the content](https://til.housni.eu/git/sync-a-diverged-fork-without-its-content.html) - 2026-09-27
* [Configuring a repository for coding agents: what the guidance actually says](https://til.housni.eu/git/repo-guardrails-for-coding-agents.html) - 2026-09-27
* [A branch you fetched was force-pushed: keep the old tip, then `rebase --onto`](https://til.housni.eu/git/resync-clone-after-force-push.html) - 2026-09-27

## oauth2

* [GitLab with OAuth 2.0 / OIDC — the simple principle](https://til.housni.eu/oauth2/gitlab-oauth2-oidc-principle.html) - 2026-09-12

## kubernetes

* [What Kubernetes actually is, and how it works](https://til.housni.eu/kubernetes/what-is-kubernetes-and-how-it-works.html) - 2026-09-17
* [Cleanly stopping an RKE2 node for planned maintenance](https://til.housni.eu/kubernetes/rke2-node-maintenance-drain-reboot.html) - 2026-09-17
* [Installing a single-node RKE2 server for a lab](https://til.housni.eu/kubernetes/rke2-single-node-lab-install.html) - 2026-09-18
* [Getting kubectl to work against RKE2 from off the node](https://til.housni.eu/kubernetes/kubectl-off-node-rke2-tls-san.html) - 2026-09-18
* [What RKE2 actually is, and how its pieces fit together](https://til.housni.eu/kubernetes/what-is-rke2-and-how-it-works.html) - 2026-09-18
* [Pods, Deployments, Services — the minimum object model](https://til.housni.eu/kubernetes/pods-deployments-services-object-model.html) - 2026-09-18
* [RKE2's default CNI is Canal, and you pick it before the first start](https://til.housni.eu/kubernetes/rke2-cni-canal-and-alternatives.html) - 2026-09-18
* [RKE2 ships no default StorageClass, and a PVC will sit Pending forever](https://til.housni.eu/kubernetes/rke2-no-default-storageclass.html) - 2026-09-18
* [RKE2's ingress default moved to Traefik, because ingress-nginx is ending](https://til.housni.eu/kubernetes/rke2-ingress-traefik-nginx-retirement.html) - 2026-09-18
* [Going HA with RKE2: three servers, one address, and the datastore choice](https://til.housni.eu/kubernetes/rke2-ha-embedded-etcd-external-datastore.html) - 2026-09-18
* [RKE2's etcd snapshots run on schedule, but a fresh cluster starts with none](https://til.housni.eu/kubernetes/rke2-etcd-snapshot-restore-drill.html) - 2026-09-19
* [Restoring RKE2 etcd across an HA cluster, and backing snapshots up to S3](https://til.housni.eu/kubernetes/rke2-etcd-ha-restore-and-s3-backup.html) - 2026-09-20
* [RKE2 leaves its servers schedulable, so your workloads have been running on the control plane all along](https://til.housni.eu/kubernetes/rke2-node-scheduling-labels-taints-tolerations.html) - 2026-09-20

## packer

* [What Packer actually is, and how it works](https://til.housni.eu/packer/what-is-packer-and-how-it-works.html) - 2026-09-17
* [Kickstart, cloud-init and Image Builder are three layers, not three choices](https://til.housni.eu/packer/rhel-template-kickstart-cloud-init-image-builder.html) - 2026-09-20

## ssh

* [Useful ~/.ssh/config patterns for IaC-provisioned hosts](https://til.housni.eu/ssh/ssh-config-patterns-for-iac.html) - 2026-09-17

## terraform

* [What Terraform/OpenTofu actually is, and how it works](https://til.housni.eu/terraform/what-is-terraform-opentofu-and-how-it-works.html) - 2026-09-17
* [What Terraform/OpenTofu, Nomad, and Packer are, and how they relate](https://til.housni.eu/terraform/terraform-opentofu-nomad-packer-how-they-relate.html) - 2026-09-17
* [Terraform state locking just dropped its DynamoDB requirement](https://til.housni.eu/terraform/state-locking-inspection-refactoring-drift.html) - 2026-09-23
* [What Terraform, OpenTofu, and Packer promise about secrets, and where each promise stops](https://til.housni.eu/terraform/what-terraform-opentofu-and-packer-promise-about-secrets.html) - 2026-09-29

## apache

* [A conditional redirect that skips one path, on Apache 2.2 through 2.4](https://til.housni.eu/apache/conditional-redirect-exclude-one-path.html) - 2026-09-18

## linux

* [What cgroups v2 actually is, and how Podman and Kubernetes use it](https://til.housni.eu/linux/cgroups-v2-podman-kubernetes.html) - 2026-09-18
* [Building a custom WSL2 kernel on GitHub Actions: `KCFLAGS`, not `CFLAGS`](https://til.housni.eu/linux/wsl2-kernel-on-github-actions.html) - 2026-09-28
* [Checking new firewall rules with nc and Python: open, refused, or dropped](https://til.housni.eu/linux/check-firewall-rules-with-nc-and-python.html) - 2026-09-29
* [Sudo rules that hand out a root shell, and a CI check that refuses them](https://til.housni.eu/linux/sudo-rules-that-hand-out-a-root-shell.html) - 2026-10-01

## windows

* [Finding and force-closing a locked file on a Windows SMB share](https://til.housni.eu/windows/close-open-smb-files-powershell.html) - 2026-09-18
* [RDP into Windows 11 with a Microsoft account: the password, not the PIN, and `MicrosoftAccount\`](https://til.housni.eu/windows/rdp-microsoft-account-login.html) - 2026-09-28
* [Oh My Posh in PowerShell and in WSL2 zsh, with one config file](https://til.housni.eu/windows/oh-my-posh-pwsh-and-wsl-zsh.html) - 2026-09-28
* [Installing PowerShell 7 on Windows, Debian and RHEL, the way Microsoft documents it](https://til.housni.eu/windows/install-powershell-7-windows-debian-rhel.html) - 2026-09-29

## vscode

* [Pointing VS Code's Dev Containers extension at Podman](https://til.housni.eu/vscode/dev-containers-podman-instead-of-docker.html) - 2026-09-19

## nixos

* [First steps on NixOS: the whole system is one file, and every change is a boot entry](https://til.housni.eu/nixos/first-steps-configuration-generations-rollback.html) - 2026-09-25
* [NixOS on WSL2: a short admin runbook, and the files WSL manages instead of NixOS](https://til.housni.eu/nixos/nixos-wsl-admin-runbook.html) - 2026-09-25
* [Oh My Zsh on NixOS: the plugin list installs nothing, and NixOS aliases win](https://til.housni.eu/nixos/zsh-oh-my-zsh-declarative.html) - 2026-09-26
* [Testing a NixOS configuration on GitHub Actions: evaluate on every push, boot it where KVM is](https://til.housni.eu/nixos/nixos-config-tests-github-actions.html) - 2026-09-26
* [Testing a NixOS configuration on self-managed GitLab CE: the eval job runs anywhere, the VM test needs a runner you prepare](https://til.housni.eu/nixos/nixos-config-tests-gitlab-ce.html) - 2026-09-26
* [Home Manager as a NixOS module: dotfiles in the same rebuild, and the file that's in the way](https://til.housni.eu/nixos/home-manager-nixos-module.html) - 2026-09-27
* [A user's PATH on NixOS: declare packages, and know which settings reach services](https://til.housni.eu/nixos/user-path-packages-shells-services.html) - 2026-09-28

## claude-code

* [Starting with Jev in Claude Code: a plugin that adds a skill, and an API key for experiments](https://til.housni.eu/claude-code/typesafe-jev-plugin.html) - 2026-09-29
<!-- index ends -->

---

## Running the site locally

The published site is built by [`.github/workflows/publish.yml`](.github/workflows/publish.yml) running three scripts and uploading `_site/`. The `Makefile` runs the same three, in the same order, so a clean `make preflight` locally means a clean deploy.

```bash
git clone https://github.com/abdelhousni/til.git    # not --depth 1, see below
cd til
make serve            # creates .venv, installs deps, builds, serves on :8000
```

| target | what it does |
| --- | --- |
| `make help` | list these targets |
| `make venv` | create `.venv` and install `requirements.txt` |
| `make build` | build the site into `_site/` |
| `make serve` | build, then serve on `localhost:8000` (`make serve PORT=9000` to move it) |
| `make check` | build + internal link check, fast |
| `make check-external` | build + external link check, slow — this one is the deploy gate |
| `make readme` | regenerate the index in this README |
| `make preflight` | everything CI runs, in CI's order |
| `make clean` / `clean-all` | drop `_site/`, and `.venv/` too |

Two things worth knowing, both of which produce *wrong output* rather than an error, which is why `make` checks for them:

- **Clone with full history.** Entry dates come from `git log --follow --diff-filter=A`, so a `--depth 1` clone dates every entry `unknown` and scrambles the ordering. CI sets `fetch-depth: 0` for the same reason.
- **Commit before you build.** An uncommitted `.md` file has no history to read a creation date from, so it renders as `unknown` and leaks into the README index if you regenerate it.

Serve `_site/` rather than opening it with `file://`. Internal links are all relative, so the locally-served copy behaves exactly like the `/til/` subpath in production — but Mermaid diagrams load as an ES module from a CDN, which a `file://` origin blocks. Canonical URLs, `sitemap.xml` and `feed.atom` always point at the production host; that is expected locally.
