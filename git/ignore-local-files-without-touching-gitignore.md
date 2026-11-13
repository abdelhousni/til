# Ignore your own scratch files without touching `.gitignore`: use `.git/info/exclude`

Working in a shared repository leaves files that are yours alone: an Ansible inventory dump, a test playbook, a saved Terraform plan. Adding them to `.gitignore` changes a file the whole team shares, so the change shows up in `git status` and ends up in a commit sooner or later. Git reads two other ignore files that are never committed: `.git/info/exclude` for one clone, and a global file for every repository on your machine.

A few terms first. A **tracked** file is one Git already has in its **index**, the staging area the next commit is built from. Any other file in the **working tree** (the files checked out on disk) is **untracked**. Ignore rules only apply to untracked files: they keep them out of `git status` and out of `git add .`.

## Two files that are never committed

| File | Applies to | Put in it |
|---|---|---|
| `.git/info/exclude` | this clone only | files of your own workflow in this repository: `inventory-dump.yml`, `dev.tfplan` |
| `~/.config/git/ignore` | every repository of your user | files your own tools create everywhere: editor swap files `*.swp`, `scratch/` |

So the question to ask about a file is whether it belongs to this project or follows you into every repository. `.gitignore`, the committed file, stays for what the project creates for everyone, such as build output.

All three files use the same pattern syntax, and a path is ignored as soon as a pattern in any of them matches it. The order between them only counts when a pattern starting with `!` un-ignores a path: `.gitignore` comes first, then `.git/info/exclude`, then the global file, and the first source with a matching pattern decides.

The global file is whatever the `core.excludesFile` setting names. By default that's `$XDG_CONFIG_HOME/git/ignore`, or `~/.config/git/ignore` when `XDG_CONFIG_HOME` isn't set or is empty. `XDG_CONFIG_HOME` is the environment variable from the XDG Base Directory specification that tells programs where to keep per-user configuration; most systems leave it unset. Either way, the file works without any configuration.

## In Ansible and Terraform projects

Some terms first. [ansible-navigator](../ansible/ansible-development-tools-adt.md) is the text interface that runs playbooks, by default inside an execution environment. A Terraform **saved plan** is the file `terraform plan -out=FILE` writes, so that `terraform apply FILE` applies exactly the changes that were reviewed. An **override file** is a `.tf` file named `override.tf` or ending in `_override.tf`: Terraform loads it after the rest of the configuration and merges its blocks over the ones already defined, which is a quick way to point one resource elsewhere on your machine. [What Terraform/OpenTofu is](../terraform/what-is-terraform-opentofu-and-how-it-works.md) explains the configuration itself.

| File | Created by | Ignore it in |
|---|---|---|
| `ansible-navigator.log` | ansible-navigator: its default log file, in the directory you run it from | `.git/info/exclude` |
| `*-artifact-*.json` | ansible-navigator: one playbook artifact per run, `{playbook_dir}/{playbook_name}-artifact-{time_stamp}.json` by default | `.git/info/exclude` |
| `inventory-dump.yml` | you: `ansible-inventory --list --yaml > inventory-dump.yml`, to look at the variables every host gets | `.git/info/exclude` |
| `test-playbook.yml` | you: a playbook to try one task | `.git/info/exclude` |
| `*.tfplan` | you: `terraform plan -out=dev.tfplan` | `.git/info/exclude` |
| `dev_override.tf` | you: a local override | `.git/info/exclude` |
| `*.swp`, `*~` | your editor (Vim swap files, backups), in every repository | `~/.config/git/ignore` |

What every user's run creates belongs in the committed `.gitignore` instead, so that nobody can commit it by mistake: Terraform's `.terraform/` directory, state files (`*.tfstate`) and variable files (`*.tfvars`), which can hold secrets, and an Ansible vault password file. GitHub's [`Terraform.gitignore`](https://github.com/github/gitignore/blob/main/Terraform.gitignore) template lists these, and override files too. If your project's `.gitignore` already covers a file in the table above, you have nothing to add.

## Move your own rules out of `.gitignore`

If you already added your files to `.gitignore`, look at what else changed in it before undoing anything: `git restore .gitignore` throws away **every** uncommitted change to the file, including any line meant for the team.

```sh
# Check that your own lines are the only change
git diff .gitignore

# Then put the shared .gitignore back as it is in the last commit
git restore .gitignore

# Ignore your scratch files in this clone only
cat >> .git/info/exclude <<'EOF'
# Local scratch files (not committed)
ansible-navigator.log
*-artifact-*.json
inventory-dump.yml
test-playbook.yml
*.tfplan
dev_override.tf
EOF
```

For patterns you want in every repository, the global file:

```sh
mkdir -p ~/.config/git
printf '%s\n' '*.swp' '*~' 'scratch/' >> ~/.config/git/ignore
```

## Check that it works

`git status --short --ignored` lists ignored paths with `!!`, next to untracked ones with `??`:

```text
?? main.tf
!! .site.yml.swp
!! .terraform/
!! ansible-navigator.log
!! dev.tfplan
!! inventory-dump.yml
!! site-artifact-2026-11-13T10:00:00.json
```

`git check-ignore -v` prints, for each path, the file, line and pattern that matched it:

```sh
git check-ignore -v inventory-dump.yml dev.tfplan .site.yml.swp .terraform/x
```

```text
.git/info/exclude:10:inventory-dump.yml	inventory-dump.yml
.git/info/exclude:12:*.tfplan	dev.tfplan
/home/user/.config/git/ignore:1:*.swp	.site.yml.swp
.gitignore:1:.terraform/	.terraform/x
```

The global file shows as an absolute path, the other two relative to the repository root. A path no pattern matches prints nothing, and the command exits with status 1 when that's true of all the paths. A `!` pattern is printed too, with exit status 0, even though it means the path is *not* ignored: with `!review.tfplan` added to `.git/info/exclude` to keep one plan visible, `git check-ignore -v review.tfplan` prints `.git/info/exclude:14:!review.tfplan	review.tfplan` and `git status` still shows `?? review.tfplan`.

## Three traps

**A tracked file is never ignored.** Adding `.gitignore` to `.gitignore`, the obvious way to hide your own edits to it, does nothing: the file is tracked, so `git status` still shows ` M .gitignore` and `git check-ignore -v .gitignore` prints nothing. `--no-index` checks the patterns without looking at the index, which shows the rule matches but has no effect:

```text
$ git check-ignore -v --no-index .gitignore
.gitignore:2:.gitignore	.gitignore
```

**A pattern ending in `/` doesn't match a symbolic link.** A symbolic link is a small file that points to another path, such as a role checked out from another repository. With `roles/*/` in `.gitignore`, the directory `roles/real/` is ignored, but `roles/linked`, a link to a role developed elsewhere, still shows as `?? roles/linked`: for Git, a link is a file, not a directory. Exclude the link by name, without the trailing slash: `roles/linked` in `.git/info/exclude`.

**Local changes to a tracked file can't be ignored.** Listing a tracked `cfg.ini` in `.git/info/exclude` still leaves ` M cfg.ini` in `git status`. Two bits in the index can hide the change:

- `git update-index --skip-worktree cfg.ini`: `git ls-files -v` then marks the file with `S`, and `--no-skip-worktree` undoes it. The bit exists for sparse checkouts, which leave part of the tree off disk.
- `git update-index --assume-unchanged cfg.ini`: `git ls-files -v` marks the file with a lowercase `h`, and `--no-assume-unchanged` undoes it. The bit is a performance promise that you won't change the file.

Both make `git status` quiet, and Git's documentation warns against using either this way: "This does not work as expected, since Git may still check working tree files against the index when performing certain operations. In general, Git does not provide a way to ignore changes to tracked files". Commands such as `pull` or `merge` may still write the file. The alternative it suggests is a committed sample, such as `cfg.ini.example`, that each user copies to an ignored name and edits.

Tested with Git 2.43.0 in scratch repositories with their own `HOME`.

## Sources

- [`gitignore(5)`](https://git-scm.com/docs/gitignore): the order of precedence, which file each kind of pattern goes in, the default of `core.excludesFile`, and `foo/` not matching a symbolic link.
- [`git-check-ignore(1)`](https://git-scm.com/docs/git-check-ignore): the `-v` output format, negated patterns and `--no-index`.
- [`git-update-index(1)`](https://git-scm.com/docs/git-update-index): the skip-worktree and assume-unchanged bits, and the quoted note on ignoring changes to tracked files.
- [`git-status(1)`](https://git-scm.com/docs/git-status): `--ignored` and the `!!` marker.
- [ansible-navigator settings](https://ansible.readthedocs.io/projects/navigator/settings/): the default `log-file` and `playbook-artifact-save-as`.
- [`ansible-inventory`](https://docs.ansible.com/projects/ansible/latest/cli/ansible-inventory.html): `--list` and `--yaml`.
- Terraform: [override files](https://developer.hashicorp.com/terraform/language/files/override) and [`terraform plan -out`](https://developer.hashicorp.com/terraform/cli/commands/plan).
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/): `XDG_CONFIG_HOME`.
