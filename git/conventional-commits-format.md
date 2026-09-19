# Conventional Commits: only two types are actually required by the spec

Every "docs: add TIL on..." commit in this repo's own history follows this convention — `git log --oneline` on this exact repository is a live example, not a hypothetical. Worth knowing precisely what the spec actually mandates, because it's less than the taxonomy everyone uses.

## The structure

Per [the official specification, v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

```
fix(ansible): make the etcd-snapshot role idempotent

rke2 etcd-snapshot save ran on every apply, even with nothing
to snapshot. changed_when now checks snapshot_save.stdout
instead of defaulting to true.

Refs: ABD-14
```

Nothing about the format is code-specific — an Ansible role, a Terraform module, or a Packer template changes through the same mechanism as any other file: a commit, reviewed as a diff. The type in front of the colon is what turns "here's a diff" into "here's a diff that changes what gets provisioned, not just a comment."

## The part that's surprising: the spec requires exactly two types

`feat` and `fix` are the only types the specification itself mandates — because they're the only two with a defined meaning for automated versioning. Everything else people write constantly (`docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`) is convention layered on top, recommended by common practice rather than required by the 16 numbered rules in the spec text. A repo that only ever wrote `feat:` and `fix:` commits would be fully spec-compliant; one that invented its own additional type name (`ui:`, `deps:`) wouldn't be violating anything either, as long as the structure around it holds.

## Why it exists: the message is machine input, not just a label

The entire point is a direct, literal mapping to [Semantic Versioning](https://semver.org/):

- `fix:` → **PATCH**
- `feat:` → **MINOR**
- a breaking change, marked either way below → **MAJOR**

```mermaid
flowchart LR
    C[Commit message] --> T{Type / marker}
    T -->|fix| PATCH[PATCH bump]
    T -->|feat| MINOR[MINOR bump]
    T -->|"! after type/scope, or BREAKING CHANGE footer"| MAJOR[MAJOR bump]
```

That's what separates this from just a house style for readable commit logs: a tool can walk the commit history since the last tag and compute the next version number without a human deciding it, because the message itself already encodes the answer.

## Marking a breaking change: two ways, same effect

```
feat(terraform)!: switch S3 state locking to use_lockfile
```

or, keeping the header plain and pushing the detail into a footer:

```
feat(terraform): switch S3 state locking to use_lockfile

BREAKING CHANGE: dynamodb_table is no longer read. Run `terraform init
-reconfigure` after this lands, or applies will fail to acquire a lock.
```

That's not an invented example — it's the exact migration [the state-locking entry](../terraform/state-locking-inspection-refactoring-drift.md) in this series covers, and it's a genuinely good fit for a `BREAKING CHANGE` footer: the point of the footer isn't just "this is major," it's telling the next person what to actually *do* about it, which a one-line header can't hold. Both forms trigger a MAJOR bump under the spec's own SemVer mapping — the `!` is the faster, greppable signal that something in this commit needs a second look before merging; the footer is where the migration step lives.

One case-sensitivity detail easy to get backwards: everyday types (`feat`, `fix`, `docs`, ...) are case-insensitive, but `BREAKING CHANGE` as a footer token must be exactly that — uppercase — for tooling to recognize it. `BREAKING-CHANGE` with a hyphen is defined as a synonym for the same footer, for compatibility with tools that can't easily emit a space inside a token name.
