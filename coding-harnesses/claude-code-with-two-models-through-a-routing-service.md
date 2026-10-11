# Claude Code through an AI routing service, with two models: Claude Opus and Z.ai GLM

Second entry in the Coding harnesses through an AI routing service series.

[The first entry](coding-harnesses-and-ai-routing-services.md) explains what a harness, a routing service and the two API formats are. This one connects Claude Code to a routing service and gives it two models from different vendors. Claude Opus takes the hard reasoning, and GLM, a cheaper model from Z.ai, takes the everyday work. The settings are the same on every service; only the base URL, the key variable and the model IDs change. OpenRouter, Opper and Eden AI are the examples.

## The two models

- **Claude Opus** is Anthropic's largest model. Its weights aren't published, so only Anthropic and the clouds that license it serve it: Amazon Bedrock, Google Vertex AI and Microsoft Azure. Those clouds have EU regions, which is how Opus can stay in the EU.
- **GLM** is a family of open-weight models from Z.ai (Zhipu AI), a Chinese company. Open-weight means the weights are published, so any host can serve the model: OpenRouter lists about forty providers for GLM-5.3, including Z.ai itself and Mistral in the EU. Many serve it *quantized*, at reduced numeric precision (`fp8`, `fp4`) to make it cheaper and faster, which can cost some quality. The provider you end up with therefore decides price, region and precision. Z.ai documents its own Claude Code setup, with every model class on GLM.

List prices on OpenRouter in October 2026, per million tokens (a token is a chunk of text, roughly three quarters of a word): Claude Opus 5.5 costs $4 input and $20 output, and GLM-5.3 from Z.ai costs $1.40 input and $4.40 output.

## Connect Claude Code to the service

Claude Code reads its settings from environment variables. Put them in your shell profile (`~/.bashrc` or `~/.zshrc`) and reload it:

```bash
export ANTHROPIC_BASE_URL="<base URL from the table>"
export ANTHROPIC_AUTH_TOKEN="<routing service API key>"
export ANTHROPIC_API_KEY=""
```

| | OpenRouter | Opper | Eden AI |
|---|---|---|---|
| `ANTHROPIC_BASE_URL` | `https://openrouter.ai/api` (EU: `https://eu.openrouter.ai/api`) | `https://api.opper.ai/v3/compat` | `https://api.edenai.run/v3` (EU: `https://api.eu.edenai.run/v3`) |
| Key variable | `ANTHROPIC_AUTH_TOKEN` | `ANTHROPIC_AUTH_TOKEN` | `ANTHROPIC_API_KEY` |

- `ANTHROPIC_BASE_URL` replaces Anthropic's API address. Claude Code adds `/v1/messages` itself, so give the URL exactly as the service documents it.
- The two key variables are sent differently. `ANTHROPIC_AUTH_TOKEN` goes out as an `Authorization: Bearer <key>` header, the usual one for gateways. `ANTHROPIC_API_KEY` goes out as an `x-api-key` header, the one Anthropic's own API uses, and Claude Code treats it as a direct Anthropic credential. Use the variable your service documents. When it is `ANTHROPIC_AUTH_TOKEN`, set `ANTHROPIC_API_KEY` to an empty string, as above, so an old Anthropic key left in the environment can't be used instead. For Eden AI, put the key in `ANTHROPIC_API_KEY` and drop the `ANTHROPIC_AUTH_TOKEN` line.
- The EU addresses need an account set up for them: OpenRouter's Business or Enterprise plan, or EU routing on the Eden AI account. OpenRouter documents the `eu.openrouter.ai` host; the `/api` path is assumed to match the global one. See the note in the first entry.
- The native Claude Code installer doesn't read a project `.env` file. To scope the settings to one project, put the same keys in an `"env"` object in that project's `.claude/settings.local.json`, a file Claude Code doesn't expect you to commit.

If you ever logged in to Claude Code with an Anthropic account, that login is cached and conflicts with the new key. Run `/logout` once inside Claude Code, quit, and start `claude` again. `/status` should then show the base URL you set and the key variable you used.

## Give each model class a model

Claude Code doesn't use a single model. It has model classes: Opus for harder reasoning, Sonnet for general coding (the default), Haiku for quick background tasks, plus a model for the subagents it starts for side tasks. One variable per class names the model it uses. Here Opus keeps Claude, and GLM takes the rest:

```bash
export ANTHROPIC_DEFAULT_OPUS_MODEL="anthropic/claude-opus-5.5[1m]"
export ANTHROPIC_DEFAULT_SONNET_MODEL="z-ai/glm-5.3[1m]"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="z-ai/glm-5.3-flash[1m]"
export CLAUDE_CODE_SUBAGENT_MODEL="z-ai/glm-5.3[1m]"
```

Those are OpenRouter's IDs. Each service names the same models differently, and on Opper and Eden AI the ID also selects the provider, and with it the region:

| Model | OpenRouter | Opper | Eden AI |
|---|---|---|---|
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | `anthropic/claude-opus-5-5` (US) | `anthropic/claude-opus-5-5` |
| Claude Opus 5.5, EU | same ID on the EU URL | `aws/claude-opus-5-5` (Bedrock, Sweden) | `amazon/anthropic.claude-opus-5-5@eu` |
| GLM-5.3 | `z-ai/glm-5.3` | `novita/zai-org/glm-5.3` (US) | `zai/glm-5.3` |
| GLM-5.3, EU | same ID on the EU URL | `mistral/zai-glm-5-3` | `mistral/zai-glm-5-3` |
| GLM-5.3 Flash | `z-ai/glm-5.3-flash` | `greenpt/glm-5.3-flash` (EU) | `zai/glm-5.3-flash` |

These come from each service's model list in October 2026 (`GET /api/v1/models` on OpenRouter, `/v3/models` on the other two). Catalogs change often, so check before copying.

Then switch with `/model opus` or `/model sonnet` inside a session, or start with `claude --model opus`. With this setup, `/model sonnet` runs GLM, not a Claude model. The alias names describe a role, not a vendor.

- `[1m]` tells Claude Code the model has a one-million-token context window, so it doesn't compact (summarise) the conversation at 200,000 tokens. OpenRouter documents the marker and strips it before routing, and Z.ai uses it in its own Claude Code setup. Leave it off on a service that doesn't document it, and check the model's real window: some GLM providers serve a smaller one.
- On OpenRouter, the model ID doesn't pick the provider; OpenRouter does. For GLM that can mean a heavily quantized host. To control it, set a [provider order](https://openrouter.ai/docs/guides/routing/provider-selection) in your account settings, for example Z.ai first. For Opus, OpenRouter recommends Anthropic first.

## What to expect from the mix

- **Tool calls.** Claude Code is built and tested with Claude models, and Anthropic doesn't support it with others. Z.ai runs every class on GLM in its own setup, so GLM is meant to handle Claude Code's tool calls, but expect rougher edges than with Claude on long edits. If file edits fail, move that class back to a Claude model.
- **Prompt caching** (reusing an already-processed prompt prefix at a lower price) depends on the provider. A long session costs more on a host that doesn't cache.
- **Thinking.** Claude's extended thinking blocks pass through only where the provider supports them.
- **EU-only sessions.** Use the EU URL on OpenRouter, or the EU model IDs on Opper and Eden AI. Every class has to point to an EU model, the subagent class included, or part of the session leaves the region. Opper also suggests `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` on a network that allows traffic only to the routing service; it turns off Claude Code's version checks, telemetry and error reports.

## The same two models without a routing service

Each vendor also takes Claude Code directly. For Opus that's Anthropic's own API or a Claude subscription. For GLM, Z.ai documents `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic` with a Z.ai key in `ANTHROPIC_AUTH_TOKEN` and IDs such as `glm-5.3[1m]`. But one Claude Code session talks to one base URL. To mix both vendors in one session, you need a routing service, which is what the setup above gives you.

Not tested here, since that needs a key and credits on each service. The settings and IDs come from each service's documentation and model list as of October 2026.

## Sources

- OpenRouter docs: [Claude Code integration](https://openrouter.ai/docs/guides/coding-agents/claude-code-integration), [In-region routing](https://openrouter.ai/docs/guides/features/in-region-routing) and [Provider selection](https://openrouter.ai/docs/guides/routing/provider-selection); model pages for [Claude Opus 5.5](https://openrouter.ai/anthropic/claude-opus-5.5) and [GLM-5.3](https://openrouter.ai/z-ai/glm-5.3).
- Opper docs: [Claude Code](https://docs.opper.ai/integrations/coding-agents/claude-code) and [Run Claude Code on any model](https://docs.opper.ai/guides/claude-code-router).
- Eden AI docs: [Use Claude Code with Eden AI](https://www.edenai.co/docs/v3/integrations/claude-code).
- Z.ai docs: [Claude Code](https://docs.z.ai/devpack/tool/claude).
- Claude Code docs: [LLM gateway configuration](https://code.claude.com/docs/en/llm-gateway-connect#set-the-credential-variable).
