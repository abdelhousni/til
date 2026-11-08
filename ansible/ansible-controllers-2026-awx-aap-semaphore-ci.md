# Ansible controllers in 2026: AWX paused, AAP, Semaphore UI, or plain CI

Second entry in the Running IaC and CaC from a controller series. [The first entry](control-node-runner-controller-tower-awx-aap.md) separated the three roles: the *control node* runs `ansible-playbook`; a *runner* runs CI jobs; a *controller* is a service that stores projects, inventories, credentials and templates, launches runs and keeps their history. This one compares the four ways a team can run its Ansible centrally today, and runs one of them, Semaphore UI, against a playbook kept in GitLab.

## The four options

| | Plain GitLab CI | AWX | AAP | Semaphore UI |
|---|---|---|---|---|
| What it is | a pipeline job runs `ansible-playbook`, usually in an execution environment | the open-source upstream of AAP's controller | Red Hat's supported product: controller, automation hub, Event-Driven Ansible | an independent open-source web interface for Ansible, OpenTofu/Terraform, Bash and PowerShell |
| Licence | GitLab CE: MIT | Apache 2.0 | Red Hat subscription | MIT |
| Latest release | GitLab and GitLab Runner release monthly | 24.6.1, 2 July 2024; releases paused | 2.6, with patch releases into 2026 | 2.19.17, used here |
| Runs on | any runner (Docker, Kubernetes, shell…) | Kubernetes, through the AWX operator | RHEL with Podman (containerized installer), OpenShift (operator) or RPM (deprecated) | one container with SQLite, or with MySQL or PostgreSQL |
| Credentials | CI/CD variables, or an external secrets manager | encrypted credential store | encrypted credential store | key store |
| Who may run what | GitLab project roles, protected branches and environments | organisations, teams, role-based access | same as AWX, behind the platform gateway | projects and project roles |
| History of runs | pipelines and job logs | jobs, with per-task events | same as AWX | tasks with their log and the commit they ran |
| ansible-core version | whatever the job's image or EE contains | the EE chosen per template | the EE chosen per template | the one bundled in its image, unless you build your own |

*CI/CD variables* are values GitLab passes to jobs as environment variables, optionally masked in logs or limited to protected branches. An *external secrets manager* is a separate service, such as HashiCorp Vault, that jobs ask for secrets at run time.

## AWX: code still moving, nothing released

The AWX README now opens with a caution: *"The last release of this repository was released on Jul 2, 2024. Releases of this project are now paused during a large scale refactoring"*, and points to the forum posts on refactoring AWX into a *"pluggable, service-oriented architecture"* ([ansible/awx](https://github.com/ansible/awx)). The `devel` branch keeps changing, and the Ansible forum has a thread asking whether AWX has a future ([Is there a future for AWX?](https://forum.ansible.com/t/is-there-a-future-for-awx/44527)). As of October 2026, no release date has been announced.

What that means for a team starting today: installing AWX means installing 24.6.1, through the AWX operator, on Kubernetes, and every fix made since July 2024 exists only in unreleased code. Teams already on AWX keep a working controller; teams choosing one now are choosing a version more than two years old. That is why this series doesn't run AWX in its lab.

## AAP: the supported controller

AAP is what AWX becomes once Red Hat packages and supports it. Since AAP 2.5 (October 2024), a *platform gateway* handles login and access for all of its services in one interface, and a containerized installer deploys it on RHEL with Podman ([AAP 2.5 release notes](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html-single/release_notes/index)). The 2.6 documentation lists patch releases into 2026 ([AAP 2.6 release notes](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.6/html-single/release_notes/index)). It needs a Red Hat subscription, and Red Hat offers a time-limited trial.

A controller with a web interface invites changes made by clicking, which Git never sees. Red Hat's Communities of Practice (CoP), in their [automation good practices](https://github.com/redhat-cop/automation-good-practices/blob/main/aap_configuration/README.adoc), ask for the opposite: *"All AAP objects -- organizations, teams, credentials, projects, inventories, job templates, workflow templates, execution environments, schedules, and settings -- should be defined as YAML data in a Git repository"*, with *"no manual changes"* through the interface, applied *"through CI/CD pipelines, not manually"*. The CoP's collection for this is [`infra.aap_configuration`](https://github.com/redhat-cop/infra.aap_configuration) for AAP 2.5 and later; `infra.controller_configuration` covers AAP 2.4 and earlier. Done that way, a controller is configured by a pipeline like any other system, and the interface is for launching and reading runs. This series describes AAP from Red Hat's documentation and doesn't run it; the inventory series' [AAP entry](inventory-in-aap-sources-smart-constructed.md) covers how its inventories work.

## Semaphore UI, run against GitLab

Semaphore UI organises work in *projects*. Its [README](https://github.com/semaphoreui/semaphore) lists what a project holds: *task templates*, *schedules*, *inventories* and *variable groups*; running a template creates a *task*. A project also has a *key store* for credentials and a list of *repositories*, the Git URLs its templates run from. Example [`02-semaphore-from-gitlab`](https://github.com/abdelhousni/iac-controller-series/tree/main/02-semaphore-from-gitlab) sets this up through Semaphore's API against the lab's GitLab CE 19.5.1:

1. `site.yml` goes into a **private** GitLab project.
2. GitLab creates a *project access token*, a token tied to one project rather than to a person, with the Reporter role and only the `read_repository` scope, valid for one day.
3. Semaphore gets that token as a `login_password` key, a repository `http://gitlab/root/ctl-02.git` that uses it, a static inventory (`semaphore-container`, the Semaphore container itself), a variable group setting `ansible_connection: local`, and a template for `site.yml` on branch `main`.
4. The template runs, and the script prints what the task reported.

The playbook prints the ansible-core version it ran with:

```yaml
- name: Show the ansible-core version Semaphore used
  ansible.builtin.debug:
    msg: >-
      ansible-core {{ ansible_version.full }} ran site.yml
      for {{ inventory_hostname }}
    verbosity: 0
```

The output, from Semaphore UI 2.19.17:

```text
Semaphore task: success
Commit run: site.yml for Semaphore UI
Cloning Repository http://gitlab/root/ctl-02.git
No <repo>/collections/requirements.yml file found. Skip galaxy install process.
No <repo>/requirements.yml file found. Skip galaxy install process.
No <repo>/roles/requirements.yml file found. Skip galaxy install process.
msg: ansible-core 2.20.10 ran site.yml for semaphore-container
semaphore-container : ok=1 changed=0 unreachable=0 failed=0 skipped=0 rescued=0 ignored=0
```

Three things in it:

- **Each task clones the repository** and records the commit it ran, so a run in the history points at a commit in Git.
- **Semaphore installs collections and roles itself** when it finds a `requirements.yml` in `collections/`, `roles/` or the repository root, with `ansible-galaxy` at run time. The versions installed are whatever that file allows on the day.
- **The ansible-core version is Semaphore's**, 2.20.10, the one bundled in the `semaphoreui/semaphore:v2.19.17` image, not one chosen by the project. Upgrading Semaphore upgrades Ansible for every project at once. An execution environment, which AWX and AAP select per template and a CI job selects with its image, pins it per project instead. [Building an EE from a locked requirements file](execution-environment-from-a-locked-requirements-file.md) shows how.

## Plain CI: the pipeline as the controller

Without a controller, a GitLab pipeline does the controller's work: the project holds the playbooks, the job's image is the execution environment, CI/CD variables hold the secrets, pipeline schedules replace job schedules, and the pipeline list is the history of runs, each tied to a commit and to whoever merged it. What's missing is anything outside Git: there is no inventory or credential screen, and running a playbook means running a pipeline. Later entries in this series build that setup step by step.

## What decides between them

These questions separate the options more than feature lists do:

- **Who launches runs?** If only people who already merge to Git do, the pipeline is enough. If others need a button with a form (a help desk restarting a service, an application team deploying), a controller gives them that without giving them Git.
- **Can you run Kubernetes or pay for AAP?** AWX needs Kubernetes; AAP needs a subscription; Semaphore UI and GitLab CI run in plain containers.
- **Who chooses the ansible-core version?** Per project with an EE (CI, AWX, AAP), or once for the whole server (Semaphore UI's bundled one, unless you build your own image).
- **Must every change go through a merge request?** A pipeline on a protected branch runs only what was merged. A controller runs whatever its projects and templates point at, so the same guarantee needs two things: its objects defined in Git and applied by a pipeline, as above, and its projects pinned to a release tag rather than a branch. The CoP good practices ask for exactly that: *"Never use 'latest' or branch names in production references"* ([Git workflow](https://github.com/redhat-cop/automation-good-practices/blob/main/git_workflow/README.adoc)). Example 02 runs `main` because it's a lab.

The commands above ran in a Linux container with Docker: GitLab CE 19.5.1, GitLab Runner 19.5.1 and Semaphore UI 2.19.17 from the companion repository's lab. AWX and AAP were not run.
