# What is ModelPort?

ModelPort is a local-first control plane for AI model access. It sits between your client and upstream providers so you can standardize request formats, hide provider secrets from local tools, inspect traffic, and switch routing without rewriting clients.

Today the codebase implements these core proxy surfaces:

- `POST /v1/messages` for Anthropic-style clients
- `POST /v1/chat/completions` for OpenAI-style clients
- `GET /v1/models` for OpenAI-style model listing
- `POST /v1/responses` for the OpenAI Responses API (Anthropic upstreams are emulated locally)
- `POST /v1/embeddings` for OpenAI-style embeddings
- `POST /v1/messages/count_tokens` for Anthropic token counting

Around that proxy, ModelPort also ships:

- Bearer-token authentication with `MODELPORT_TOKEN`
- Provider routing by request body, header, or model-id inference
- Streaming and non-streaming responses
- Basic tool-call translation between Anthropic and OpenAI chat shapes
- SQLite-backed request logs, usage snapshots, and estimated cost tracking
- Admin APIs for providers, credentials, pricing overrides, and settings
- Analytics APIs and a dashboard for overview, requests, models, providers, costs, and settings
- `modelport-configure`, an interactive CLI for wiring Claude Code through the proxy

## Architecture

```text
Client
  -> ModelPort bearer token auth
  -> Anthropic/OpenAI request parser
  -> Provider/model route resolver
  -> Request translator
  -> Upstream provider client
  -> Response translator
  -> Usage, cost, health, and I/O logging
  -> Client response
```

## Repository Layout

- `backend/`: FastAPI proxy, routing, translators, tracking, admin APIs, analytics APIs, and tests
- `dashboard/`: Vite-built React dashboard served by FastAPI
- `cli/`: `modelport-configure` CLI package
- `config.yaml`: local provider defaults and database path
- `pricing_catalog.yaml`: seeded pricing overrides

## Current Limits

> **Provider-type caveats:** Some endpoints only work against a matching upstream provider family. Selecting the wrong provider type returns `501 Not Implemented`.

Provider compatibility:

- Anthropic-compatible upstreams support `POST /v1/messages`, `POST /v1/chat/completions`, and `GET /v1/models`. OpenAI-style clients are translated onto Anthropic upstreams when you select a provider with type `anthropic_compatible`.
- `POST /v1/responses` works for both OpenAI-compatible and Anthropic-compatible providers. Against Anthropic, ModelPort emulates the Responses API locally.
- `POST /v1/embeddings`, images, audio, legacy completions, and moderations work only against OpenAI-compatible upstream providers (`501` for Anthropic-compatible providers).
- `POST /v1/messages/count_tokens`, batches, and files work only against Anthropic-compatible providers (`501` for OpenAI-compatible providers).

These features are still planned:

- Dedicated project-scoped auth and permission models
- Automatic background provider health checks and catalog refresh

## Next Steps

- Start with [Quick Start](quick-start.md)
- Learn request routing in [Model Routing](guides/model-routing.md)
- Review the implemented API surfaces in [API Reference](api-reference/messages.md)
