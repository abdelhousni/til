# Ignore your own scratch files without touching `.gitignore`: use `.git/info/exclude`

Working in a shared repository leaves files that are yours alone: an inventory dump, a test playbook, a tool's log. Adding them to `.gitignore` changes a file the whole team shares, so the change shows up in `git status` and ends up in a commit sooner or later. Git reads two other ignore files that are never committed: `.git/info/exclude` for one clone, and a global file for every repository on your machine.

A few terms first. A **tracked** file is one Git already has in its **index**, the staging area the next commit is built from. Any other file in the **working tree** (the files checked out on disk) is **untracked**. Ignore rules only apply to untracked files: they keep them out of `git status` and out of `git add .`.

## Two files that are never committed

| File | Applies to | Put in it |
|---|---|---|
| `.git/info/exclude` | this clone only | files of your own workflow in this repository: `inventory-dump-*.yml`, `test-playbook.yml` |
| `~/.config/git/ignore` | every repository of your user | files your own tools create everywhere: editor backups, `*.tmp`, `scratch/` |

So the question to ask about a file is whether it belongs to this project or follows you into every repository. `.gitignore`, the committed file, stays for what the project creates for everyone, such as build output.

All three files use the same pattern syntax, and a path is ignored as soon as a pattern in any of them matches it. The order between them only counts when a pattern starting with `!` un-ignores a path: `.gitignore` comes first, then `.git/info/exclude`, then the global file, and the first source with a matching pattern decides.

The global file is whatever the `core.excludesFile` setting names. By default that's `$XDG_CONFIG_HOME/git/ignore`, or `~/.config/git/ignore` when `XDG_CONFIG_HOME` isn't set or is empty. `XDG_CONFIG_HOME` is the environment variable from the XDG Base Directory specification that tells programs where to keep per-user configuration; most systems leave it unset. Either way, the file works without any configuration.

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
inventory-dump-*.yml
test-playbook.yml
ansible-navigator.log
EOF
```

For patterns you want in every repository, the global file:

```sh
mkdir -p ~/.config/git
printf '%s\n' '*.tmp' 'scratch/' >> ~/.config/git/ignore
```

## Check that it works

`git status --short --ignored` lists ignored paths with `!!`, next to untracked ones with `??`:

```text
?? free
!! build/
!! dump.yml
!! notes.tmp
```

`git check-ignore -v` prints, for each path, the file, line and pattern that matched it:

```sh
git check-ignore -v dump.yml notes.tmp build/x
```

```text
.git/info/exclude:8:dump.yml	dump.yml
/home/user/.config/git/ignore:1:*.tmp	notes.tmp
.gitignore:1:build/	build/x
```

The global file shows as an absolute path, the other two relative to the repository root. A path no pattern matches prints nothing, and the command exits with status 1 when that's true of all the paths. A `!` pattern is printed too, with exit status 0, even though it means the path is *not* ignored: with `!keep.tmp` in `.git/info/exclude`, `git check-ignore -v keep.tmp` prints `.git/info/exclude:9:!keep.tmp	keep.tmp` and `git status` still shows `?? keep.tmp`.

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
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/): `XDG_CONFIG_HOME`.
