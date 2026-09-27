# Someone force-pushed the branch you pulled: check what's yours, then reset or `pull --rebase`

A coding agent working on my branch pushed a commit (`2913eb4`), and I fetched it. It then noticed a typo in the commit message and fixed it with `--amend` and a force-push. That gave a new commit, `504a439`, with the same code. Then it pushed its next step, `d23665b`, on top. My clone still had `2913eb4`, which GitHub no longer had.

The same happens with any history rewrite on a shared branch: an amend, a squash, or an interactive rebase followed by `git push --force`. Everything below was reproduced with Git 2.43, using two clones of a scratch bare repository. One clone did the force-push; the other had fetched before it.

## What it looks like

`git fetch` says so, but only in one line, easy to miss:

```text
 + 2913eb4...d23665b feature    -> origin/feature  (forced update)
```

The `+` and `(forced update)` mean the remote branch no longer contains what it pointed to before. `git status` then reports:

```text
Your branch and 'origin/feature' have diverged,
and have 1 and 2 different commits each, respectively.
  (use "git pull" if you want to integrate the remote branch with yours)
```

The "1" is the old version of the rewritten commit. If you also committed something yourself since fetching, it counts those too. The hint to use `git pull` is the one thing not to follow blindly; see below.

## 1. Find out what exists only on your side

```sh
git fetch origin
git log --oneline origin/feature..feature
```

`A..B` lists commits reachable from `B` but not from `A`: here, the commits only your branch has. If the only line is the commit that was rewritten, nothing of yours is at stake:

```text
2913eb4 Fix empty output on current coreutils and run under POSIX sh
```

To see how the old and new versions differ, compare them:

```sh
git range-diff 2913eb4~1..2913eb4 504a439~1..504a439
```

`range-diff` compares commits as patches, message included. For a message-only fix, the only `-`/`+` pair is in the `## Commit message ##` section; the file section has no changed lines. `git diff 2913eb4 504a439` answers a narrower question: an empty output means the two commits have the same files. When both have the same parent, that means the same change.

## 2a. Nothing of yours: reset to the remote

```sh
git status        # no uncommitted changes, or stash them first
git reset --hard origin/feature
git log --oneline -3
```

The log now starts with `d23665b`, then `504a439`. `reset --hard` discards uncommitted changes to tracked files without asking, hence the `git status` first. The old commit is not lost straight away: `git reflog` lists it as `HEAD@{1}`. Now that no branch points to it, `git gc` may prune it once its reflog entry expires, after 30 days by default (`gc.reflogExpireUnreachable`).

## 2b. Commits of yours on top: `git pull --rebase`

If step 1 shows a commit you made after fetching, don't reset. Replay your commits onto the new remote branch, and leave the old version of the rewritten commit behind:

```sh
git pull --rebase
```

In the test, with the rewritten commit's code changed too, not only its message, this gave `base`, then the new commit, then mine, without a conflict. It works because `git pull --rebase`, like `git rebase` without an argument, uses the remote-tracking branch's **reflog**. `origin/feature` once pointed at `2913eb4`, so Git treats that commit as upstream's and doesn't replay it. The rebase documentation calls this `--fork-point`.

**Naming the upstream explicitly changes the result.** `git rebase origin/feature` doesn't consult the reflog, so it tries to replay the old commit as well:

- **Identical change** (message-only fix): Git recognizes the patch as already applied and skips it, with `warning: skipped previously applied commit 2913eb4`. The result is correct.
- **Different change**: `CONFLICT (content)`, on a commit that isn't even yours.

The fork-point trick needs the reflog entry, which exists only if you had fetched the old commit into `origin/feature`. If you're unsure, name the old commit yourself. This replays only the commits after it:

```sh
git rebase --onto origin/feature 2913eb4
```

## Don't merge

`git pull --no-rebase` merges the old and new histories. In the test, the next commit on the remote changed the same line as the rewritten one, so the merge stopped with `CONFLICT (content): Merge conflict in s.sh`. Without that overlap, you'd get a merge commit keeping both versions of the rewritten commit in the history for good.

## `git pull` already refuses, unless you configured it not to

In Git 2.43, a plain `git pull` on diverged branches stops before doing anything:

```text
fatal: Need to specify how to reconcile divergent branches.
```

That default only holds while `pull.rebase` and `pull.ff` are unset. Many people set `pull.rebase false` once, to silence the hint that some older Git versions printed on each pull. With it set, the same `git pull` merges straight away, and here it hit the conflict above.

`pull.ff only` makes the refusal explicit, and it wins over `pull.rebase`:

```sh
git config --global pull.ff only
```

With it, `git pull` fails with `fatal: Not possible to fast-forward, aborting.` whenever the branches diverged. It does so even with `pull.rebase true` or `false` also set. An explicit `git pull --rebase` still works, so you choose when to rebase, after step 1.

| Command, on the diverged branch | Result in the test |
|---|---|
| `git pull`, no config | Refuses: `Need to specify how to reconcile divergent branches` |
| `git pull` with `pull.rebase false` | Merges; here, a conflict |
| `git pull` with `pull.ff only` | Refuses: `Not possible to fast-forward` |
| `git pull --rebase`, or `git rebase` | Old commit dropped, your commits replayed |
| `git rebase origin/feature` | Old commit replayed: skipped if identical, conflict if not |
| `git rebase --onto origin/feature <old>` | Only the commits after `<old>` replayed |
| `git reset --hard origin/feature` | Your branch equals the remote; local commits only in the reflog |

## On the pushing side

The fix is not to rewrite a branch someone else has fetched. A wrong commit message can wait for a later commit, or for the squash at merge time. `git push --force-with-lease` doesn't help here. It protects the pusher from overwriting commits it hasn't seen, not the clones that already fetched. If a force-push is unavoidable, tell the others the old and new hashes. Step 1 is then a quick check.

## Sources

- The Git documentation: [git-rebase](https://git-scm.com/docs/git-rebase) (`--fork-point`, `--onto`, skipped cherry-picks), [git-pull](https://git-scm.com/docs/git-pull) (`pull.ff`, `pull.rebase`), [git-range-diff](https://git-scm.com/docs/git-range-diff) and [gitrevisions](https://git-scm.com/docs/gitrevisions) (`A..B`).
- A reproduction in two clones of a scratch bare repository, with Git 2.43.0: one force-push that only changed the message, and one that also changed the code.
