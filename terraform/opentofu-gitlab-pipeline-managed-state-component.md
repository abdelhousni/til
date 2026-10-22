# OpenTofu in a GitLab pipeline: GitLab-managed state and the OpenTofu CI/CD component

Fourth entry in the Running IaC and CaC from a controller series. [The first entry](../ansible/control-node-runner-controller-tower-awx-aap.md) set out the roles: a GitLab *runner* picks up a pipeline's jobs, and the machine or container a job runs in does the work. This entry puts OpenTofu in that place. A project's pipeline checks, plans and applies its OpenTofu code, and GitLab keeps the *state*, OpenTofu's record of what it created ([the fundamentals entry](what-is-terraform-opentofu-and-how-it-works.md) explains why it needs one). All of it ran on the series' lab: GitLab CE 19.5.1 and GitLab Runner 19.5.1 in Docker, from the companion repository [abdelhousni/iac-controller-series](https://github.com/abdelhousni/iac-controller-series), example [`04-opentofu-gitlab-state`](https://github.com/abdelhousni/iac-controller-series/tree/main/04-opentofu-gitlab-state).

The GitLab terms used below (*pipeline*, *stage*, *job*, *runner*) are defined in [the GitLab CI entry](../gitlab-ci/ansible-lint-custom-python-image.md). Three more:

- A **CI/CD component** is a reusable piece of pipeline configuration, kept in its own GitLab project and included by version, with *inputs* that set its options.
- A **manual job** waits in the pipeline until someone with the right role starts it.
- A **resource group** makes jobs that share it run one at a time, even across pipelines.

## Two files

The OpenTofu code declares one resource and an empty `http` backend. `terraform_data` is built into OpenTofu, so the example needs no provider to download:

```hcl
terraform {
  required_version = ">= 1.12"

  # GitLab-managed state: the pipeline's gitlab-tofu fills in the address
  # and the credentials (the job token) from CI variables.
  backend "http" {}
}

resource "terraform_data" "release" {
  input = {
    environment = var.environment
    version     = "1.0.0"
  }
}
```

The pipeline is three lines and a list of stages:

```yaml
include:
  - component: $CI_SERVER_FQDN/components/opentofu/validate-plan-apply@4.9.0
    inputs:
      version: 4.9.0
      opentofu_version: 1.12.6

stages: [validate, build, deploy]
```

`validate-plan-apply` is one of the templates of GitLab's [OpenTofu CI/CD component](https://gitlab.com/components/opentofu), version 4.9.0 (31 August 2026). Its jobs run in the component's own image, `registry.gitlab.com/components/opentofu/gitlab-opentofu:4.9.0-opentofu1.12.6-alpine`, which holds `tofu` and a wrapper script, `gitlab-tofu`. The wrapper is what connects OpenTofu to GitLab: its source sets the HTTP backend's address to `$CI_API_V4_URL/projects/$CI_PROJECT_ID/terraform/state/<state name>` and its credentials to the user `gitlab-ci-token` with the password `$CI_JOB_TOKEN`, the short-lived token GitLab gives every job. The `version` input repeats the component's version because, as the template's own comment says, a component can't yet read the version it was included at, and the image tag is built from it.

## On a self-managed GitLab, the component has to be copied in first

`$CI_SERVER_FQDN` is the GitLab instance running the pipeline, so the include looks for `components/opentofu` on that instance. On gitlab.com it exists. On a self-managed GitLab it doesn't, and the component's README says so: *"GitLab CI/CD components are not yet distributed and available on self-managed GitLab instances"*, and an include of `gitlab.com/components/opentofu/…` *"won't work from a self-managed instance"*. Its answer is to mirror the project, at the same path, with a *pull mirror*: a GitLab project that fetches another repository on a schedule.

A pull mirror needs the GitLab server to reach gitlab.com. The lab's GitLab has no internet access, so the example copies the component in by pushing from a clone instead:

```sh
git clone --single-branch --branch main https://gitlab.com/components/opentofu.git
git -C opentofu fetch origin refs/tags/4.9.0:refs/tags/4.9.0
git -C opentofu push -o ci.skip http://<lab-gitlab>/components/opentofu.git main refs/tags/4.9.0
```

`-o ci.skip` matters: the component's repository has its own `.gitlab-ci.yml`, which builds and signs the job images, and a push would otherwise start that pipeline on the lab's runner. Including the component by a release tag (`@4.9.0`) rather than `~latest` is what its README asks for: *"Please make sure to use a released version of this CI/CD component."*

## The pipeline

Run on `main`, after the copy:

```text
Before apply:
  validate / fmt: success
  validate / validate: success
  build / plan: success
  deploy / apply: manual
Plan: 1 to add, 0 to change, 0 to destroy.
Apply: success, Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

- `fmt` and `validate` check the code. `fmt` is allowed to fail by default (the `fmt_allow_failure` input).
- `plan` saves the plan as a job artifact, which `apply` then uses, so what is applied is what was planned.
- `apply` is manual on the default branch, the component's default `apply_rules`. The example starts it through the API (`POST /projects/:id/jobs/:job_id/play`), as a person would with the play button.
- `apply` runs in an *environment* and a *resource group*, both named after the state, `default` here. In GitLab, an environment records what was deployed where and when; the resource group means two pipelines can never apply to the same state at the same time.

## The state GitLab keeps

Each project can hold several named states. Through GitLab's GraphQL API, and the state itself through the REST API:

```text
State default: serial 1, written by job apply, locked: false
Resources: terraform_data.release
Output release: {"environment":"lab","version":"1.0.0"}
```

The *serial* is the state's version number: every write adds one, and GitLab keeps the earlier versions. The lock is OpenTofu's state lock (see [the state locking entry](state-locking-inspection-refactoring-drift.md)), which GitLab implements behind the HTTP backend's `lock` address, so a plan or an apply started outside the pipeline fails while one inside it holds the lock, or waits with `-lock-timeout`.

GitLab's documentation adds three things worth knowing before relying on it ([GitLab-managed OpenTofu state](https://docs.gitlab.com/user/infrastructure/iac/terraform_state/)):

- **Encryption.** State files *"are encrypted with the Lockbox Ruby gem when at rest"*, with a key derived from the instance's `db_key_base` setting, so *"the instance must be available to decrypt a state file"*. Restoring a GitLab backup therefore also needs the instance's secrets file, where `db_key_base` lives.
- **Roles.** *"To lock, unlock, and write to the state by using `tofu apply`, you must have the Maintainer or Owner role"*; Developers can read it with `tofu plan -lock=false`.
- **Plans aren't encrypted.** *"OpenTofu `plan.json` or `plan.cache` files are not encrypted and might contain sensitive data"*, and *"by default, users with the Guest role can access your plan files"*. The component sets its plan artifact's access to `none` (the `plan_artifacts_access` input), so it isn't downloadable from the interface.

## The same state from outside the pipeline

The state isn't tied to CI. Setting the HTTP backend's variables by hand, with a personal access token in place of the job token, gives an engineer's machine the same view. In the example, from another container on the lab network:

```sh
export TF_HTTP_ADDRESS=http://gitlab/api/v4/projects/<id>/terraform/state/default
export TF_HTTP_USERNAME=root TF_HTTP_PASSWORD=<personal access token>
tofu init && tofu output -json release
```

```text
{"environment":"lab","version":"1.0.0"}
```

That's also how to inspect or repair a state when a pipeline can't, with the role rules above: a Maintainer's token can lock and write, a Developer's only read.

The commands above ran in a Linux container: GitLab CE 19.5.1, GitLab Runner 19.5.1 with the Docker executor, and the component's OpenTofu 1.12.6 image, from the companion repository's lab.
