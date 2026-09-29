# Syncing a diverged fork: take the pipeline fixes, not the content

This TIL collection started as a fork of [simonw/til](https://github.com/simonw/til), and since then the fork has diverged completely. The articles are mine, the build is mine (see [static-site-instead-of-datasette.md](../github-pages/static-site-instead-of-datasette.md)), and upstream's `build.yml` was deleted. GitHub still shows a "This branch is N commits behind simonw/til:main" banner, though, and its **Sync fork** button offers exactly one thing: merge everything. For this fork, that's wrong.

What I actually want from upstream:

- **Yes:** the "non-moving parts", meaning pipeline and tooling fixes (like bumping GitHub Actions versions) that still apply to my setup.
- **No:** upstream's articles, images, or topic folders.
- **Yes:** the "behind" counter at zero, so the next sync only shows what's actually new.

## 1. Look at what upstream has before touching anything

Add upstream as a remote, then find the last commit the two histories share:

```bash
git remote add upstream https://github.com/simonw/til
git fetch upstream main
# a shallow clone has no shared history to find
git fetch --unshallow origin

BASE=$(git merge-base HEAD upstream/main)
git log --oneline "$BASE"..upstream/main        # what upstream added
git diff --stat "$BASE" upstream/main           # which files
git diff --name-status "$BASE" upstream/main | grep -v '\.md$'   # the non-article files
```

If `merge-base` prints nothing, the clone is shallow. Unshallow it and try again.

In my case the last command showed the useful part right away. Aside from images and the README index, the only non-article file was `.github/workflows/build.yml`, where upstream had bumped `checkout`, `setup-python` and `cache`, and moved to Python 3.14.

## 2. Merge with `-s ours` to record the sync without the files

```bash
git merge -s ours upstream/main -m "Sync with upstream without taking its content"
```

The `ours` *strategy* (not the `-X ours` *option*, which still merges non-conflicting files) creates a real merge commit whose tree is exactly your current tree. Upstream's commits become ancestors, so GitHub's "behind" counter drops to zero, and the next `merge-base` starts from here. The next sync then shows only new upstream commits, not the same 16 again.

A quick check that nothing slipped in:

```bash
git diff --stat HEAD^1 HEAD    # empty output: no files changed
```

## 3. Port the pipeline changes by hand, where they apply

My fork doesn't run `build.yml` at all. Restoring it would bring back a pipeline that deploys to Simon's S3 and Fly.io setup. So I applied the same bumps to the workflow I *do* run, `publish.yml`, and pinned each action by commit SHA the way this repo's zizmor check expects:

```bash
git ls-remote https://github.com/actions/setup-python 'refs/tags/v7.0.0*'
# for an annotated tag, use the ^{} line: that one is the commit
```

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
- uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
  with:
    python-version: "3.14"
```

A bump that doesn't apply gets skipped. `publish.yml` has no cache step, so upstream's `actions/cache` bump didn't carry over. Before pushing, I ran the build scripts under the new Python version (`uv venv -p 3.14`).

## 4. Merge the PR with a merge commit, never a squash

The `-s ours` commit changes no files, so it *is* the whole sync. Squash-merging or rebase-merging the PR throws that commit away, and the fork shows as "behind" again. Use **Create a merge commit**.

## Why not just click "Sync fork"?

On a fork that still tracks upstream closely, clicking it is fine. On a diverged one, it either conflicts (my fork deleted `build.yml` and rewrote `README.md`) or quietly brings in files you never wanted. Once they're committed, taking them back out is more work than the steps above.
