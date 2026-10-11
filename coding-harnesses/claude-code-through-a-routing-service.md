# Claude Code through an AI routing service: OpenRouter, Opper and Eden AI

Second entry in the Coding harnesses through an AI routing service series.

Claude Code speaks the Anthropic Messages API, and the routing services in this series accept that format directly, so no local proxy is needed. [The first entry](coding-harnesses-and-ai-routing-services.md) explains what a harness, a routing service and the two API formats are. Here the change comes down to a base URL, an API key in the right variable, and model IDs.

## The settings for each service

Claude Code reads its connection settings from environment variables. Put them in your shell profile (`~/.bashrc` or `~/.zshrc`) and reload it.

| | OpenRouter | Opper | Eden AI |
|---|---|---|---|
| `ANTHROPIC_BASE_URL` | `https://openrouter.ai/api` (EU: `https://eu.openrouter.ai/api`) | `https://api.opper.ai/v3/compat` | `https://api.edenai.run/v3` (EU: `https://api.eu.edenai.run/v3`) |
| Key goes in | `ANTHROPIC_AUTH_TOKEN` | `ANTHROPIC_AUTH_TOKEN` | `ANTHROPIC_API_KEY` |
| Also set | `ANTHROPIC_API_KEY=""` | — | — |

For OpenRouter, for example:

```bash
export OPENROUTER_API_KEY="<your-openrouter-api-key>"
export ANTHROPIC_BASE_URL="https://openrouter.ai/api"
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
export ANTHROPIC_API_KEY=""
```

- `ANTHROPIC_BASE_URL` replaces Anthropic's API address. Claude Code adds `/v1/messages` itself, so give the URL exactly as the service documents it, scheme and path included.
- The two key variables are sent differently. `ANTHROPIC_AUTH_TOKEN` goes out as `Authorization: Bearer <token>`, the usual header for gateways. `ANTHROPIC_API_KEY` goes out as an `x-api-key` header, the one Anthropic's own API uses, and Claude Code treats it as a direct Anthropic credential. OpenRouter and Opper document the first; Eden AI documents the second. Use the one your service documents.
- OpenRouter says to set `ANTHROPIC_API_KEY` to an empty string, so that an old Anthropic key left in your environment can't be used instead.
- The OpenRouter EU URL needs an account on OpenRouter's Business or Enterprise plan; see the note in the first entry. OpenRouter documents the `eu.openrouter.ai` host; the `/api` path is assumed to match the global one. Eden AI's EU URL applies when your account is set up for EU routing.
- Opper also has a one-command launcher, `npx @opperai/cli launch claude`, which sets the two variables for that session only.

Two common mistakes. In the profile above, `OPENROUTER_API_KEY` must be defined before the line that uses it, or the token is empty and every request fails with an auth error. And the native Claude Code installer doesn't read a project `.env` file, so the variables must be in the shell environment or in a settings file.

To scope the settings to one project, put them in that project's `.claude/settings.local.json`. Claude Code doesn't expect you to commit that file, which matters because the key is in it:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
    "ANTHROPIC_AUTH_TOKEN": "<your-openrouter-api-key>",
    "ANTHROPIC_API_KEY": ""
  }
}
```

## Clear the old login, then check

If you ever logged in to Claude Code with an Anthropic account, that login is cached and conflicts with the routing-service credential. Run `/logout` once inside Claude Code, quit, reload your shell and start `claude` again. Then run `/status`. With OpenRouter it should show:

```text
Auth token: ANTHROPIC_AUTH_TOKEN
Anthropic base URL: https://openrouter.ai/api
```

If the auth line names the wrong variable, or a `Login method` line names a Claude account, the variables didn't reach the session. Each service's dashboard also lists the requests as they arrive.

## Choose the models

Claude Code doesn't use a single model. It has model classes: Haiku for quick work, Sonnet for general coding, Opus for harder reasoning, Fable for the most demanding long tasks, plus a model for the subagents it starts for side tasks. One variable per class says which model ID the class uses, in the routing service's naming:

```bash
export ANTHROPIC_DEFAULT_OPUS_MODEL="~anthropic/claude-opus-latest[1m]"
export ANTHROPIC_DEFAULT_SONNET_MODEL="~anthropic/claude-sonnet-latest[1m]"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="~anthropic/claude-haiku-latest"
export ANTHROPIC_DEFAULT_FABLE_MODEL="~anthropic/claude-fable-latest[1m]"
export CLAUDE_CODE_SUBAGENT_MODEL="~anthropic/claude-opus-latest[1m]"
```

These are OpenRouter's IDs. On Opper a fixed ID looks like `anthropic/claude-sonnet-5`, and Eden AI uses `anthropic/claude-sonnet-latest`. Check the catalog of the service you use.

- On OpenRouter, a leading `~` and a `-latest` suffix make an alias that follows the newest model of the family. A fixed ID such as `anthropic/claude-opus-5` stays on one version.
- `[1m]` tells Claude Code the model has a one-million-token context window (a token is a chunk of text, roughly three quarters of a word). Without it, Claude Code assumes 200,000 tokens and compacts (summarises) the conversation earlier than it needs to. OpenRouter strips the marker before routing the request.
- Through OpenRouter, Fable isn't offered in `/model` unless `ANTHROPIC_DEFAULT_FABLE_MODEL` is set.

Open `/model` afterwards to see which classes are listed. `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` adds models fetched from the routing service to the picker; restart Claude Code after setting it.

Any model ID from the catalog fits in those variables, including other vendors' models: Opper's own example maps the Haiku class to a Gemini model. That is where to be careful. Claude Code is built around Claude models and their tool calls, Anthropic doesn't support it with other models, and OpenRouter only guarantees it with Anthropic as the provider (it recommends putting Anthropic first in your account's [provider order](https://openrouter.ai/docs/guides/routing/provider-selection)). A model that answers chat prompts well can still break on file edits.

For EU-only sessions, both the URL and the model matter. Opper's guide suggests picking a model it marks as EU-hosted, such as a Mistral model. On a network that allows traffic only to the routing service, it also suggests setting `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, which turns off Claude Code's version checks, telemetry and error reports.

## Fast mode on OpenRouter

Claude Code's `/fast` toggle (faster output from some Opus models, at a higher price) works through OpenRouter with `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK=1`. It also needs the Opus variable pinned to a fixed ID such as `anthropic/claude-opus-5`. With the `~anthropic/claude-opus-latest` alias, `/fast` reports "Fast mode ON" but sends requests at standard speed.

Not tested here, since that needs a key and credits on each service. The settings above come from each service's own guide as of October 2026.

## Sources

- OpenRouter docs: [Claude Code integration](https://openrouter.ai/docs/guides/coding-agents/claude-code-integration) and [In-region routing](https://openrouter.ai/docs/guides/features/in-region-routing).
- Opper docs: [Claude Code](https://docs.opper.ai/integrations/coding-agents/claude-code) and [Run Claude Code on any model](https://docs.opper.ai/guides/claude-code-router).
- Eden AI docs: [Use Claude Code with Eden AI](https://www.edenai.co/docs/v3/integrations/claude-code).
- Claude Code docs: [LLM gateway configuration](https://code.claude.com/docs/en/llm-gateway-connect#set-the-credential-variable).
