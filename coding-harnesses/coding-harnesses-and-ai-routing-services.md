# Coding harnesses and AI routing services: what each piece does

First entry in the Coding harnesses through an AI routing service series.

This series connects terminal coding agents to models through an AI routing service such as [OpenRouter](https://openrouter.ai), [Opper](https://opper.ai) or [Eden AI](https://www.edenai.co), instead of each model vendor's own API. This entry defines the pieces. Each later entry covers one harness, and the series ends with a comparison and a way to run all of them in containers.

> **A note on choosing where your requests run.** This series gives the local option first wherever one exists: for a reader in Europe, a routing service and model providers that process requests in the EU. That can matter for data protection rules, for latency, or simply as a preference for local providers. Other regions stay available; the point is to make the choice yourself instead of getting whatever the default routing picks. Two places decide where a request runs: where the routing service decrypts and processes it, and where the model provider it forwards it to runs the model. A service hosted in the EU can still forward a request to a provider in another region, and the other way round. As of October 2026:
>
> - **OpenRouter** has in-region routing on its Business and Enterprise plans. You send requests to `https://eu.openrouter.ai` (or `us.openrouter.ai`) instead of `openrouter.ai`, and it routes them only to providers it has onboarded for that region. If none serves the model there, the request fails instead of going to another region. Only part of the catalog is available that way.
> - **Opper** says its gateway is hosted only in the EU. Where inference happens depends on the model you pick, and it marks the EU-hosted ones in its catalog. Rules enforced at the gateway can restrict a key to EU-only providers.
> - **Eden AI** is headquartered in the EU and documents an EU endpoint, `https://api.eu.edenai.run/v3`. It notes that not every model has an EU deployment, and that fallback models may not have one either.
>
> These are the vendors' own claims. If you need them for compliance, read their data processing agreements (DPAs) and check where the exact model and its fallbacks are served.

## The pieces

- **Model**: the large language model (LLM) that reads your prompt and writes the answer, such as Claude, GPT, Gemini, Qwen or Mistral. It is identified by a *model ID*, a string like `anthropic/claude-sonnet-5`.
- **Model provider**: the company whose servers run the model and answer API calls. It is often the vendor that made the model (Anthropic, OpenAI), but cloud platforms such as Amazon Bedrock and Google Vertex AI serve the same models from their own data centres, and smaller hosts serve open-weight models (models whose weights are published, so anyone can run them).
- **Coding harness**: the program on your machine that turns a model into a coding agent. It sends your request and the relevant files to the model, lets the model call *tools* (read a file, edit it, run a command), runs those tools, sends back the results, and loops until the task is done. Claude Code, OpenCode, Codex CLI, Qwen Code and Oh My Pi are harnesses. The model decides what to do; the harness is what actually touches your files.
- **AI routing service** (also called an LLM gateway or router): a service that sits between the harness and the model providers. You hold one API key and one account with it. It receives every request, picks a provider for the model you asked for, forwards the request, and bills you from prepaid credits. It can also switch to another provider when one fails, cap spending per key, and show usage per person or project.

## Two API formats

A harness talks to a model over HTTPS in one of two request formats, and that decides how it connects to a routing service:

- The **Anthropic Messages API** format (`POST /v1/messages`), used by Claude Code.
- The **OpenAI-compatible** format, the shape of OpenAI's Chat Completions API (`POST /v1/chat/completions`), which most other harnesses and most model providers accept. "Compatible" means another service accepts the same JSON body, so a client written for OpenAI works by changing only the address it sends to.

Routing services accept one or both formats and translate where needed. OpenRouter, Opper and Eden AI all accept both, which is why the same three-line change works for very different harnesses.

## How a harness is pointed at a routing service

Almost always with three settings, through environment variables or the harness's own config file:

- a **base URL**, the address that replaces the vendor's default API address;
- an **API key** from the routing service, sent in an HTTP header;
- a **model ID** in the routing service's naming, usually `vendor/model`.

The harness doesn't know it is talking to a router. That is the point, and also the risk: a harness built around one vendor's models (Claude Code around Claude, Codex CLI around OpenAI's models) may handle another vendor's models poorly. The usual symptom is a model that chats fine but fumbles tool calls, the step where it edits files or runs commands.

## What it costs and what changes

- **Billing**: you pay the routing service per token (a token is a chunk of text, roughly three quarters of an English word), not a monthly subscription. A Claude or ChatGPT subscription doesn't apply while the harness uses a routing-service key.
- **Features**: vendor-specific features such as prompt caching (reusing an already-processed prompt prefix at a lower price) or a faster priority tier work only when the provider that serves the request supports them.
- **Where it runs**: the routing service processes your code as well as the model provider, so you choose both, as the note at the top describes.

## Sources

- OpenRouter docs: [In-region routing](https://openrouter.ai/docs/guides/features/in-region-routing) and [Sovereign AI](https://openrouter.ai/docs/guides/features/sovereign-ai).
- Opper docs: [Gateway](https://docs.opper.ai/overview/gateway) and [Run Claude Code on any model](https://docs.opper.ai/guides/claude-code-router).
- Eden AI: [EU AI endpoint: how to keep AI requests and data in Europe](https://www.edenai.co/post/eu-ai-endpoint-how-to-keep-ai-requests-and-data-in-europe).
