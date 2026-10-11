# OpenCode through an AI routing service, with Claude Opus and Z.ai GLM

Third entry in the Coding harnesses through an AI routing service series.

[OpenCode](https://opencode.ai) is an open-source coding harness for the terminal (MIT licence). Unlike Claude Code, it isn't tied to one vendor. It talks to models through the [AI SDK](https://ai-sdk.dev), a JavaScript library with one adapter package per API, and gets its list of providers and models from [models.dev](https://models.dev), a public registry. OpenRouter, Opper and Eden AI are all in that registry, so all three work with just an API key.

This entry uses the same two models as [the Claude Code entry](claude-code-with-two-models-through-a-routing-service.md), which explains why: Claude Opus for the hard reasoning and GLM for the everyday work. [The first entry](coding-harnesses-and-ai-routing-services.md) defines the terms.

## Give OpenCode the key

Each service is a built-in OpenCode provider with its own key variable:

| | OpenRouter | Opper | Eden AI |
|---|---|---|---|
| Provider ID in OpenCode | `openrouter` | `opper` | `edenai` |
| Key variable | `OPENROUTER_API_KEY` | `OPPER_API_KEY` | `EDENAI_API_KEY` |
| Default base URL | `https://openrouter.ai/api/v1` | `https://api.opper.ai/v3/compat` | `https://api.edenai.run/v3` |

Either export the variable before starting `opencode`, or run `/connect` inside OpenCode, pick the service and paste the key. `/connect` stores the key in `~/.local/share/opencode/auth.json`. Unlike Claude Code, OpenCode doesn't need you to blank out other variables, because each provider reads only its own.

OpenCode doesn't load `.env` files. To keep a key out of the config file, the config can reference it as `{env:VARIABLE}` or `{file:path}`, and OpenCode substitutes the value when it starts.

## Choose which model does what

OpenCode doesn't have Claude Code's model classes. It has *agents*, each a role with its own prompt, permissions and, optionally, model:

- **Build**, the default primary agent, with every tool enabled: it edits files and runs commands.
- **Plan**, a primary agent restricted to reading: it analyses the code and proposes changes without making them. **Tab** switches between Build and Plan during a session.
- **Subagents** such as General and Explore, which a primary agent starts for side tasks. Without a model of their own, they use the model of the agent that started them.
- `small_model`, used for light tasks such as session titles.

A model reference is `provider/model`, where `model` is the service's own ID. So on OpenRouter it has three segments: `openrouter/z-ai/glm-5.3`.

Here Plan gets Opus, for the thinking before any change, and Build gets GLM, for the edits that follow. Put this in `~/.config/opencode/opencode.json` for all projects, or in `opencode.json` at a project's root, which takes precedence:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/z-ai/glm-5.3",
  "small_model": "openrouter/z-ai/glm-5.3-flash",
  "agent": {
    "plan": { "model": "openrouter/anthropic/claude-opus-5.5" }
  }
}
```

The same references on the other two services:

| Role | OpenRouter | Opper | Eden AI |
|---|---|---|---|
| Plan (Opus) | `openrouter/anthropic/claude-opus-5.5` | `opper/claude-opus-5` | `edenai/anthropic/claude-opus-5-5` |
| Build (GLM) | `openrouter/z-ai/glm-5.3` | `opper/glm-5.3` | `edenai/zai/glm-5.3` |
| `small_model` | `openrouter/z-ai/glm-5.3-flash` | `opper/glm-5.3-flash` | `edenai/zai/glm-5.3-flash` |

These are the IDs models.dev listed in October 2026, which is what `/models` shows. Opper's entries there are *pools*: a bare name such as `glm-5.3` that Opper balances across the providers serving it, without a region. Its registry list had Opus 5, not 5.5. To use a model the registry doesn't have, declare it yourself, as the EU section below does.

## Choose the provider behind GLM on OpenRouter

On OpenRouter the model ID doesn't pick the provider, and about forty serve GLM-5.3, many of them *quantized* (run at reduced precision, cheaper but sometimes worse). OpenCode passes OpenRouter's routing preferences per model:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {
      "models": {
        "z-ai/glm-5.3": {
          "options": {
            "provider": { "order": ["z-ai"], "allow_fallbacks": false }
          }
        }
      }
    }
  }
}
```

`order` lists the providers to try first (`z-ai` is Z.ai's own endpoint), and `allow_fallbacks: false` makes the request fail rather than go to any other provider.

## Keep it in the EU

Every model the session uses has to be served in the EU, including `small_model` and the subagents' models, or part of the session leaves the region. See the note in the first entry for what each service guarantees.

- **OpenRouter**: override the base URL, and keep the same model IDs. This needs an account on OpenRouter's Business or Enterprise plan.

  ```json
  { "provider": { "openrouter": { "options": { "baseURL": "https://eu.openrouter.ai/api/v1" } } } }
  ```

- **Eden AI**: OpenCode's docs give the EU base URL, `https://api.eu.edenai.run/v3`, in the same `options.baseURL` field under `edenai`. The EU endpoint serves only part of the catalog.
- **Opper**: the region is part of the model ID, and the EU IDs aren't in the registry, so declare them. OpenCode merges declared models with the registry's, and needs their context and output limits to know when to compact:

  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "provider": {
      "opper": {
        "models": {
          "aws/claude-opus-5-5": { "name": "Claude Opus 5.5 (EU)", "limit": { "context": 1000000, "output": 128000 } },
          "mistral/zai-glm-5-3": { "name": "GLM-5.3 (EU)", "limit": { "context": 1048576, "output": 131072 } }
        }
      }
    },
    "model": "opper/mistral/zai-glm-5-3",
    "small_model": "opper/mistral/zai-glm-5-3",
    "agent": { "plan": { "model": "opper/aws/claude-opus-5-5" } }
  }
  ```

  The same works on Eden AI for its EU IDs, `amazon/anthropic.claude-opus-5-5@eu` and `mistral/zai-glm-5-3`. The limits above are the ones models.dev lists for the same models under their global IDs; check the service's model list (`GET /v3/models`) in case a regional provider serves less.

## Differences from Claude Code

- OpenCode sends the OpenAI-compatible format to Opper and Eden AI, and OpenRouter has its own AI SDK adapter. Neither is the Anthropic format Claude Code uses, so Claude-specific features such as extended thinking or prompt caching depend on how the service translates them.
- OpenCode is built for many vendors' models and recommends some by name. GLM isn't a guest here the way it is in Claude Code, but tool-call quality still varies by model and by provider.
- Opper's CLI also has `npx @opperai/cli launch opencode`, which writes a provider block with the models your key may use, including pools and Opper's dynamic routes.

Not tested here, since that needs a key and credits on each service. The settings come from OpenCode's documentation, the models.dev registry and each service's docs as of October 2026.

## Sources

- OpenCode docs: [Providers](https://opencode.ai/docs/providers/), [Models](https://opencode.ai/docs/models/), [Agents](https://opencode.ai/docs/agents/) and [Config](https://opencode.ai/docs/config/).
- [models.dev](https://models.dev) registry (`/api.json`).
- Opper docs: [OpenCode](https://docs.opper.ai/integrations/coding-agents/opencode).
- OpenRouter docs: [Provider selection](https://openrouter.ai/docs/guides/routing/provider-selection) and [In-region routing](https://openrouter.ai/docs/guides/features/in-region-routing).
