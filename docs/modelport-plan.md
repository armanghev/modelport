# Local AI Proxy - Full Build Plan

# Project summary

Build a local AI proxy that lets AI clients talk to many model providers through one local endpoint.

Main use case:

```
Claude Code
  ↓ ANTHROPIC_BASE_URL=http://localhost:8000
Local AI Proxy
  ↓ automatic API translation + routing
Gemini / GPT / Claude / OpenRouter / Ollama / LM Studio
```

The proxy should support both Anthropic-compatible and OpenAI-compatible APIs, expose a unified model list, route requests by model alias/provider, use real provider API keys internally, and track usage/cost/logs in a clean dashboard.

# Final architecture decision

Use this split:

```
FastAPI backend = proxy engine, auth, routing, translation, provider calls, usage tracking, logs
Next.js dashboard = visual UI for overview, requests, logs, models, providers, costs, settings
SQLite = local-first database for request records, logs, provider health, aliases, settings metadata
.env = v1 provider key storage
config.yaml = providers, aliases, routing, pricing, defaults
```

Why this split:

- FastAPI is better for a long-running local proxy, streaming responses, request validation, and provider integrations.
- Next.js is better for the dashboard UI.
- SQLite is enough for local-first usage and easy to migrate later.

# Core flow

```
Client
  ↓
Local proxy token auth
  ↓
Input API detector
  ↓
Request normalizer
  ↓
Model alias resolver
  ↓
Provider router
  ↓
Request translator
  ↓
Provider client
  ↓
Response translator
  ↓
Usage tracker + logs
  ↓
Client response
```

Runtime:

```
Proxy API:      http://localhost:8000
Dashboard UI:  http://localhost:3000
SQLite DB:     ./data/proxy.db
Config file:   ./config.yaml
Env file:      ./.env
```

# Claude Code setup

Claude Code should only receive the local endpoint and local proxy token.

```bash
export ANTHROPIC_BASE_URL=http://localhost:8000
export ANTHROPIC_AUTH_TOKEN=dev-local-proxy-token
```

Claude Code never receives the real OpenAI, Gemini, Anthropic, OpenRouter, Groq, or other provider keys.

# API compatibility targets

## Anthropic-compatible endpoints

Required first:

```
POST /v1/messages
GET  /v1/models
```

Later:

```
POST /v1/messages/count_tokens
```

## OpenAI-compatible endpoints

Required first:

```
POST /v1/chat/completions
GET  /v1/models
```

Later:

```
POST /v1/responses
POST /v1/embeddings
```

# Provider support

Start with provider types:

```
openai_compatible
anthropic_compatible
local_openai_compatible
```

Early providers:

```
OpenAI
Anthropic
Gemini through OpenAI compatibility
OpenRouter
Ollama through OpenAI compatibility or native API later
LM Studio through OpenAI-compatible local endpoint
Groq
Together AI
Fireworks AI
```

Do not start with native Gemini. Use Gemini's OpenAI-compatible endpoint first because it keeps the translation layer simpler.

# API key storage

## v1: .env keys only

```
LOCAL_PROXY_TOKEN=dev-local-proxy-token

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OPENROUTER_API_KEY=sk-or-...
GROQ_API_KEY=gsk_...
TOGETHER_API_KEY=...
```

The dashboard should only show configured/missing status and masked hints.

Example:

```
OpenAI       Configured     sk-••••••••••AB12
Anthropic    Configured     sk-ant-••••••9XZ4
Gemini       Configured     AIza••••••••PQ8
OpenRouter   Missing        Not configured
```

The frontend should never fetch or display raw keys.

## v2: encrypted key storage

Later, allow adding/updating keys from the dashboard. The dashboard sends the key once to FastAPI, FastAPI encrypts it, and SQLite stores only encrypted values.

```sql
CREATE TABLE provider_credentials (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL UNIQUE,
  encrypted_api_key TEXT NOT NULL,
  key_hint TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

One encryption secret stays in `.env`:

```
PROXY_ENCRYPTION_KEY=long-random-secret
```

## v3: optional keychain support

Future options:

```
macOS Keychain
1Password CLI
Doppler
Vault
Bitwarden Secrets Manager
```

# config.yaml

```yaml
server:
  host: "127.0.0.1"
  port: 8000

security:
  local_proxy_token_env: "LOCAL_PROXY_TOKEN"

database:
  url: "sqlite:///./data/proxy.db"

defaults:
  input_format: "anthropic"
  provider: "openrouter"
  model: "claude-sonnet"

providers:
  openai:
    type: "openai_compatible"
    display_name: "OpenAI"
    base_url: "https://api.openai.com/v1"
    api_key_env: "OPENAI_API_KEY"

  anthropic:
    type: "anthropic_compatible"
    display_name: "Anthropic"
    base_url: "https://api.anthropic.com"
    api_key_env: "ANTHROPIC_API_KEY"

  gemini:
    type: "openai_compatible"
    display_name: "Gemini"
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai"
    api_key_env: "GEMINI_API_KEY"

  openrouter:
    type: "openai_compatible"
    display_name: "OpenRouter"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"

  ollama:
    type: "openai_compatible"
    display_name: "Ollama"
    base_url: "http://localhost:11434/v1"
    api_key_env: null

model_aliases:
  claude-sonnet:
    provider: "anthropic"
    model: "claude-3-5-sonnet-latest"
    description: "Default high-intelligence Claude model"

  gpt:
    provider: "openai"
    model: "gpt-4.1"
    description: "Default GPT model"

  gemini:
    provider: "gemini"
    model: "gemini-2.5-pro"
    description: "Default Gemini reasoning model"

  fast:
    provider: "openai"
    model: "gpt-4o-mini"
    description: "Low-latency, cost-efficient model"

  local:
    provider: "ollama"
    model: "qwen2.5-coder"
    description: "Local coding model through Ollama"
```

# Model switching behavior

Resolve model choice in this order:

```
1. Request body model field
2. Header override, for example x-proxy-model
3. Environment variable PROXY_MODEL
4. config.yaml default model
```

Example request:

```json
{
  "model": "gemini",
  "messages": []
}
```

Proxy resolves:

```
alias: gemini
provider: gemini
real model: gemini-2.5-pro
provider format: OpenAI-compatible
base URL: Gemini OpenAI-compatible endpoint
key: GEMINI_API_KEY
```

# Model exposure

Expose configured models through:

```
GET /v1/models
```

Return both local aliases and real provider models.

Example local model aliases:

```
claude-sonnet
claude-haiku
gpt
gpt-4.1
gemini
fast
cheap
local
```

v1 can expose static config models only. Later versions can fetch live provider model lists and merge them into a normalized registry.

# Translation layer

Core translators:

```
Anthropic request → OpenAI request
OpenAI response → Anthropic response
OpenAI request → Anthropic request
Anthropic response → OpenAI response
```

First required path:

```
Anthropic /v1/messages → OpenAI-compatible /v1/chat/completions
```

This is needed for Claude Code using Gemini, GPT, OpenRouter, Ollama, or LM Studio.

# Anthropic to OpenAI mapping

Anthropic input:

```json
{
  "model": "claude-sonnet",
  "max_tokens": 4096,
  "system": "You are helpful.",
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    }
  ]
}
```

OpenAI-compatible output:

```json
{
  "model": "gpt-4.1",
  "max_tokens": 4096,
  "messages": [
    {
      "role": "system",
      "content": "You are helpful."
    },
    {
      "role": "user",
      "content": "Hello"
    }
  ]
}
```

# Content block handling

Anthropic content can be simple strings or structured blocks.

MVP supports:

```
text blocks
```

Later:

```
image blocks
tool_use blocks
tool_result blocks
```

Unsupported content should return a clear compatibility error instead of silently mangling the request.

# Streaming

Streaming is important for Claude Code. MVP can start without it, but streaming should come soon after basic requests work.

Target Anthropic-style event flow:

```
message_start
content_block_start
content_block_delta
content_block_stop
message_delta
message_stop
```

Implementation concept:

```
Provider stream chunk
  ↓
Normalize chunk
  ↓
Convert to client-compatible event
  ↓
Yield SSE frame
```

# Tool calls

Tool calls matter for Claude Code compatibility.

Translation goals:

```
Anthropic tool_use → OpenAI tool_calls
Anthropic tool_result → OpenAI tool messages
OpenAI tool_calls → Anthropic tool_use
OpenAI tool message → Anthropic tool_result
```

For the MVP, reject unsupported tools with a clear error or pass through only when the selected provider supports them.

# Routing and failover

The router should support:

```
model alias routing
provider priority routing
fallback provider routing
health-based routing
manual override routing
```

Example:

```yaml
routing_rules:
  - match: "claude-*"
    primary_provider: "anthropic"
    fallback_providers:
      - "openrouter"
      - "gemini"

  - match: "gemini-*"
    primary_provider: "gemini"
    fallback_providers:
      - "openrouter"

  - match: "local-*"
    primary_provider: "ollama"
    fallback_providers:
      - "openrouter"
```

# Provider health checks

Examples:

```
OpenAI: GET /v1/models
Anthropic: GET /v1/models or lightweight request if needed
Gemini OpenAI-compatible: GET /v1/models
Ollama: GET /api/tags or /v1/models
OpenRouter: GET /api/v1/models
```

Track:

```
healthy / degraded / offline
average latency
success rate
last checked time
last error
available model count
```

# Usage tracking

Track each request:

```
input tokens
output tokens
total tokens
estimated cost
provider
resolved model
requested model
client name
endpoint
request duration
streaming yes/no
status code
error message
retry count
fallback used yes/no
```

Token source values:

```
provider
estimated
manual_count
unknown
```

Use provider-reported usage when available. If missing, estimate with character count divided by 4 and mark as estimated.

# Cost tracking

Pricing config:

```yaml
pricing:
  openai:
    gpt-4.1:
      input_per_1m: 2.00
      output_per_1m: 8.00

  gemini:
    gemini-2.5-pro:
      input_per_1m: 1.25
      output_per_1m: 10.00

  anthropic:
    claude-3-5-sonnet-latest:
      input_per_1m: 3.00
      output_per_1m: 15.00
```

Formula:

```
cost = input_tokens / 1,000,000 * input_price
     + output_tokens / 1,000,000 * output_price
```

If pricing is missing, store cost as null or unavailable.

# Database schema

## api_requests

```sql
CREATE TABLE api_requests (
  id TEXT PRIMARY KEY,
  created_at DATETIME NOT NULL,
  input_format TEXT NOT NULL,
  output_format TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  client_name TEXT,
  requested_model TEXT,
  resolved_model TEXT,
  provider TEXT,
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  total_tokens INTEGER DEFAULT 0,
  token_source TEXT,
  estimated_cost_usd REAL,
  pricing_source TEXT,
  duration_ms INTEGER,
  ttfb_ms INTEGER,
  status_code INTEGER,
  error_message TEXT,
  streamed BOOLEAN DEFAULT 0,
  retry_count INTEGER DEFAULT 0,
  fallback_used BOOLEAN DEFAULT 0,
  request_id TEXT,
  trace_id TEXT
);
```

## proxy_logs

```sql
CREATE TABLE proxy_logs (
  id TEXT PRIMARY KEY,
  created_at DATETIME NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  request_id TEXT,
  trace_id TEXT,
  provider TEXT,
  model TEXT,
  client_name TEXT,
  metadata_json TEXT
);
```

## provider_status

```sql
CREATE TABLE provider_status (
  provider TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  average_latency_ms INTEGER,
  success_rate REAL,
  available_models INTEGER,
  last_checked_at DATETIME,
  last_error TEXT
);
```

## model_aliases

```sql
CREATE TABLE model_aliases (
  alias TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  description TEXT,
  is_default BOOLEAN DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

# Dashboard design system

Keep the UI neutral, clean, and not crowded.

```
off-white background
warm light gray surfaces
charcoal text
muted slate chart colors
small green status accents
rounded cards
thin borders
light shadows
generous spacing
Lucide-style outline icons
```

# Dashboard pages

## Overview

Purpose: quick health and usage overview.

Sections:

```
total tokens today
estimated cost today
top model
average latency
token usage over time chart
top models/providers list
recent requests table
```

## Requests

Purpose: inspect proxy activity.

Sections:

```
search bar
client filter
provider filter
model filter
status filter
time range filter
requests table
selected request detail panel
export button
pagination
```

Columns:

```
Time
Client
Provider
Model
Tokens
Duration
Cost
Status
```

## Logs

Purpose: CLI-style real-time debugging view.

Sections:

```
search logs
source/client filter
level filter
provider filter
time range filter
live tail toggle
pause button
export button
terminal-style log viewer
log summary panel
active streams panel
recent anomalies panel
selected log details panel
```

Terminal-style log viewer should use a dark charcoal card inside the light UI.

Example log lines:

```
4461 May 22 10:24:31.124 INFO  [req:01JWE...] Incoming POST /v1/messages client=Claude Code
4462 May 22 10:24:31.126 INFO  [req:01JWE...] Model alias resolved alias=claude-sonnet → Claude 3.5 Sonnet
4463 May 22 10:24:31.127 INFO  [req:01JWE...] Routing to provider provider=Anthropic region=us-east-1
4464 May 22 10:24:32.813 INFO  [req:01JWE...] Tokens counted input=122134 output=31758 total=153892
4465 May 22 10:24:32.815 INFO  [req:01JWE...] Cost calculated cost=$0.0542 currency=USD
4466 May 22 10:24:36.112 WARN  [req:01JWE...] Upstream timeout retrying attempt=1/2
4467 May 22 10:24:38.552 ERROR [req:01JWE...] Upstream 503 provider=Gemini model=Gemini 2.5 Pro
```

Level colors:

```
INFO = green
WARN = amber
ERROR = red
DEBUG = blue/cyan
```

## Models

Purpose: manage model aliases, defaults, and usage.

Sections:

```
active models
total tokens this week
most used model
average latency
models table
model aliases / routing rules table
add alias button
```

Columns:

```
Model
Provider
Alias
Default
Usage share
Context window
Usage 7D
Actions
```

## Providers

Purpose: monitor provider health and routing.

Sections:

```
active providers
average uptime
failover events
average response time
provider health cards
routing and failover rules table
```

Provider card fields:

```
provider name
health status
models available
average latency
success rate
usage trend
```

## Costs

Purpose: track spending across providers and models.

Sections:

```
spend today
spend this week
projected monthly cost
average cost per request
spending over time chart
cost breakdown by provider/model
recent high-cost requests table
```

## Settings

Purpose: configure providers, defaults, API key status, aliases, logging, and dashboard preferences.

Sections:

```
default routing
API keys
model aliases
logging and tracking
appearance and preferences
```

Important rule:

```
The settings page can show configured/missing and masked key hints, but it should never expose raw provider keys.
```

# Admin API endpoints

```
GET  /admin/stats/overview
GET  /admin/requests
GET  /admin/requests/{id}
GET  /admin/logs
GET  /admin/logs/stream
GET  /admin/models
GET  /admin/providers
GET  /admin/costs
GET  /admin/settings
POST /admin/settings/default-routing
POST /admin/model-aliases
PATCH /admin/model-aliases/{alias}
DELETE /admin/model-aliases/{alias}
POST /admin/providers/{provider}/test
```

Later encrypted key management:

```
POST   /admin/provider-keys/{provider}
DELETE /admin/provider-keys/{provider}
```

# Folder structure

```
local-ai-proxy/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── api/
│   │   │   ├── anthropic.py
│   │   │   ├── openai.py
│   │   │   └── admin.py
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── openai_compatible.py
│   │   │   ├── anthropic_compatible.py
│   │   │   └── ollama.py
│   │   ├── translators/
│   │   │   ├── anthropic_to_openai.py
│   │   │   ├── openai_to_anthropic.py
│   │   │   ├── streaming.py
│   │   │   └── tools.py
│   │   ├── routing/
│   │   │   ├── model_registry.py
│   │   │   ├── alias_resolver.py
│   │   │   └── provider_router.py
│   │   ├── tracking/
│   │   │   ├── usage_service.py
│   │   │   ├── cost_service.py
│   │   │   ├── pricing.py
│   │   │   └── log_service.py
│   │   ├── schemas/
│   │   │   ├── anthropic.py
│   │   │   ├── openai.py
│   │   │   └── admin.py
│   │   └── utils/
│   │       ├── errors.py
│   │       └── time.py
│   ├── requirements.txt
│   └── alembic/
├── dashboard/
│   ├── app/
│   │   ├── overview/
│   │   ├── requests/
│   │   ├── logs/
│   │   ├── models/
│   │   ├── providers/
│   │   ├── costs/
│   │   └── settings/
│   ├── components/
│   │   ├── sidebar.tsx
│   │   ├── metric-card.tsx
│   │   ├── data-table.tsx
│   │   ├── terminal-log-viewer.tsx
│   │   └── provider-icon.tsx
│   └── lib/
│       ├── api.ts
│       └── format.ts
├── data/
│   └── proxy.db
├── config.yaml
├── .env.example
├── docker-compose.yml
└── README.md
```

# MVP build phases

## Phase 1: Core proxy

```
FastAPI app
config loader
local proxy token auth
provider config loading
model alias resolver
OpenAI-compatible provider client
Anthropic /v1/messages endpoint
Anthropic → OpenAI request translator
OpenAI → Anthropic response translator
basic non-streaming response
```

Test:

```bash
curl http://localhost:8000/v1/messages \
  -H "Authorization: Bearer dev-local-proxy-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt",
    "max_tokens": 512,
    "messages": [{"role":"user","content":"hello"}]
  }'
```

## Phase 2: Claude Code compatibility

```
/v1/messages behavior compatible enough for Claude Code
model aliases that map Claude-style names to providers
basic error translation
request logging
```

Manual test:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8000
export ANTHROPIC_AUTH_TOKEN=dev-local-proxy-token
claude
```

## Phase 3: Usage and cost tracking

```
SQLite database
api_requests table
usage extraction from provider responses
fallback token estimation
pricing config
cost calculation
admin stats endpoints
```

## Phase 4: Dashboard shell

```
Next.js dashboard
sidebar
top header
overview page
requests page
settings page shell
```

## Phase 5: Logs page

```
structured log service
proxy_logs table
/admin/logs endpoint
/admin/logs/stream endpoint
CLI-style terminal log viewer
log filters
selected log details panel
```

## Phase 6: Streaming

```
OpenAI-compatible stream reader
Anthropic stream writer
SSE translator
stream usage tracking
stream logs
```

## Phase 7: Tools

```
Anthropic tool_use → OpenAI tool_calls
OpenAI tool_calls → Anthropic tool_use
tool_result handling
compatibility tests with Claude Code
```

## Phase 8: Provider health and failover

```
provider health checks
provider_status table
routing rules
fallback behavior
provider page dashboard
anomaly logging
```

# Testing plan

## Unit tests

```
model alias resolution
Anthropic → OpenAI translation
OpenAI → Anthropic translation
usage normalization
cost calculation
provider config loading
local proxy auth
```

## Integration tests

```
POST /v1/messages → OpenAI
POST /v1/messages → Gemini OpenAI-compatible
POST /v1/messages → OpenRouter
POST /v1/chat/completions → Anthropic
GET /v1/models
admin stats endpoints
logging endpoints
```

## Manual tests

```
Claude Code
OpenAI Python SDK
OpenAI JavaScript SDK
curl
Ollama local server
LM Studio local server
```

# Security principles

```
Never expose provider API keys to the frontend.
Never log raw provider keys.
Never include raw request bodies in logs by default.
Mask secrets in errors and logs.
Use a local proxy token even on localhost.
Store raw keys in .env for v1.
Use encrypted database storage only in v2.
Allow disabling request body logging.
```

# Do not do in v1

```
Do not start with native Gemini integration.
Do not build encrypted key management immediately.
Do not build every provider first.
Do not build the dashboard before the proxy works.
Do not overcomplicate routing before basic alias routing works.
Do not silently accept unsupported tools or content blocks.
```

# First polished MVP target

```
FastAPI local proxy
Claude Code-compatible /v1/messages
OpenAI-compatible backend providers
OpenAI, Gemini, OpenRouter, Ollama, LM Studio
model aliases
.env provider keys
local proxy auth token
SQLite request tracking
estimated cost tracking
Next.js dashboard
Overview page
Requests page
Logs page
Models page
Providers page
Costs page
Settings page
```

Streaming and tool calls can be added immediately after the basic MVP if Claude Code requires deeper compatibility.

# Final product vision

```
Local AI Proxy
├── Anthropic-compatible API
├── OpenAI-compatible API
├── provider switching
├── model aliases
├── request translation
├── streaming translation
├── tool-call translation
├── provider API key management
├── usage tracking
├── cost tracking
├── provider health monitoring
├── failover routing
├── CLI-style live logs
└── clean dashboard
```

The long-term goal is to make it feel like a clean local version of LiteLLM/OpenRouter, but focused on Claude Code compatibility, local-first control, polished usage tracking, and a dashboard that is useful without being crowded.