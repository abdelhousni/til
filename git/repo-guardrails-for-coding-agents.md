# Configuring a repository for coding agents: what the guidance actually says

This repo is mostly written with a coding agent (Claude Code, running in a cloud session). The agent opens branches and PRs and fixes CI. After a few rounds of that I wondered whether there's any agreed guidance on how the *repository* should be set up for it: branch protection, CI, instructions files. The answer: yes, but it's spread across vendors, and Simon Willison's guide, which I expected to cover it, mostly doesn't.

Four terms recur below. *Branch protection* and *rulesets* are GitHub settings that restrict what can be pushed to a branch, such as blocking force pushes. `CODEOWNERS` is a file that names who owns which paths, so GitHub can require their review of changes to those paths. `AGENTS.md` is a Markdown file of instructions for coding agents, a convention several tools read; `CLAUDE.md` is the same idea for Claude Code. *MCP* (Model Context Protocol) is a standard for connecting tools and data sources to an agent, configured per repository in a file.

## Simon Willison: git is the safety net, not the gate

Simon's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/) is about how you *work* with an agent, not how you configure the repo. The relevant chapter, [Using Git with coding agents](https://simonwillison.net/guides/agentic-engineering-patterns/using-git-with-coding-agents/), treats git as the thing that makes mistakes cheap:

- Keep the agent's changes on branches.
- Start a session by having the agent read `git log`.
- Let the agent resolve conflicts, dig through `reflog`, and run `bisect`.
- Rewriting history on your own branches is fine. He treats history as "a deliberately authored story".

The other relevant chapter is [First run the tests](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/): give the agent a fast check it can run itself. Here that's `make check`.

## GitHub: agents don't push to main, and don't merge

GitHub's docs for its own cloud agent read as general guidance for any agent: [Building guardrails](https://docs.github.com/en/copilot/tutorials/cloud-agent/build-guardrails) and [Risks and mitigations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations).

- The agent can't push to the default branch or merge PRs. Humans merge.
- Protect the files that steer the agent (`AGENTS.md`, `CLAUDE.md`, MCP config) with `CODEOWNERS` plus "Require review from Code Owners".
- Keep the workflow token's permissions minimal, and require approval before workflows run on agent-opened PRs.
- If a ruleset blocks the agent, add the agent as a [bypass actor](https://github.blog/changelog/2025-11-13-configure-copilot-coding-agent-as-a-bypass-actor-for-rulesets/) instead of weakening the rule for humans.

## Anthropic: when the agent runs *inside* your CI

The [claude-code-action security guide](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md) covers a different case: an agent triggered by `@claude` comments inside GitHub Actions.

- Only people with write access can trigger it.
- Never check out an untrusted PR head into the workspace before the agent runs.
- Keep API keys in secrets.
- Keep full output off on public repos: it can leak file contents into public logs.

## GitLab: prompt injection and identity

GitLab's [security threats in agentic systems](https://docs.gitlab.com/user/duo_agent_platform/security_threats/) page frames things around prompt injection, a dedicated service identity for the agent, and sandboxing. Its [external agents](https://docs.gitlab.com/user/duo_agent_platform/agents/external/) page warns that third-party agents like Claude Code don't get GitLab's built-in prompt scanning or network isolation.

## What that meant for this repo

Already covered:

- Work goes through branches and PRs.
- `CLAUDE.md` holds the conventions.
- A security workflow runs gitleaks, actionlint and zizmor.
- Actions are pinned by SHA, and the workflow token's permissions are minimal.

The gaps the guidance exposed, and what I did about each:

- **Commit authorship:** the cloud session's git identity is `Claude <noreply@anthropic.com>`. My convention is that I'm the author and Claude is a `Co-Authored-By`. Fixing that after the fact means rewriting history and force-pushing. So `CLAUDE.md` now tells the agent to check `git config user.email` and set my identity before its first commit.
- **Merging:** `CLAUDE.md` now says the agent opens PRs but only merges when explicitly asked. It also says which merge method each kind of PR needs: a fork sync must keep its merge commit (see [sync-a-diverged-fork-without-its-content.md](sync-a-diverged-fork-without-its-content.md)).
- **Branch protection:** the minimum is a ruleset on `main` that blocks force pushes and deletion. That one can't break anything. "Require a pull request" and "require status checks" would, because the publish workflow's README bot commits straight to `main`, and the built-in workflow token can't be a ruleset bypass actor. "Require linear history" would reject the merge commit a fork sync depends on.
- **`CODEOWNERS` on `CLAUDE.md`:** skipped for now. On a solo repo I can't approve my own PR, so it adds friction without adding review.
