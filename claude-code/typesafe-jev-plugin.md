# Starting with Jev in Claude Code: a plugin that adds a skill, and an API key for experiments

Jev is TypeSafe's first "System One" model. It doesn't write text or code. You send it some `state` and a map of typed questions, and it answers each one with a number or a label: a yes/no probability, a choice among options, or a score. The idea is to replace fragile parsing, or a prompt-and-parse LLM call, with a judgment your code can use directly. It came up in a [Code Newsletter guide](https://codenewsletter.ai/p/the-ultimate-guide-to-building-with-jev); the details below come from TypeSafe's own docs and plugin repository.

## Install the plugin

```bash
claude plugin marketplace add typesafe-ai/skills
claude plugin install typesafe@typesafe-ai
```

The first command registers the [typesafe-ai/skills](https://github.com/typesafe-ai/skills) repository as a plugin marketplace. The second installs its only plugin, `typesafe`. What you get is one MIT-licensed skill, `skills/typesafe-ai/SKILL.md`. There are no hooks, MCP server or commands, so nothing runs on your machine. The skill tells Claude how to design with TypeSafe and to read the live docs at [docs.typesafe.ai](https://docs.typesafe.ai/llms.txt) as the source of truth.

To update:

```bash
claude plugin marketplace update typesafe-ai
claude plugin update typesafe@typesafe-ai
```

Then restart Claude Code or run `/reload-plugins`. `/plugin` → *Marketplaces → typesafe-ai* can enable auto-update instead.

## First prompts

Name the skill, or invoke it with `/typesafe:typesafe-ai`. The docs suggest starting with a survey of your own code:

```text
Using the TypeSafe skill, explore the project and find opportunities for using
intelligent judgement to stand in for complex parsing or other fragile code.
```

To let Claude run real queries, create a key at [console.typesafe.ai/keys](https://console.typesafe.ai/keys). Export it before starting Claude Code, rather than pasting it into the chat:

```bash
export TYPESAFE_API_KEY="..."
```

```text
Using the TypeSafe skill, run some experiments using the TypeSafe API key that I've
exported to `TYPESAFE_API_KEY`. Propose changes based on the most promising results.
```

## What a call looks like

One endpoint, `POST https://api.typesafe.ai/v1/systemone`, with `Authorization: Bearer <key>`:

```json
{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "is_urgent": { "type": "noul", "instructions": "Does this convey urgency?" }
  }
}
```

The answer comes back under the key you chose:

```json
{ "model": "jev-1.13.0", "answers": { "is_urgent": { "type": "noul", "noul": 0.95 } } }
```

There are three question types:
- `noul`: yes/no as a number from 0 to 1;
- `choice`: one label among options you give;
- `score`: a value on a scale.

Choice and score answers also carry a `confidence`, which the docs suggest using to send uncertain cases to a human. Python and JavaScript SDKs exist too.

Not tested here, since that needs an API key. The request and response above are the examples from TypeSafe's API reference. Pricing, speed and model claims are TypeSafe's; check them against your own workload.

## Sources

- [typesafe-ai/skills](https://github.com/typesafe-ai/skills): `.claude-plugin/marketplace.json`, `plugin.json` (v0.5.7), and `skills/typesafe-ai/SKILL.md`.
- TypeSafe docs: [Agent skill](https://docs.typesafe.ai/agent-skill), [API reference](https://docs.typesafe.ai/api) and [Primitives](https://docs.typesafe.ai/primitives).
- Code Newsletter: [The ultimate guide to building with Jev](https://codenewsletter.ai/p/the-ultimate-guide-to-building-with-jev).
