# `git config user.email` isn't the identity Git commits with: check `git var`

In a cloud coding session, `git config user.email` printed `noreply@anthropic.com`, yet commits came out as `abdelhousni <23284113+abdelhousni@users.noreply.github.com>`. Both were right about different things. `git config` only reads configuration files; the environment variables `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` override them, and `git config` doesn't know they exist.

Two terms first. Every commit records an **author** (who wrote the change) and a **committer** (who made the commit), each a name, an email and a date. They are usually the same person; `git log --format='%an <%ae> / %cn <%ce>'` prints both.

## Ask Git what it will use

```sh
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

`git var` prints the identity the next commit would get, after every source has been applied, followed by a timestamp:

```text
abdelhousni <23284113+abdelhousni@users.noreply.github.com> 1792259342 +0000
```

`git var -l` lists both identities alongside the configuration, which shows a mismatch at a glance:

```text
user.email=local@example.com
GIT_COMMITTER_IDENT=Local <local@example.com> 1794068487 +0000
GIT_AUTHOR_IDENT=Local <env@example.com> 1794068487 +0000
```

Here the repository's config says `local@example.com`, but `GIT_AUTHOR_EMAIL=env@example.com` was set, so the author gets that address and the committer keeps the config one.

## Which source wins

From strongest to weakest, as tested with Git 2.43 in a scratch repository with its own `HOME`:

1. `git commit --author="Name <email>"`, for the author of that commit only.
2. The `GIT_AUTHOR_*` and `GIT_COMMITTER_*` environment variables.
3. `git -c user.email=...` on the command line.
4. The repository's `.git/config`, then the global `~/.gitconfig` (`git config --show-origin --get-all user.email` lists each file and its value).
5. The `EMAIL` environment variable, used only when no `user.email` is set anywhere.

With none of them, `git commit` stops with "Please tell me who you are".

Each variable covers one field of one role. Setting only `GIT_AUTHOR_EMAIL` changed the author's email; the author's name and the whole committer still came from the config.

An empty variable counts as set. `GIT_AUTHOR_EMAIL=` (empty) gave `Local <>` even with `user.email` configured, and `git commit` accepted it without a warning.

## Find and fix the override

```sh
env | grep -E '^(GIT_(AUTHOR|COMMITTER)_|EMAIL=)'
```

If the variables are set and wrong, unset them in the shell (`unset GIT_AUTHOR_EMAIL ...`) or change them where they're defined: a shell profile, a CI job's variables, a container's environment, or a cloud environment's settings. Editing `user.email` alone won't help while they're set.

If `git var` already shows the right identity, as with the variables in that cloud session, nothing needs fixing, even though `git config user.email` disagrees.

Check before the first commit. Fixing the author of commits already pushed means rewriting them and force-pushing (see [resync-clone-after-force-push.md](resync-clone-after-force-push.md) for what that does to other clones).

## Sources

- [`git-commit(1)`, "Commit information"](https://git-scm.com/docs/git-commit#_commit_information): the environment variables, `user.name`/`user.email` and `EMAIL`.
- [`git-var(1)`](https://git-scm.com/docs/git-var): `GIT_AUTHOR_IDENT`, `GIT_COMMITTER_IDENT` and `-l`.
- [`git(1)`, "Environment variables"](https://git-scm.com/docs/git#_git_commits): `GIT_AUTHOR_NAME` and the others.
