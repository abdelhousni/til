# git tag basics, grounded in how Ansible collection releases actually use them

`git tag` looks simple until a release process actually depends on getting it right. Ansible collection releases are a good concrete example — the tag isn't decorative, tooling reads it back.

## Annotated, not lightweight

```sh
git tag v1.0        # lightweight -- just a named pointer to a commit
git tag -a v1.0 -m "message"   # annotated -- a real object: message, tagger, date
```

A collection release always uses the annotated form, with a specific message convention:

```sh
git tag -a 2.1.0 -m "my_namespace.my_collection: 2.1.0"
```

Two things worth noticing in that one line: no `v` prefix, and the message names the collection, not just the version.

## Why no `v` prefix

The tag has to match `galaxy.yml`'s `version:` field **exactly** — `2.1.0`, not `v2.1.0`. Tooling that computes the next SemVer bump (or checks what's already released) reads the tag list back and compares it directly against that version string. A tag with an extra `v` doesn't just look inconsistent, it silently stops matching anything that string-compares against `galaxy.yml`.

## `git push` does not push tags

This is the one that catches people who are otherwise comfortable with git: an ordinary `git push` never sends tags, annotated or not. They need to go explicitly:

```sh
git tag -a 2.1.0 -m "my_namespace.my_collection: 2.1.0"
git push upstream 2.1.0
```

Pushing to `upstream` by name (not `origin`, not `--tags`) also isn't an accident here — in a fork-based contribution workflow, `origin` is your own fork and `upstream` is the canonical repo; a release tag belongs on the canonical repo specifically, and naming it explicitly avoids also pushing any other tags that happen to exist locally.

## Once it's pushed, treat it as permanent

A pushed tag is effectively a public claim: "this commit is version X." Anyone can already have fetched it by the time you notice a mistake, so moving or deleting a released tag isn't a quiet fix — it's a second thing to notice and reconcile. Worth treating the moment of pushing a release tag as a deliberate, double-checked step, not a routine `git push` you do without looking.

## Inspecting tags

```sh
git tag -l                 # list all tags
git tag -l "2.*"            # filter
git show 2.1.0               # the annotation, tagger, date, and the commit it points to
```

## The GitHub Release comes from the tag, not the other way around

```sh
gh release create 2.1.0 --title "2.1.0" --notes "See CHANGELOG.rst for details."
```

`gh release create` takes an existing tag name and wraps a GitHub Release around it — the tag has to exist and be pushed first. Get the tag wrong (prefix, typo, wrong commit) and the release inherits that mistake.

## The GitLab equivalent: the pushed tag drives the pipeline

On a GitLab-hosted collection, the same pushed tag is what a release pipeline reacts to — no separate "create a release" command to run by hand:

```yaml
# .gitlab-ci.yml
release_job:
  stage: release
  rules:
    - if: $CI_COMMIT_TAG
  script:
    - echo "Releasing $CI_COMMIT_TAG"
  release:
    tag_name: $CI_COMMIT_TAG
    description: "See CHANGELOG.rst for details."
```

`rules: - if: $CI_COMMIT_TAG` is what scopes this job to tag pipelines specifically — without it, the job would also try to run on every ordinary branch push. `$CI_COMMIT_TAG` is a predefined variable GitLab sets to the tag name when (and only when) a pipeline was triggered by a tag push, so the job reads the version back from the tag instead of it being typed in twice. The `release` keyword then does what `gh release create` does on GitHub: it turns that tag into an actual GitLab Release once the job runs.
