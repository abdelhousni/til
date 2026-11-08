# Adding Renovate to a GitHub or GitLab project: the hosted app, the runner, and the versions it can't see

[Renovate](https://docs.renovatebot.com/) is a bot that reads a repository, finds every dependency whose version is written down, looks up newer releases and opens one pull request per update. It's open source, and [Mend](https://www.mend.io/) maintains it and runs a free hosted version. Getting it onto a project takes two steps: choose who runs it, which differs between GitHub and GitLab, and then make sure every version you care about is written somewhere Renovate can read.

The terms this relies on:

- **Pull request** (GitHub) or **merge request** (GitLab): a proposed change on its own branch, reviewed and merged on the platform. Renovate opens one for each update. The rest of this entry says "PR" for both.
- **Manager**: the Renovate module that understands one kind of file, such as `ansible-galaxy` for `requirements.yml`, `dockerfile` for a Dockerfile, `terraform` for `.tf` files or `github-actions` for workflows. It *extracts* each dependency's name and current version.
- **Datasource**: where Renovate looks up the available versions of a dependency, such as Ansible Galaxy, a container registry, the Terraform registry, a Helm chart repository, the GitHub releases API or plain `git ls-remote`.
- **Preset**: a named, reusable piece of Renovate configuration, pulled in with `"extends"`. `config:recommended` is the usual starting point.
- **Onboarding PR**: the first PR Renovate opens on a repository, titled "Configure Renovate". It adds a `renovate.json` and lists what Renovate found. Nothing else happens until you merge it.
- **Dependency Dashboard**: an issue Renovate keeps up to date with every pending, open and ignored update, with checkboxes to trigger or approve them.
- **Lock file**: a file that records the exact version of every dependency, next to the file that holds the version constraints. [Pinning ansible-core](../ansible/pinning-ansible-core-pip-tools-uv-poetry.md) explains the difference.
- **Digest**: the hash that identifies one exact commit or image, as opposed to a tag such as `v4` that can move.

One Renovate run, wherever it runs:

```mermaid
flowchart LR
    A[Read renovate.json<br/>and presets] --> B[Managers extract<br/>name + current version]
    B --> C{Version usable?}
    C -- "missing, a branch,<br/>or needs a token" --> S[Skipped, with a reason]
    C -- yes --> D[Datasources list<br/>newer versions]
    D --> E[packageRules: group,<br/>schedule, approve, automerge]
    E --> F[One branch and PR<br/>per update or group]
    E --> G[Dependency Dashboard]
```

## Who runs it

| | GitHub.com | GitLab.com |
|---|---|---|
| Hosted by Mend, free | **Mend Renovate app** from [github.com/apps/renovate](https://github.com/apps/renovate), on a user or an organization, for all or selected repositories | **Mend Developer Platform for GitLab.com**, relaunched in July 2026, installed on a **group** only. Mend's instructions require a paid GitLab account: free GitLab accounts aren't supported |
| Self-hosted | The [`renovatebot/github-action`](https://github.com/renovatebot/github-action) Action (v46.3.12), with a token or your own GitHub App | The [`renovate-bot/renovate-runner`](https://gitlab.com/renovate-bot/renovate-runner) CI template (v26.1.0), in a scheduled pipeline |

The Renovate documentation advises the hosted app for most users, on both platforms. Mend then keeps the token, schedules runs and updates the Renovate version. On the free Community Cloud plan, Mend runs one job per organization at a time, schedules each active repository every 4 hours, and stops a job after 30 minutes. It also reacts to webhooks, so ticking a box on the dashboard starts a job without waiting for the schedule.

## GitHub: install the Mend Renovate app

1. Open [github.com/apps/renovate](https://github.com/apps/renovate), select **Install**, and pick the account.
2. Choose **All repositories** or **Only select repositories**. With "All repositories", Renovate skips forks and repositories without any file it recognises. With "Select repositories", it processes forks too.
3. Wait for the "Configure Renovate" PR on each repository. Renovate opens it from a branch named `renovate/configure`. Push changes to `renovate.json` on that branch, and Renovate rewrites the PR description to show what the new configuration would do.
4. Merge it. Closing it without merging opts the repository out.

The app asks for read access to administration (to read branch protection), Dependabot alerts and metadata. It asks for read and write access to code, checks, commit statuses, issues, pull requests and **workflows**: GitHub requires that last permission separately before an app can change a file under `.github/workflows/`. Mend's web portal, [developer.mend.io](https://developer.mend.io/), shows each job's log and can start a run on demand.

To run Renovate yourself instead, the Action runs the Renovate container image with a token. The documentation lists the permissions a fine-grained token needs: read and write on contents, issues, pull requests, commit statuses and workflows, plus read on Dependabot alerts and organization members. A classic token needs the `repo` scope, and `workflow` to update Actions. Give the self-hosted bot a `branchPrefix` other than the default `renovate/`, so that it doesn't fight with the app if both ever run on one repository.

## GitLab: a scheduled pipeline with renovate-runner

On a free GitLab.com account, or on a self-managed GitLab, Renovate runs as a CI job in a project of its own. The steps:

1. Create a new private project, for example `group/renovate-runner`, just for the bot. The runner's README says not to fork the template project.
2. Create a token for the bot and add it under **Settings → CI/CD → Variables** as `RENOVATE_TOKEN`, masked. The token's role and scopes are listed after these steps.
3. Add `RENOVATE_GITHUB_COM_TOKEN`, a GitHub token with the minimum scopes. Renovate uses it to fetch release notes and to look up versions through the GitHub API. Without it, those lookups are skipped or rate-limited (see the dry run below).
4. Tell the bot which projects to process, in a `RENOVATE_EXTRA_FLAGS` variable, as shown below.
5. Commit a `.gitlab-ci.yml` that includes the template, pinned to a release tag, as shown below.
6. Add a schedule under **Build → Pipeline schedules**. The README suggests hourly, `3 * * * *`. The job only runs from a schedule, so start the first run with the schedule's play button.

The token:

- **Which token**: a **group access token** on the group the bot works on, or a personal access token of a dedicated user. A group access token creates its own bot user, which then authors the merge requests. GitLab requires an expiry date on a group access token, so put the renewal in a calendar.
- **Role**: at least **Developer**, which can open merge requests and issues. To automerge, the token also needs "Allowed to merge" on the protected branch, which means **Maintainer** when only maintainers may merge.
- **Scopes**: Renovate's GitLab page asks for `api` (`read_api` is enough for a dry run). The runner's README lists `read_user`, `api` and `write_repository`.

Autodiscovery and onboarding are both off by default in the template. To process every project in one group and open an onboarding merge request in each, set `RENOVATE_EXTRA_FLAGS` to:

```text
--autodiscover=true --autodiscover-filter=group/*
```

Add `--onboarding=false` to process only projects that already have a `renovate.json`. A space-separated list such as `group/app group/infra` names the projects explicitly instead. The filter matters: without it, the bot processes any project that someone invites it into.

The runner project's `.gitlab-ci.yml`:

```yaml
include:
  - project: 'renovate-bot/renovate-runner'
    file: '/templates/renovate.gitlab-ci.yml'
    ref: v26.1.0
```

On a self-managed GitLab that can't include a project from GitLab.com, use `remote: https://gitlab.com/renovate-bot/renovate-runner/-/raw/v26.1.0/templates/renovate.gitlab-ci.yml` instead. Adding `gitlab>renovate-bot/renovate-runner` to the `extends` of the runner project's own `renovate.json` lets Renovate update that `ref`.

The template, at v26.1.0, sets `RENOVATE_PLATFORM=gitlab`, takes the endpoint from `$CI_API_V4_URL`, runs the image `ghcr.io/renovatebot/renovate:44` (the latest 44.x on each pull), caches the repository data between runs, and keeps a debug log as a job artifact for a day. Its onboarding config extends `config:recommended`.

The same project ships a second template, `/templates/renovate-config-validator.gitlab-ci.yml`, that adds a job checking `renovate.json` in the project that includes it.

## The configuration

The onboarding PR or MR proposes a `renovate.json` like this one:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"]
}
```

`config:recommended` turns on the Dependency Dashboard and groups packages released together, such as the parts of a monorepo. It applies Renovate's package replacements and workarounds, and adds changelog links and release-age badges to the PRs. When the history already uses [Conventional Commits](../git/conventional-commits-messages-that-tools-can-read.md), the onboarding PR turns on semantic commit messages, so Renovate's commits follow the same `type(scope): summary` form. The file can also live at `.github/renovate.json`, `.gitlab/renovate.json` or `.renovaterc.json`, among others.

Check the file before you push it. Renovate 44.222.2 needs Node.js 24.11 or later (or 26.13 or later):

```console
$ npx --yes --package renovate@44.222.2 -- renovate-config-validator --strict
 INFO: Validating renovate.json
 INFO: Config validated successfully against 1 file(s)
```

`--strict` also fails when the file uses an option that Renovate has since renamed.

## What Renovate finds, and what it can't see

To see what Renovate would do before installing anything, run it against a clone with the `local` platform. The platform is experimental. It only looks versions up (`dryRun=lookup`) and never creates branches. `--report-type=file` writes every dependency and proposed update to a JSON file:

```sh
cd my-project
npx --yes --package renovate@44.222.2 -- renovate --platform=local \
  --report-type=file --report-path=/tmp/renovate-report.json
```

The test project mixed the files of an RKE2 lab repository: an Ansible `requirements.yml`, a Dockerfile, a `.gitlab-ci.yml`, a GitHub workflow, an [OpenTofu provider](../terraform/what-is-terraform-opentofu-and-how-it-works.md), RKE2 and Longhorn versions in an Ansible vars file, and a flake. Before any change, the report said:

| File | Dependency as written | Result |
|---|---|---|
| `requirements.yml` | role `lablabs.rke2`, `version: main` | skipped: `invalid-value` |
| `requirements.yml` | collection `kubernetes.core`, no version | skipped: `unspecified-version` |
| `requirements.yml` | collection `community.general` `11.0.0` | 11.4.10 (minor), 14.0.0 (major), as two PRs |
| `Dockerfile` and `.gitlab-ci.yml` | `docker.io/library/python:3.12-slim` | `3.15-slim` |
| `main.tf` | provider `bpg/proxmox`, `~> 0.66` | `~> 0.120`, in one jump |
| workflow | `actions/checkout@v4` | skipped: `github-token-required` |
| `Dockerfile` | `RUN curl … get-helm-3 \| bash`, from `main` | not seen at all |

What each of those needs:

**A branch name isn't a version.** `version: main` and a missing version leave Renovate nothing to compare with. Pinned to the role's tag `1.53.0`, `lablabs.rke2` was looked up with the `git-tags` datasource and got a PR to `1.54.0`. Pinned to `5.0.0`, `kubernetes.core` got PRs to 5.5.0 and 6.6.0.

**A version in a variable needs a `# renovate:` comment.** No manager knows that `ARG KUBECTL_VERSION=v1.31.0` in a Dockerfile is kubectl. The `customManagers:dockerfileVersions` preset reads a comment on the line above any `ARG` or `ENV` whose name ends in `_VERSION`:

```dockerfile
# renovate: datasource=docker depName=registry.k8s.io/kubectl
ARG KUBECTL_VERSION=v1.31.0
```

The comment has to name a datasource that actually publishes the versions. The first try, `docker.io/bitnami/kubectl`, came back with "Found no results from datasource that look like a version". `registry.k8s.io/kubectl` returned the full list.

Files that no preset covers need a regex manager of your own. For Ansible vars files with the same comment convention:

```yaml
# renovate: datasource=helm depName=longhorn registryUrl=https://charts.longhorn.io
longhorn_version: "1.7.2"
```

```json
"customManagers": [
  {
    "customType": "regex",
    "description": "Versions in Ansible vars files, marked with a renovate comment",
    "managerFilePatterns": ["/^ansible/.+\\.ya?ml$/"],
    "matchStrings": [
      "# renovate: datasource=(?<datasource>\\S+) depName=(?<depName>\\S+)( registryUrl=(?<registryUrl>\\S+))?\\n\\w+_version: \"?(?<currentValue>[^\"\\n]+)\"?"
    ]
  }
]
```

That found `longhorn` and offered 1.13.0. RKE2 works the same way. The `git-tags` datasource reads tags with `git ls-remote`, so it needs no GitHub token, and its `depName` is the repository URL:

```yaml
# renovate: datasource=git-tags depName=https://github.com/rancher/rke2
rke2_version: "v1.31.4+rke2r1"
```

It offered `v1.37.2+rke2r1` and skipped the release candidates (`-rc1+rke2r1`).

**An install script fetched from `main` can't be tracked.** Renovate only reads versions written in files. Download a release by version instead (Helm publishes one tarball per version on `get.helm.sh`), put the version in an `ARG` with a comment, and the line becomes an update like any other.

**The GitHub API needs a token.** The run warned `GitHub token is required for some dependencies` for `actions/checkout` and `opentofu/opentofu`, because the container it ran in couldn't reach the GitHub API. The `github-tags` and `github-releases` datasources go through that API. `git-tags`, used for RKE2 above, doesn't. The Mend app on GitHub has a token already. A GitLab runner needs `RENOVATE_GITHUB_COM_TOKEN`.

For workflows on GitHub, `helpers:pinGitHubActionDigests` pins each action to a commit digest, and Renovate then updates the digest according to the tag in a version comment (`uses: actions/checkout@<sha> # v4`). An action pinned to a bare digest, with no version comment, isn't updated at all, because Renovate can't tell which tag it belongs to. Those lookups need the GitHub API, so the run here doesn't show them.

## Kubernetes minors, one at a time

By default, Renovate offers only the newest minor: kubectl at `v1.31.0` got one PR straight to `v1.37.2`, and RKE2 one to `v1.37.2+rke2r1`. That's six minors at once. [RKE2](../kubernetes/what-is-rke2-and-how-it-works.md) runs the Kubernetes API server, which the Kubernetes version skew policy says must not skip a minor version when it's upgraded. kubectl is only supported within one minor of that API server, so the two should also move together.

`separateMultipleMinor` gives each minor its own branch. `groupName` puts RKE2 and kubectl in the same branch. With both, the run produced one branch per minor, each carrying both updates: `renovate/minor-1.32-kubernetes` held RKE2 `v1.32.13+rke2r2` and kubectl `v1.32.13`, and so on up to 1.37. The patch updates within 1.31 went to `renovate/kubernetes`.

Without anything else, all seven PRs would be created as Renovate's rate limits allow, which is 2 an hour and 10 open at a time by default. `dependencyDashboardApproval` holds each one back until its checkbox is ticked on the Dependency Dashboard, so the cluster moves one minor per approval:

```json
"packageRules": [
  {
    "description": "Cluster components: one PR per minor, created only when approved on the dashboard",
    "matchDepNames": ["registry.k8s.io/kubectl", "https://github.com/rancher/rke2", "longhorn"],
    "separateMultipleMinor": true,
    "dependencyDashboardApproval": true
  },
  {
    "description": "RKE2 and kubectl move together",
    "matchDepNames": ["registry.k8s.io/kubectl", "https://github.com/rancher/rke2"],
    "groupName": "kubernetes"
  }
]
```

Longhorn got the same treatment on its own: 1.7.3, then one branch for each of 1.8 to 1.13.

## Nix flakes: opt in, and the channel moves too

The `nix` manager reads `flake.nix` and its lock (a flake is a Nix project whose inputs are pinned in `flake.lock`: see the flakes section of [NixOS first steps](../nixos/first-steps-configuration-generations-rollback.md)). It is in beta and off by default:

```json
"nix": { "enabled": true }
```

With it on, an input that follows a NixOS release branch is treated as a version. The `nixpkgs` versioning knows the release names:

```text
nix  flake.nix  nixpkgs  cur=nixos-25.11  ->  nixos-26.05 (major)
```

So Renovate does propose the twice-yearly channel switch in `flake.nix`, as a major update. To rewrite `flake.lock` it runs `nix flake update nixpkgs`, so the job needs the `nix` command. It only changes the flake's own input, though. The same release name, such as `nixos-26.05`, in a CI image tag, a workflow's `nix_path` or a test file is plain text to Renovate. Either keep it in one place, or mark each copy with a `# renovate:` comment and a regex manager. With `"lockFileMaintenance": { "enabled": true }`, Renovate also opens a PR that refreshes every lock file it supports, `flake.lock` included, on its own schedule, `before 4am on monday` by default.

## A starting configuration

This is the file the last run used. It validates with `--strict` on 44.222.2:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "customManagers:dockerfileVersions",
    "helpers:pinGitHubActionDigests"
  ],
  "timezone": "Europe/Brussels",
  "schedule": ["before 6am on monday"],
  "lockFileMaintenance": { "enabled": true },
  "nix": { "enabled": true },
  "customManagers": [
    {
      "customType": "regex",
      "description": "Versions in Ansible vars files, marked with a renovate comment",
      "managerFilePatterns": ["/^ansible/.+\\.ya?ml$/"],
      "matchStrings": [
        "# renovate: datasource=(?<datasource>\\S+) depName=(?<depName>\\S+)( registryUrl=(?<registryUrl>\\S+))?\\n\\w+_version: \"?(?<currentValue>[^\"\\n]+)\"?"
      ]
    }
  ],
  "packageRules": [
    {
      "description": "Cluster components: one PR per minor, created only when approved on the dashboard",
      "matchDepNames": ["registry.k8s.io/kubectl", "https://github.com/rancher/rke2", "longhorn"],
      "separateMultipleMinor": true,
      "dependencyDashboardApproval": true
    },
    {
      "description": "RKE2 and kubectl move together",
      "matchDepNames": ["registry.k8s.io/kubectl", "https://github.com/rancher/rke2"],
      "groupName": "kubernetes"
    },
    {
      "description": "GitHub Actions: automerge digests, patches and minors once CI is green",
      "matchManagers": ["github-actions"],
      "matchUpdateTypes": ["digest", "pinDigest", "patch", "minor"],
      "automerge": true
    }
  ]
}
```

`schedule` limits when Renovate creates or updates branches. `timezone` makes it read that schedule in local time instead of UTC. `automerge` merges a PR once its status checks pass. On GitLab, the token also needs merge rights on the protected branch, as described above.

Renovate 44.222.2 (the npm `latest` tag on 2026-11-08) ran on Node.js 24.22.2 in a Linux cloud container, with the `local` platform against a scratch Git repository. The registries answered: Ansible Galaxy, Docker Hub, `registry.k8s.io`, the Terraform registry, `charts.longhorn.io`, and `git ls-remote` against GitHub. The GitHub API didn't answer, so no GitHub-hosted version was looked up. The local platform creates no branches, so the Dependency Dashboard, the approval checkboxes and automerge weren't exercised. The Mend apps and the GitLab runner weren't installed: those steps come from the documentation listed below.

## Sources

- Renovate documentation, for 44.222.2: [Installing and onboarding](https://docs.renovatebot.com/getting-started/installing-onboarding/), [Mend-hosted apps](https://docs.renovatebot.com/mend-hosted/overview/), [Security and permissions](https://docs.renovatebot.com/security-and-permissions/), [GitHub platform](https://docs.renovatebot.com/modules/platform/github/), [GitLab platform](https://docs.renovatebot.com/modules/platform/gitlab/), [Local platform](https://docs.renovatebot.com/modules/platform/local/), [Config validation](https://docs.renovatebot.com/config-validation/), [Nix manager](https://docs.renovatebot.com/modules/manager/nix/), [Regex manager](https://docs.renovatebot.com/modules/manager/regex/), [GitHub Actions manager](https://docs.renovatebot.com/modules/manager/github-actions/), [Scheduling](https://docs.renovatebot.com/key-concepts/scheduling/) and [Configuration options](https://docs.renovatebot.com/configuration-options/) (`separateMultipleMinor`, `dependencyDashboardApproval`, `groupName`, `lockFileMaintenance`, `timezone`).
- Preset definitions read from the installed `renovate@44.222.2` package (`dist/config/presets/internal/`), and the nix manager's default config and `flake.lock` update command (`dist/modules/manager/nix/`).
- Mend documentation: [Install Mend Developer Platform for GitLab.com](https://docs.mend.io/integrations/latest/install-mend-developer-platform-for-gitlab-com).
- [renovate-bot/renovate-runner](https://gitlab.com/renovate-bot/renovate-runner): README and `templates/renovate.gitlab-ci.yml` at v26.1.0.
- [renovatebot/github-action](https://github.com/renovatebot/github-action): README, latest tag v46.3.12.
- Kubernetes: [Version skew policy](https://kubernetes.io/releases/version-skew-policy/) (`kube-apiserver` minor upgrades, kubectl).
