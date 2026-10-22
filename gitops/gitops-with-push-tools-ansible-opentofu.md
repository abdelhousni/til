# GitOps with tools that push: Ansible and OpenTofu against the four OpenGitOps principles

Third entry in the Running IaC and CaC from a controller series. [The first two entries](../ansible/control-node-runner-controller-tower-awx-aap.md) looked at what runs Ansible: a pipeline's runner job or a controller. Both are often called "GitOps" as soon as the playbooks live in Git. GitOps has a stricter definition than that, written for agents that run all the time, and Ansible and OpenTofu don't work that way. This entry compares them against it, so that the series can say precisely which parts a GitLab pipeline gives and which it only approximates.

## The definition

[OpenGitOps](https://opengitops.dev/), overseen by the GitOps Working Group at the Linux Foundation, published four principles (version 1.0.0). The *desired state* of a system managed by GitOps must be ([PRINCIPLES.md](https://github.com/open-gitops/documents/blob/main/PRINCIPLES.md)):

1. **Declarative**: *"expressed declaratively"*, describing the state to reach rather than the steps to reach it.
2. **Versioned and immutable**: *"stored in a way that enforces immutability, versioning and retains a complete version history"*. Git is the usual store.
3. **Pulled automatically**: *"Software agents automatically pull the desired state declarations from the source."*
4. **Continuously reconciled**: *"Software agents continuously observe actual system state and attempt to apply the desired state."*

Two terms from its [glossary](https://github.com/open-gitops/documents/blob/main/GLOSSARY.md): *drift* is when the actual state *"has moved or is in the process of moving away from the desired state"*; *reconciliation* is *"the process of ensuring the actual state of a system matches its desired state"*. The glossary also says why the third principle insists on pulling: the agent must be able to read the desired state *"at any time, not only when there is an intentional change in the state store triggering a push event"*, and it contrasts this with *"traditional CI/CD, where automation is generally driven by pre-set triggers"*. In GitOps, a reconciliation starts whenever actual and desired state differ, including when something changed outside Git.

The model is Kubernetes, where [controllers reconcile continuously](../kubernetes/what-is-kubernetes-and-how-it-works.md) and GitOps tools such as Argo CD and Flux run inside the cluster as one more controller: they watch a Git repository and apply what it holds, again and again. GitLab follows the same model for Kubernetes: *"GitLab integrates Flux for GitOps"* ([Using GitOps with a Kubernetes cluster](https://docs.gitlab.com/user/clusters/agent/gitops/)).

## Ansible and OpenTofu push

Neither Ansible nor OpenTofu has an agent. [OpenTofu converges only when you run it](../terraform/what-is-terraform-opentofu-and-how-it-works.md); between two runs nothing watches the infrastructure. Ansible connects from a control node, applies the playbook and exits. Run from a pipeline, both are *pushed*: a commit or a merge triggers a job, the job applies the change, and nothing happens until the next trigger.

| Principle | Ansible from a pipeline | OpenTofu from a pipeline | `ansible-pull` on a timer | OpenTofu under Flux (Tofu Controller) |
|---|---|---|---|---|
| 1. Declarative | partly: modules describe states (`state: present`), but a play is an ordered list of tasks, and `command` or `shell` tasks describe steps | yes: resources describe the end state | as Ansible | yes |
| 2. Versioned and immutable | yes, in Git | yes, in Git; the state file is versioned separately | yes | yes |
| 3. Pulled automatically | no: the pipeline pushes on a trigger | no | yes: each host clones the repository | yes: the controller watches the source |
| 4. Continuously reconciled | only if the pipeline also runs on a schedule | only if the pipeline also runs on a schedule | yes, if it runs the playbook every time | yes |

Ansible modules being *idempotent*, giving the same result however many times they run, is what makes running the same playbook again a reconciliation rather than a repetition. That holds for well-written modules, not for a `shell` task that appends a line on every run.

## Pulling isn't reconciling: ansible-pull

`ansible-pull` turns Ansible around: each managed node clones the repository and runs the playbook on itself, usually from a cron job or a systemd timer. Its own source describes it as inverting *"the default push architecture of ansible into a pull architecture"*, useful *"both for extreme scale-out and periodic remediation"* ([pull.py](https://github.com/ansible/ansible/blob/devel/lib/ansible/cli/pull.py)). It has an option that changes what it is, though: `-o` (`--only-if-changed`) runs the playbook only if the repository has new commits.

Run twice in a row against the lab's GitLab, with ansible-core 2.20.10:

```sh
ansible-pull -o -d /tmp/pull -U http://gitlab/root/ctl-02.git -i localhost, site.yml
```

```text
== run 1
ok: [localhost] =>
    msg: ansible-core 2.20.10 ran site.yml for localhost
localhost                  : ok=1    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
== run 2
Repository has not changed, quitting
```

Both outputs are trimmed: the first to the task and the recap, the second to its first line, which `ansible-pull` follows with the Git module's result. The second run pulled and stopped: with `-o`, a file someone edited by hand on that host stays edited until the next commit. Without `-o`, every run applies the playbook, so drift is corrected at each timer tick, which is what the fourth principle asks for. The lab's GitLab project is private; the runs used a read-only project access token in the URL, left out above.

## What a pipeline can do about the missing principles

A GitLab pipeline can't pull, but it can run without a commit. A *scheduled pipeline* runs a project's pipeline at set times, and that gives two ways to approximate reconciliation:

- **Detect drift.** OpenTofu's `tofu plan -detailed-exitcode` exits with 0 when nothing would change, 1 on error and 2 when the real infrastructure differs from the code, so a scheduled job can fail, and alert, on 2. For Ansible, `ansible-playbook --check --diff` reports what would change without changing it; a host with `changed` tasks has drifted.
- **Correct drift.** The scheduled job applies instead of checking: `tofu apply` or `ansible-playbook` on the schedule, as `ansible-pull` without `-o` does on its timer.

Detecting leaves the decision to a person; correcting is closer to the principles but applies changes nobody reviewed at that moment, such as a provider upgrade changing a default. Pinning narrows that: if the scheduled job runs a release tag, an execution environment by digest and providers at locked versions, the only thing it can apply is what was reviewed when that tag was made. The Red Hat CoP good practices ask for the same in production: *"Never use 'latest' or branch names in production references"* ([Git workflow](https://github.com/redhat-cop/automation-good-practices/blob/main/git_workflow/README.adoc)). The series comes back to both in a later part.

For OpenTofu there is also a way to meet all four principles: the [Tofu Controller](https://github.com/flux-iac/tofu-controller), formerly Weave TF-Controller, a Flux controller that reconciles OpenTofu and Terraform resources *"in the GitOps way"*, with a drift-detection-only mode among its models. It needs a Kubernetes cluster running Flux, which this series doesn't use.

## The vocabulary the series uses

- **GitOps** in the OpenGitOps sense: an agent pulls from Git and reconciles continuously. In this series, only `ansible-pull` without `-o` and the Tofu Controller meet it.
- **A pipeline driven by Git**, often called *push-based GitOps*: Git is the source of truth, merge requests are the only way to change it, and a pipeline applies each merge. Principles 1 and 2 hold; 3 doesn't; 4 holds only as far as scheduled runs go.

Most of this series builds the second, because Ansible and OpenTofu are push tools. The scheduled runs that bring it closer to the first are left for a later part.

The `ansible-pull` runs ran in the Semaphore UI 2.19.17 container of the companion repository's lab, against GitLab CE 19.5.1; nothing else in this entry was run.
