<h1 align="center">ModelPort</h1>

ModelPort is a local-first control plane for AI model access. It gives developers one private place to route requests across providers, keep real provider credentials out of client tools, observe usage and cost, inspect request behavior, and manage the models and providers available to local AI workflows.

The bigger goal is to make model access portable across clients, providers, and response formats. ModelPort should support Anthropic-compatible and OpenAI-compatible clients, provider failover, usage analytics, model catalogs, pricing visibility, and eventually custom response schemas and structured output formats.

The current default runtime is:

- Backend proxy/API: `http://127.0.0.1:13243`
- Dashboard UI: `http://localhost:3000`
- Database: `./data/modelport.db`
- Config: `./config.yaml`
- Provider credentials: `.env`

## Current Status

Working today:

- FastAPI proxy with bearer-token auth via `MODELPORT_TOKEN`.
- `POST /v1/messages` for Anthropic-style clients.
- `GET /v1/models` and `POST /v1/chat/completions` for OpenAI-style clients.
- `POST /v1/responses` for both OpenAI-compatible and Anthropic-compatible providers (Anthropic emulated locally).
- `POST /v1/embeddings`, images, audio, legacy completions, and moderations against OpenAI-compatible upstreams (`501` for Anthropic providers).
- `POST /v1/messages/count_tokens`, batches, and files against Anthropic-compatible upstreams (`501` for OpenAI-compatible providers).
- Streaming and non-streaming chat completions.
- Request normalization between Anthropic and OpenAI chat shapes for the current OpenAI-compatible upstream path, including basic tool calls/tool results.
- Provider routing by request body `provider`, `fallback_providers`, or `X-ModelPort-Provider`.
- Seeded provider config for OpenAI, Anthropic, Gemini OpenAI compatibility, OpenRouter, and Ollama.
- SQLite-backed request logs, provider settings, credentials metadata, pricing overrides, provider health snapshots, and model metadata.
- Admin and analytics APIs for dashboard pages.
- Dashboard pages for overview, requests, models, providers, costs, and settings.
- Model directory metadata from OpenRouter, Gemini native model listing, local providers, pricing catalog entries, and observed usage.
- Pricing seed from `pricing_catalog.yaml`.
- Backend pytest coverage for proxy routes, analytics, admin settings, request tracking, model metadata, pricing seed, tool translation, and ID generation.
- Interactive `modelport-configure` CLI for wiring Claude Code (and future agents) through the proxy.

Still in progress:

- Native Anthropic-compatible upstream providers are supported for `POST /v1/messages`, `POST /v1/chat/completions`, and `GET /v1/models`.
- The dashboard expects the backend to be running; it is no longer just a static mock dashboard.
- Provider health is based on recent runtime/API observations rather than a dedicated background health-check loop.
- API keys can be stored in environment variables or encrypted database credentials, but local `.env` remains the simplest path for development.

Future plans:

- Broader provider-specific capability coverage beyond the current OpenAI/Anthropic compatibility surfaces.
- Custom response schemas and structured output formats that can be managed consistently across providers.
- More advanced routing policies, including automatic fallback, cost-aware routing, latency-aware routing, and model capability matching.
- Dedicated provider health checks and background model catalog refresh.
- Safer credential management options such as OS keychain, 1Password, Doppler, Vault, or other secret backends.
- Export, retention, and cleanup workflows for request logs, analytics, and stored I/O payloads.
- A future macOS companion app for monitoring local computer stats, managing the proxy from the desktop, and eventually running local models directly.

## Architecture

```txt
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

Repository layout:

- `backend/`: FastAPI proxy, admin APIs, analytics APIs, SQLAlchemy models, translators, routing, pricing, and tests.
- `dashboard/`: Next.js 16 / React 19 dashboard using Tailwind CSS 4 and shadcn/Radix UI primitives.
- `config.yaml`: local provider defaults and database location.
- `.env.example`: required local environment variables.
- `pricing_catalog.yaml`: model pricing seed data.
- `cli/`: interactive agent configuration package (`modelport-configure`).
- `bin/`: repository convenience scripts (including `./bin/modelport-configure`).
- `docs/`: Fumadocs documentation site.

## Quick Start

Create local environment variables:

```bash
cp .env.example .env
```

At minimum, set:

```bash
MODELPORT_TOKEN=dev-modelport-token
```

Then add whichever provider keys you want to use:

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
GROQ_API_KEY=
TOGETHER_API_KEY=
```

Install and run the backend from the repository root:

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
set -a; source .env; set +a
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 13243
```

Install and run the dashboard:

```bash
cd dashboard
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

If the backend is not running on `http://127.0.0.1:13243`, set this for the dashboard:

```bash
NEXT_PUBLIC_MODELPORT_BACKEND_URL=http://127.0.0.1:13243
```

## Using the Proxy

All proxy endpoints require:

```txt
Authorization: Bearer <MODELPORT_TOKEN>
```

Provider selection is required unless the model id includes a recognized provider or native prefix. Pass either:

- Header: `X-ModelPort-Provider: openrouter`
- Request body: `"provider": "openrouter"`

When provider is omitted, ModelPort infers routing from the model id:

- ModelPort provider prefix: `openrouter/google/gemini-2.5-flash`, `gemini/models/gemini-2.5-flash`, `openai/gpt-4.1`
- OpenRouter-owned models: `openrouter/auto` (sent upstream as `openrouter/auto`, not `openrouter/openrouter/auto`)
- Native prefixes: `google/gemini-2.5-flash` routes to OpenRouter; any other `vendor/model` id routes to OpenRouter when the vendor is not a configured ModelPort provider (e.g. `nvidia/nemotron-3.5-content-safety:free`); `models/gemini-2.5-flash` routes to Gemini
- Bare model ids such as `gpt-4.1` still require an explicit provider

Fallback routing can be passed with:

```json
{
  "fallback_providers": ["gemini", "ollama"]
}
```

The client endpoint format and upstream model family are independent. These examples intentionally cross them to show the proxy translation layer.

OpenAI-compatible client request routed to an Anthropic-family model through OpenRouter:

```bash
curl http://127.0.0.1:13243/v1/chat/completions \
  -H "Authorization: Bearer $MODELPORT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-ModelPort-Provider: openrouter" \
  -d '{
    "model": "anthropic/claude-sonnet-4",
    "messages": [
      { "role": "user", "content": "Say hello from ModelPort." }
    ]
  }'
```

Anthropic-compatible client request routed to an OpenAI-family model through OpenRouter:

```bash
curl http://127.0.0.1:13243/v1/messages \
  -H "Authorization: Bearer $MODELPORT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-ModelPort-Provider: openrouter" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "max_tokens": 128,
    "messages": [
      { "role": "user", "content": "Say hello from ModelPort." }
    ]
  }'
```

For Anthropic-style clients that support base URL configuration:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:13243
export ANTHROPIC_AUTH_TOKEN=$MODELPORT_TOKEN
```

### Configure Claude Code with `modelport-configure`

`modelport-configure` is an interactive CLI that writes Claude Code settings so requests go through ModelPort (proxy URL, bearer token, and optional default models). Provider routing is inferred from model ids—no `X-ModelPort-Provider` header is required. The package is agent-pluggable; more clients can be added under `cli/modelport_agent_config/agents/`.

Run from the repository root (uses `cli/.venv` when it exists):

```bash
./bin/modelport-configure
```

Or install the CLI and run it from anywhere:

```bash
python -m venv cli/.venv && source cli/.venv/bin/activate
pip install -e cli/
modelport-configure
```

**Interactive flow**

1. **Scope** — global (`~/.claude/settings.json`), project (`.claude/settings.json`), or local (`.claude/settings.local.json`).
2. **Proxy** — base URL (defaults from `config.yaml`) and `MODELPORT_TOKEN` (from `.env` when set). The tool probes the proxy when possible.
3. **Models** — provider-tabbed picker (switch tabs to browse openrouter, gemini, openai, etc.; search within the active tab). Pick default and optional Sonnet / Opus / Haiku overrides from different providers.
4. **Summary** — review routed model ids and confirm; existing non-ModelPort keys are preserved.

Restart Claude Code after applying changes.

**Non-interactive example**

```bash
modelport-configure \
  --agent claude-code \
  --scope project \
  --project-dir . \
  --base-url http://127.0.0.1:13243 \
  --token "$MODELPORT_TOKEN" \
  --model anthropic/claude-sonnet-4 \
  --sonnet-model models/gemini-2.5-flash \
  --yes
```

`modelport-configure --help` lists all flags (`--dry-run`, `--json`, tier model overrides, etc.). See `cli/README.md` for file layout and adding another agent adapter.

## Dashboard

The dashboard reads live data from the backend through:

- `/analytics/overview`
- `/analytics/requests`
- `/analytics/models`
- `/analytics/costs`
- `/admin/providers`
- `/admin/providers/health`
- `/admin/providers/models`
- `/admin/settings`

Main pages:

- Overview: high-level token, cost, latency, model, usage, and recent request summary.
- Requests: searchable/sortable request log with request details and optional I/O inspector.
- Models: provider model directory with metadata, pricing, modality, context, usage, and provider filters.
- Providers: provider health and routing details.
- Costs: estimated spend over time, by provider/model, and high-cost recent requests.
- Settings: providers, credentials, pricing, tracking toggles, theme, and refresh interval.

I/O logging is disabled by default. It can be enabled in Settings or from the Requests page when inspecting a request. When enabled, request and response bodies are stored in SQLite, so treat the local database as sensitive.

## Configuration

`config.yaml` controls the server, database, token environment variable name, and seeded providers:

```yaml
server:
  host: "127.0.0.1"
  port: 13243

security:
  modelport_token: "MODELPORT_TOKEN"

database:
  url: "sqlite:///./data/modelport.db"
```

Provider entries include:

- `type`: `openai_compatible`, `anthropic_compatible`, or `local_openai_compatible`
- `display_name`
- `base_url`
- `api_key_env`

Local OpenAI-compatible providers like Ollama can run without an API key.

## Development

Run backend tests:

```bash
cd backend
pytest
```

Run dashboard lint:

```bash
cd dashboard
pnpm lint
```

Run agent-configure CLI tests:

```bash
cd cli
python -m venv .venv && source .venv/bin/activate
pip install -e .
pytest
```

Useful backend modules:

- `backend/app/api/openai.py`: OpenAI-compatible proxy routes.
- `backend/app/api/anthropic.py`: Anthropic-compatible proxy route.
- `backend/app/api/admin.py`: provider, credential, pricing, and settings APIs.
- `backend/app/api/analytics.py`: dashboard analytics APIs.
- `backend/app/translators/`: request/response translation.
- `backend/app/routing/provider_router.py`: provider and fallback route resolution.
- `backend/app/tracking/`: usage, cost, pricing, and request logging.
- `backend/app/model_metadata_service.py`: provider model catalog and metadata aggregation.

## Security Notes

ModelPort is designed as a local development tool. Do not expose the backend directly to an untrusted network.

- Keep real provider API keys out of client tools; clients should only receive the local ModelPort URL and `MODELPORT_TOKEN`.
- Raw provider keys from `.env` are not displayed in the dashboard.
- Database-stored credentials are encrypted using `PROXY_ENCRYPTION_KEY`.
- Request/response body logging can capture prompts, completions, tool inputs, and other sensitive data.
