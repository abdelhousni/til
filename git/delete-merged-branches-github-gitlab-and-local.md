# Deleting merged branches: GitHub's auto-delete, GitLab's equivalent, and the local clone

A merged branch has done its job, but nothing removes it by default. It stays on GitHub or GitLab, it stays in every clone, and the branch list grows until nobody knows which ones still hold work. Squash merges make it worse, because Git itself no longer recognises those branches as merged.

The terms this relies on:

- **Pull request** (GitHub) or **merge request** (GitLab): a request to merge one branch into another, reviewed on the platform. The branch with the changes is the **head branch** on GitHub and the **source branch** on GitLab; the one it merges into, usually `main`, is the **base** or **target** branch.
- **Squash merge**: the platform turns all the branch's commits into one new commit on `main`. That commit is not the branch's tip and has none of its commits as ancestors, so Git sees the branch as unmerged.
- **Remote-tracking branch**: your clone's copy of a branch on the server, such as `origin/feature`. A local branch that follows one has it as its **upstream**.

`gh` and `glab`, the GitHub and GitLab command-line tools, need installing and signing in first: see [git-gh-glab-install-and-auth.md](git-gh-glab-install-and-auth.md).

## GitHub: turn on "Automatically delete head branches"

In the repository, **Settings → General → Pull Requests → Automatically delete head branches**. It takes admin rights on the repository. From the command line:

```sh
gh repo edit OWNER/REPO --delete-branch-on-merge
gh api repos/OWNER/REPO --jq .delete_branch_on_merge   # true once it's on
```

What it does, and what it doesn't:

- It deletes the head branch when a pull request is **merged**. Closing a pull request without merging leaves the branch.
- It only acts on merges from now on. Branches merged before you turned it on stay.
- Branch protection rules and rulesets can stop the deletion.
- For a pull request from a fork, GitHub reads the setting on the **fork**, and the person merging needs write access to the fork. Otherwise the branch stays.
- A deleted branch can be brought back with **Restore branch** at the bottom of its closed pull request.

For a single merge, `gh pr merge` can do the same without the setting. `--delete-branch` (`-d`) deletes the branch on GitHub, except for a pull request from a fork or when the merge is left to auto-merge, and, when you run it inside a clone, the local branch of that name too.

```sh
gh pr merge 42 --squash --delete-branch
```

## GitHub: delete the branches merged before the setting was on

`git branch --merged` can't find squash-merged branches, so ask GitHub instead: every merged pull request records its head branch and the commit it ended on. The loop below deletes a branch only when its tip is still that commit. A branch that received new commits after its pull request merged, for example because it was reused for the next pull request, is kept.

```sh
REPO=OWNER/REPO
gh pr list -R "$REPO" --state merged --limit 1000 \
   --json headRefName,headRefOid --jq '.[] | "\(.headRefName) \(.headRefOid)"' |
while read -r branch sha; do
  tip=$(gh api "repos/$REPO/git/ref/heads/$branch" --jq .object.sha 2>/dev/null) || continue  # already gone
  if [ "$tip" = "$sha" ]; then
    echo "delete $branch"
    # gh api -X DELETE "repos/$REPO/git/refs/heads/$branch"
  else
    echo "keep   $branch (new commits since its pull request merged)"
  fi
done
```

Run it once as is: it only prints. Then remove the `#` and run it again. The `git/ref/heads/…` endpoints take branch names with slashes, such as `claude/fix-x`. A branch that never had a pull request doesn't appear in the list at all; delete it by hand if it's done with, with the same `gh api -X DELETE` line.

## GitLab: the same setting, per merge request and per project

GitLab decides per merge request, with **Delete source branch when merge request accepted** when creating it, or **Delete source branch** when merging it. The project setting only changes that checkbox's default: **Enable "Delete source branch" option by default**, field `remove_source_branch_after_merge` in the API. Like GitHub's, it applies to new merge requests, not to ones already open, and for a merge request from a fork GitLab reads the fork's default.

```sh
# in a clone of the project; :fullpath is replaced with its group/project path
glab api --method PUT projects/:fullpath -F remove_source_branch_after_merge=true
glab api projects/:fullpath | jq .remove_source_branch_after_merge

glab mr merge 42 --squash --remove-source-branch
```

The deletion is done as the user who merges or sets auto-merge. If they lack the role for it, as can happen in a fork, the merge goes through and the branch stays.

## GitLab: delete the branches merged before

GitLab has a bulk action: **Code → Branches → More (⋮) → Delete merged branches**, or `DELETE /projects/:id/repository/merged_branches` in the API. It deletes the branches **merged into the default branch**, never protected ones. The documentation doesn't say whether a squash-merged branch counts, and in Git's own test it doesn't (see the next section). After squash merges, go through the merge requests instead, as on GitHub:

```sh
# in a clone of the project
glab mr list --merged --per-page 100 -F json |
jq -r '.[] | "\(.source_branch) \(.sha)"' |
while read -r branch sha; do
  json=$(glab api projects/:fullpath/repository/branches/:b --placeholder b="$branch" 2>/dev/null) ||
    continue                                                   # already gone
  tip=$(jq -r .commit.id <<<"$json")
  if [ "$tip" = "$sha" ]; then
    echo "delete $branch"
    # glab api --method DELETE projects/:fullpath/repository/branches/:b --placeholder b="$branch"
  else
    echo "keep   $branch (new commits since its merge request merged)"
  fi
done
```

`--placeholder` encodes the branch name as one path segment, so names with slashes work. `--per-page 100` reads only the 100 most recent merged merge requests; add `--page 2` and so on for more.

## The local clone

Deleting a branch on the server doesn't touch any clone. Each clone keeps its remote-tracking branch until a fetch prunes it, and its local branch until you delete it.

```sh
git fetch --prune                       # drop origin/* branches deleted on the server
git config --global fetch.prune true    # or prune on every fetch and pull
```

A local branch whose upstream was pruned shows as `gone`:

```sh
git branch -vv
#   feature-merge  32cb2e7 [origin/feature-merge: gone] feature-merge 2
#   feature-squash 83a189b [origin/feature-squash: gone] feature-squash 2
#   feature-wip    a0c1265 [origin/feature-wip] feature-wip 2

git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads |
  awk '$2 == "[gone]" { print $1 }'      # just the names
```

`gone` only says the server deleted the branch, not that its work reached `main`. Here `git branch -d` and `-D` differ:

```text
$ git branch -d feature-merge
Deleted branch feature-merge (was 32cb2e7).
$ git branch -d feature-squash
error: the branch 'feature-squash' is not fully merged.
```

`-d` deletes only a branch whose commits are all in `main`. That's true after a merge commit, never after a squash merge, so a squash-merged branch needs `-D`, which deletes without checking. To check first, compare what merging the branch would produce with `main` itself: when they're the same tree, the branch has nothing `main` lacks.

```sh
git switch main && git pull --ff-only
for b in $(git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads |
           awk '$2 == "[gone]" { print $1 }'); do
  if [ "$(git merge-tree --write-tree main "$b" | head -1)" = "$(git rev-parse 'main^{tree}')" ]; then
    git branch -D "$b"
  else
    echo "keep $b: it has changes main doesn't"
  fi
done
```

`git merge-tree --write-tree` needs Git 2.38 or later. `git cherry main feature-squash`, the usual "is this already upstream?" check, doesn't help here: it compares commits one by one, and after a squash it marked both of the branch's commits as missing (`+`), although their changes were on `main`.

The local commands ran with Git 2.43 in scratch repositories: a branch merged with a merge commit, one squash-merged, one still open, and one squash-merged branch that received a commit afterwards (kept, as expected). The `gh` and `glab` commands weren't run against GitHub or GitLab; they come from the documentation and `gh`'s source listed below. The two server-side loops ran against stand-ins for `gh` and `glab` that return the documented JSON, which checked their logic: an unchanged branch is deleted, a reused one kept, a deleted one skipped.

## Sources

- GitHub documentation: [Managing the automatic deletion of branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-the-automatic-deletion-of-branches) and [Deleting and restoring branches in a pull request](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/deleting-and-restoring-branches-in-a-pull-request).
- `gh` source, [cli/cli](https://github.com/cli/cli): `pkg/cmd/repo/edit/edit.go` (`--delete-branch-on-merge`) and `pkg/cmd/pr/merge/merge.go` (`--delete-branch`).
- GitLab documentation: [Merge requests, Delete the source branch](https://docs.gitlab.com/user/project/merge_requests/#delete-the-source-branch), [Delete merged branches](https://docs.gitlab.com/user/project/repository/branches/#delete-merged-branches), [Branches API](https://docs.gitlab.com/api/branches/), [Projects API](https://docs.gitlab.com/api/projects/) (`remove_source_branch_after_merge`) and [Squash and merge](https://docs.gitlab.com/user/project/merge_requests/squash_and_merge/).
- `glab` documentation: [`glab api`](https://docs.gitlab.com/cli/api/), [`glab mr list`](https://docs.gitlab.com/cli/mr/list/) and [`glab mr merge`](https://docs.gitlab.com/cli/mr/merge/).
- Git documentation: [git-fetch](https://git-scm.com/docs/git-fetch) (`--prune`, `fetch.prune`), [git-branch](https://git-scm.com/docs/git-branch), [git-merge-tree](https://git-scm.com/docs/git-merge-tree) and [git-cherry](https://git-scm.com/docs/git-cherry).
