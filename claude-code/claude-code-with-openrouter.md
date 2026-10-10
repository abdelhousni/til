# Using Claude Code with an OpenRouter model: three environment variables and a `/logout`

[OpenRouter](https://openrouter.ai) is an LLM gateway. A gateway is a service that sits between your client and the model providers. You send it every request with one API key, and it forwards each request to a provider (Anthropic, Amazon Bedrock, Google Vertex and others), bills you from one set of prepaid credits, and can switch to another provider when one fails. Claude Code can talk to it with no local proxy, because OpenRouter accepts the same request format as Anthropic's Messages API. OpenRouter calls this compatible endpoint its "Anthropic Skin".

## Point Claude Code at OpenRouter

Claude Code reads its connection settings from environment variables. Create a key at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys), then put these in your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
export OPENROUTER_API_KEY="<your-openrouter-api-key>"
export ANTHROPIC_BASE_URL="https://openrouter.ai/api"
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
export ANTHROPIC_API_KEY=""
```

- `ANTHROPIC_BASE_URL` replaces Anthropic's API address. It needs the scheme and the `/api` path, not just the host name.
- `ANTHROPIC_AUTH_TOKEN` is sent as `Authorization: Bearer <token>`, which is how OpenRouter authenticates.
- `ANTHROPIC_API_KEY` must be set to an empty string. Claude Code sends that variable as an `x-api-key` header and treats it as a direct Anthropic credential. If an old Anthropic key is still set there, Claude Code may authenticate against Anthropic instead.

Two things trip people up here. The line `ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"` is expanded when the profile is read, so `OPENROUTER_API_KEY` must be defined above it, or the token is empty and every request fails with an auth error. And the native Claude Code installer doesn't read a project `.env` file, so the variables must be in the shell environment or in a settings file.

The settings-file form scopes the same values to one project. Use `.claude/settings.local.json`, which Claude Code doesn't expect you to commit, since the key is in it:

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

If you ever logged in to Claude Code with an Anthropic account, that login is cached and conflicts with the gateway credential. Run `/logout` once inside Claude Code, quit, reload your shell (`source ~/.bashrc`) and start `claude` again. Then run `/status`:

```text
Auth token: ANTHROPIC_AUTH_TOKEN
Anthropic base URL: https://openrouter.ai/api
```

If the auth line names `ANTHROPIC_API_KEY`, or a `Login method` line names a Claude account, the variables didn't reach the session. The requests should also appear in the [OpenRouter activity dashboard](https://openrouter.ai/activity).

## Choose the model

Claude Code doesn't ask for one model. It has model classes: Haiku for quick work, Sonnet for general coding, Opus for harder reasoning, and Fable for the most demanding long tasks, plus a model for the subagents it starts for side tasks. Each class has a variable that overrides which model it uses. The value is an OpenRouter model ID, the `provider/model` name shown on each model's page:

```bash
export ANTHROPIC_DEFAULT_OPUS_MODEL="~anthropic/claude-opus-latest[1m]"
export ANTHROPIC_DEFAULT_SONNET_MODEL="~anthropic/claude-sonnet-latest[1m]"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="~anthropic/claude-haiku-latest"
export ANTHROPIC_DEFAULT_FABLE_MODEL="~anthropic/claude-fable-latest[1m]"
export CLAUDE_CODE_SUBAGENT_MODEL="~anthropic/claude-opus-latest[1m]"
```

- A leading `~` and a `-latest` suffix make an alias that follows the newest model of that family. A fixed ID such as `anthropic/claude-opus-5` stays on one version.
- `[1m]` tells Claude Code the model has a one-million-token context window. Without it, Claude Code assumes 200,000 tokens and compacts (summarises) the conversation earlier than it needs to. OpenRouter strips the marker before routing the request.
- Fable isn't offered in `/model` through OpenRouter unless `ANTHROPIC_DEFAULT_FABLE_MODEL` is set.

Open `/model` afterwards to see which classes are listed. Setting `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` adds a picker with a curated list of OpenRouter's top models; restart Claude Code after setting it.

Any OpenRouter model ID can go in those variables, including models from other companies. That is the reason to be careful: Claude Code is built around Anthropic's models and their tool use, and OpenRouter only guarantees it works with Anthropic as the provider. It recommends putting Anthropic first in the [provider order](https://openrouter.ai/docs/guides/routing/provider-selection) of your account. A non-Anthropic model may answer chat prompts fine and still break on file edits or tool calls.

## Fast mode

Claude Code's `/fast` toggle (faster output from some Opus models, at a higher price) needs `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK=1`. It also needs the Opus variable pinned to a fixed ID such as `anthropic/claude-opus-5`. With the `~anthropic/claude-opus-latest` alias, `/fast` reports "Fast mode ON" but sends requests at standard speed.

Not tested here, since it needs an OpenRouter key and credits. The commands and output above are from OpenRouter's guide as of October 2026.

## Sources

- OpenRouter docs: [Claude Code integration](https://openrouter.ai/docs/guides/coding-agents/claude-code-integration).
- Claude Code docs: [LLM gateway configuration](https://code.claude.com/docs/en/llm-gateway-connect#set-the-credential-variable).
