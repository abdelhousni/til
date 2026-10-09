# Packaging AI assistant context with Lola: MCP servers, skills and rules as modules

An AI coding assistant needs to be told what to work with: which tools it can call, which procedures to follow and which rules to respect. Setting that up by hand in every project, and again in every cloud session (a session whose container starts empty each time), doesn't last. [Lola](https://github.com/RedHatProductSecurity/lola) is a package manager for that context, from Red Hat Product Security, introduced in a [Red Hat Developer article](https://developers.redhat.com/articles/2026/04/08/manage-ai-context-lola-package-manager). I tested version 0.7.1 with Claude Code 2.1.296 on 2026-10-09.

Four terms first:

- **MCP server**: a program, or a hosted URL, that offers tools to the assistant through the Model Context Protocol, the standard [this entry on guardrails for coding agents](../git/repo-guardrails-for-coding-agents.md) describes. Claude Code reads a project's servers from `.mcp.json`.
- **Skill**: a folder with a `SKILL.md` file, whose front matter has a `name` and a `description`. The assistant reads the description to decide when to load the instructions below it. The [Jev plugin entry](typesafe-jev-plugin.md) installs one.
- **Lola module**: a folder that bundles skills, slash commands, subagents, an `mcps.json` of MCP servers and an `AGENTS.md` of rules. `lola install` translates it into each assistant's own files: Claude Code, Cursor, Gemini CLI, Copilot and OpenCode among others.
- **Marketplace**: a YAML file listing modules and where to fetch them (a git repository and a path inside it).

## A module

`lola mod init ops-mcp` scaffolds one. The content Lola installs sits under `module/`:

```
ops-mcp/
├── README.md
└── module/
    ├── AGENTS.md
    ├── mcps.json
    └── skills/
        └── ops-triage/
            └── SKILL.md
```

The project README describes a different layout (`mcp.json` at the root, a `plugin.json` manifest); 0.7.1 generates the one above, so trust `lola mod init` over the README.

`mcps.json` uses the same `mcpServers` format as Claude Code. This one pairs [linux-mcp-server](https://rhel-lightspeed.github.io/linux-mcp-server/), which inspects a Linux host locally or over SSH, with the hosted [Oh Dear](https://ohdear.app/docs/tools-and-sdks/oh-dear-mcp-server) monitoring server:

```json
{
  "mcpServers": {
    "linux": {
      "command": "linux-mcp-server",
      "env": { "LINUX_MCP_ALLOWED_LOG_PATHS": "${LINUX_MCP_ALLOWED_LOG_PATHS}" }
    },
    "ohdear": { "type": "http", "url": "https://ohdear.app/mcp" }
  }
}
```

No secret goes in the file: `${...}` is read from the environment when the server starts, and Oh Dear signs in with OAuth (a browser sign-in) the first time it's used.

## Installing it

```bash
pip install lola-ai                 # needs Python 3.13 or later
lola mod add -n ops-mcp ./ops-mcp   # register the module
lola install ops-mcp -a claude-code # project scope by default
lola list                           # what is installed where
```

For Claude Code, the install wrote three things into the project:

- the skill to `.claude/skills/ops-triage/SKILL.md`;
- both servers to `.mcp.json`;
- `AGENTS.md` into `CLAUDE.md`, between `<!-- lola:module:ops-mcp:start -->` and `:end` markers, so a later install or uninstall replaces only that block.

`--scope user` installs into `~/.claude/` instead, for every project.

Ansible skills already exist as a marketplace: [ansible-community/ai-forge](https://github.com/ansible-community/ai-forge) ships modules for collection standards, roles and the collection release cycle.

```bash
lola market add ansible-content https://raw.githubusercontent.com/ansible-community/ai-forge/main/lola-market.yml
lola install ansible-collection-standards -a claude-code
```

That added the `ansible-zen` skill and three commands next to `ops-triage`.

## A marketplace of your own, and per-project lists

Several modules in one repository are listed in a `lola-market.yml`, each with the repository and the path to its `module/` folder:

```yaml
name: my-toolkit
description: Context modules for ops work
version: 0.1.0
modules:
  - name: ops-mcp
    description: Diagnose Linux hosts and monitored sites
    version: 0.1.0
    repository: https://github.com/example/my-toolkit.git
    path: modules/ops-mcp/module
```

A project then lists what it needs in `.lola-req` and runs `lola sync`:

```
@my-toolkit/ops-mcp
@ansible-content/ansible-collection-standards
```

Four things I ran into with 0.7.1:

- **Name modules explicitly.** `lola mod add ./ops-mcp` registered the module as `module` (the content folder's name), and `lola install ops-mcp` then failed with "Module 'ops-mcp' not found". `-n ops-mcp` fixes it.
- **Use the marketplace form for repositories with several modules.** A `.lola-req` line can be a git URL with `#subdirectory=modules/ops-mcp/module`, but Lola names such a module after the repository, so a second module from the same repository is skipped as a duplicate. `@marketplace/module` keeps the names from the YAML.
- **`lola sync` fetches the default branch.** A marketplace entry can carry a `ref:`; `lola install @market/module` honours it, `lola sync` doesn't. Test a branch with `install`.
- **Private repositories.** `lola market add` reads the YAML over HTTPS, so a private repository's `raw.githubusercontent.com` URL fails without a token. Registering the file from a local clone works, and Lola then fetches each module with your usual Git credentials.

## Lola or a Claude Code plugin

Claude Code has its own packaging, plugins, which install from a marketplace too (see the [Jev plugin entry](typesafe-jev-plugin.md)). A plugin can carry skills, commands, MCP servers and also **hooks**: commands Claude Code runs on events, such as before every tool call, which can block the call. Lola has no hooks, and a plugin works only in Claude Code. A split that works:

- **Lola modules** for MCP servers and domain skills, which other assistants can use too.
- **A Claude Code plugin** for hooks and for workflow skills tied to Claude Code.

## In a cloud session

A cloud session's container starts empty, so whatever Lola installed under `~/.claude` is gone next time; project-scope files survive only if they're committed. Either commit the generated files, or install at session start from the environment's setup script or a `SessionStart` hook:

```bash
pip install -q lola-ai
lola market add ansible-content https://raw.githubusercontent.com/ansible-community/ai-forge/main/lola-market.yml
lola sync -a claude-code
```

The environment's network policy must allow PyPI and the Git hosts. Servers that sign in through a browser, like Oh Dear, can't finish OAuth in a headless session; add them once as claude.ai connectors instead.

## Sources

- [Lola](https://github.com/RedHatProductSecurity/lola) and the [Red Hat Developer introduction](https://developers.redhat.com/articles/2026/04/08/manage-ai-context-lola-package-manager).
- [ansible-community/ai-forge](https://github.com/ansible-community/ai-forge) and its `lola-market.yml`.
- [linux-mcp-server documentation](https://rhel-lightspeed.github.io/linux-mcp-server/) and [Oh Dear's MCP server](https://ohdear.app/docs/tools-and-sdks/oh-dear-mcp-server).
- Claude Code docs: [plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) and [hooks](https://code.claude.com/docs/en/hooks).
