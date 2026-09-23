# Today I Learned

Things I've learned, collected in [abdelhousni/til](https://github.com/abdelhousni/til). Site pattern and tooling adapted from [simonw/til](https://github.com/simonw/til).

[![Linkedin Badge](https://img.shields.io/badge/abdelhousni-0A66C2?style=flat&logo=Linkedin&logoColor=white&labelColor=0A66C2&link=https://www.linkedin.com/in/abdelhousni/)](https://www.linkedin.com/in/abdelhousni/)

Browse these TILs at https://abdelhousni.github.io/til/

<!-- count starts -->58<!-- count ends --> TILs so far. <a href="https://abdelhousni.github.io/til/feed.atom">Atom feed here</a>.

<!-- index starts -->
## ansible

* [Using the Foreman/Satellite dynamic inventory plugin](https://abdelhousni.github.io/til/ansible/foreman-dynamic-inventory-plugin.html) - 2026-09-05
* [Storing an Ansible Galaxy token as an environment variable, not in ansible.cfg](https://abdelhousni.github.io/til/ansible/galaxy-token-as-environment-variable.html) - 2026-09-05
* [Starting an Ansible role project with uv for the venv](https://abdelhousni.github.io/til/ansible/starting-a-role-with-uv-venv.html) - 2026-09-05
* [Targeting hosts the same way, whether the inventory is static or dynamic](https://abdelhousni.github.io/til/ansible/targeting-hosts-static-and-dynamic-inventory.html) - 2026-09-05
* [git tag basics, grounded in how Ansible collection releases actually use them](https://abdelhousni.github.io/til/ansible/git-tag-basics-collection-releases.html) - 2026-09-12
* [Deploying a Podman Quadlet stack on RHEL9 with linux-system-roles](https://abdelhousni.github.io/til/ansible/podman-quadlet-caddy-adminer-php-linux-system-roles.html) - 2026-09-16
* [Ansible Vault encrypts the secret in git; Podman's default driver stores it in plaintext](https://abdelhousni.github.io/til/ansible/ansible-vault-podman-secrets.html) - 2026-09-20

## github-pages

* [Adding an Atom feed and syntax highlighting to a static site build script](https://abdelhousni.github.io/til/github-pages/atom-feed-and-syntax-highlighting.html) - 2026-09-05
* [Publishing a TIL collection as a static GitHub Pages site](https://abdelhousni.github.io/til/github-pages/static-site-instead-of-datasette.html) - 2026-09-05
* [Rendering Mermaid diagrams in a Python-Markdown static site](https://abdelhousni.github.io/til/github-pages/mermaid-diagrams-in-markdown.html) - 2026-09-12

## gitlab-ci

* [A simple GitLab CI pipeline for ansible-lint on a custom Python image](https://abdelhousni.github.io/til/gitlab-ci/ansible-lint-custom-python-image.html) - 2026-09-05

## http

* [Getting a remote file's properties with curl, without downloading it](https://abdelhousni.github.io/til/http/curl-remote-file-properties-without-downloading.html) - 2026-09-05

## podman

* [Hosting a simple PHP page with Podman + Caddy, with automatic HTTPS](https://abdelhousni.github.io/til/podman/caddy-php-fpm-automatic-https.html) - 2026-09-05
* [Moving a container image between hosts with podman save + scp + load, no registry](https://abdelhousni.github.io/til/podman/save-scp-load-image-between-hosts.html) - 2026-09-05
* [Sanity-checking a fresh Docker or Podman install with each engine's own hello-world](https://abdelhousni.github.io/til/podman/docker-and-podman-hello-world.html) - 2026-09-06
* [Podman equivalents to Docker's Dive image-layer explorer](https://abdelhousni.github.io/til/podman/podman-equivalent-to-docker-dive.html) - 2026-09-12
* [Root vs rootless Podman on RHEL 10 and Ubuntu 26.04](https://abdelhousni.github.io/til/podman/root-vs-rootless-rhel10-ubuntu2604.html) - 2026-09-13
* [Pointing Podman at an Artifactory mirror without editing a single image name](https://abdelhousni.github.io/til/podman/artifactory-as-a-pull-through-mirror.html) - 2026-09-21
* [Auto-updating the Caddy/Adminer/PHP Quadlet stack needs more than one AutoUpdate key](https://abdelhousni.github.io/til/podman/quadlet-autoupdate-caddy-adminer-php.html) - 2026-09-21

## proxmox

* [Installing a RIPE Atlas software probe in a Proxmox LXC](https://abdelhousni.github.io/til/proxmox/ripe-atlas-software-probe-lxc.html) - 2026-09-05
* [Injecting qemu-guest-agent into an Ubuntu cloud template, from the CLI](https://abdelhousni.github.io/til/proxmox/inject-qemu-guest-agent-ubuntu-template.html) - 2026-09-07
* [Debugging a Proxmox VM whose cloud-init config didn't apply](https://abdelhousni.github.io/til/proxmox/debugging-cloud-init-on-first-boot.html) - 2026-09-20
* [A libvirt RHEL Kickstart example ported to Proxmox, minus the one flag with no equivalent](https://abdelhousni.github.io/til/proxmox/rhel-kickstart-libvirt-example-ported.html) - 2026-09-20

## python

* [A regex link checker breaks on the exact HTML it was meant to check](https://abdelhousni.github.io/til/python/regex-vs-htmlparser-for-dead-links.html) - 2026-09-05

## seo

* [Don't hand-write a sitemap.xml, generate it from data you already have](https://abdelhousni.github.io/til/seo/generating-a-sitemap-from-existing-data.html) - 2026-09-05
* [robots.txt for a small static site is basically a pointer to the sitemap](https://abdelhousni.github.io/til/seo/robots-txt-is-mostly-just-pointing-at-the-sitemap.html) - 2026-09-05
* [A schema.org Person block is what actually helps you rank for your own name](https://abdelhousni.github.io/til/seo/schema-org-person-for-name-search.html) - 2026-09-05
* [Verifying a GitHub Pages site with Bing Webmaster Tools (no DNS needed)](https://abdelhousni.github.io/til/seo/verifying-a-github-pages-site-with-bing.html) - 2026-09-05

## tls

* [Adding a certificate to a Java keystore/truststore with keytool](https://abdelhousni.github.io/til/tls/keytool-import-certificate-java-truststore.html) - 2026-09-05
* [Checking a TLS certificate's dates, issuer, and SANs with openssl](https://abdelhousni.github.io/til/tls/openssl-checking-cert-dates-and-details.html) - 2026-09-05
* [Splitting a .pfx into a certificate, key, and CA chain with openssl](https://abdelhousni.github.io/til/tls/splitting-pfx-into-pem-crt-and-ca-chain.html) - 2026-09-05

## cloud-init

* [Layering extra cloud-init config without fighting Terraform/OpenTofu's auto-generated user-data](https://abdelhousni.github.io/til/cloud-init/vendor-data-alongside-terraform-user-data.html) - 2026-09-07

## git

* [Installing git, gh, and glab, and the auth each one actually needs](https://abdelhousni.github.io/til/git/git-gh-glab-install-and-auth.html) - 2026-09-12

## oauth2

* [GitLab with OAuth 2.0 / OIDC — the simple principle](https://abdelhousni.github.io/til/oauth2/gitlab-oauth2-oidc-principle.html) - 2026-09-12

## kubernetes

* [Cleanly stopping an RKE2 node for planned maintenance](https://abdelhousni.github.io/til/kubernetes/rke2-node-maintenance-drain-reboot.html) - 2026-09-17
* [What Kubernetes actually is, and how it works](https://abdelhousni.github.io/til/kubernetes/what-is-kubernetes-and-how-it-works.html) - 2026-09-17
* [Getting kubectl to work against RKE2 from off the node](https://abdelhousni.github.io/til/kubernetes/kubectl-off-node-rke2-tls-san.html) - 2026-09-18
* [Pods, Deployments, Services — the minimum object model](https://abdelhousni.github.io/til/kubernetes/pods-deployments-services-object-model.html) - 2026-09-18
* [RKE2's default CNI is Canal, and you pick it before the first start](https://abdelhousni.github.io/til/kubernetes/rke2-cni-canal-and-alternatives.html) - 2026-09-18
* [Going HA with RKE2: three servers, one address, and the datastore choice](https://abdelhousni.github.io/til/kubernetes/rke2-ha-embedded-etcd-external-datastore.html) - 2026-09-18
* [RKE2's ingress default moved to Traefik, because ingress-nginx is ending](https://abdelhousni.github.io/til/kubernetes/rke2-ingress-traefik-nginx-retirement.html) - 2026-09-18
* [RKE2 ships no default StorageClass, and a PVC will sit Pending forever](https://abdelhousni.github.io/til/kubernetes/rke2-no-default-storageclass.html) - 2026-09-18
* [Installing a single-node RKE2 server for a lab](https://abdelhousni.github.io/til/kubernetes/rke2-single-node-lab-install.html) - 2026-09-18
* [What RKE2 actually is, and how its pieces fit together](https://abdelhousni.github.io/til/kubernetes/what-is-rke2-and-how-it-works.html) - 2026-09-18
* [RKE2's etcd snapshots run on schedule, but a fresh cluster starts with none](https://abdelhousni.github.io/til/kubernetes/rke2-etcd-snapshot-restore-drill.html) - 2026-09-19
* [Restoring RKE2 etcd across an HA cluster, and backing snapshots up to S3](https://abdelhousni.github.io/til/kubernetes/rke2-etcd-ha-restore-and-s3-backup.html) - 2026-09-20
* [RKE2 leaves its servers schedulable, so your workloads have been running on the control plane all along](https://abdelhousni.github.io/til/kubernetes/rke2-node-scheduling-labels-taints-tolerations.html) - 2026-09-20

## packer

* [What Packer actually is, and how it works](https://abdelhousni.github.io/til/packer/what-is-packer-and-how-it-works.html) - 2026-09-17
* [Kickstart, cloud-init and Image Builder are three layers, not three choices](https://abdelhousni.github.io/til/packer/rhel-template-kickstart-cloud-init-image-builder.html) - 2026-09-20

## ssh

* [Useful ~/.ssh/config patterns for IaC-provisioned hosts](https://abdelhousni.github.io/til/ssh/ssh-config-patterns-for-iac.html) - 2026-09-17

## terraform

* [What Terraform/OpenTofu, Nomad, and Packer are, and how they relate](https://abdelhousni.github.io/til/terraform/terraform-opentofu-nomad-packer-how-they-relate.html) - 2026-09-17
* [What Terraform/OpenTofu actually is, and how it works](https://abdelhousni.github.io/til/terraform/what-is-terraform-opentofu-and-how-it-works.html) - 2026-09-17
* [Terraform state locking just dropped its DynamoDB requirement](https://abdelhousni.github.io/til/terraform/state-locking-inspection-refactoring-drift.html) - 2026-09-23
* [What Terraform, OpenTofu, and Packer promise about secrets, and where each promise stops](https://abdelhousni.github.io/til/terraform/what-terraform-opentofu-and-packer-promise-about-secrets.html) - 2026-09-23

## apache

* [A conditional redirect that skips one path, on Apache 2.2 through 2.4](https://abdelhousni.github.io/til/apache/conditional-redirect-exclude-one-path.html) - 2026-09-18

## linux

* [What cgroups v2 actually is, and how Podman and Kubernetes use it](https://abdelhousni.github.io/til/linux/cgroups-v2-podman-kubernetes.html) - 2026-09-18

## windows

* [Finding and force-closing a locked file on a Windows SMB share](https://abdelhousni.github.io/til/windows/close-open-smb-files-powershell.html) - 2026-09-18

## vscode

* [Pointing VS Code's Dev Containers extension at Podman](https://abdelhousni.github.io/til/vscode/dev-containers-podman-instead-of-docker.html) - 2026-09-19
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
