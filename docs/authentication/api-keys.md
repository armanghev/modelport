# API Keys

ModelPort has three separate authentication layers today:

1. a bearer token for clients calling the proxy (`MODELPORT_TOKEN`)
2. a separate bearer token for the dashboard-facing admin and analytics APIs (`MODELPORT_DASHBOARD_TOKEN`)
3. per-provider credentials for upstream providers

## Proxy Authentication

All proxy endpoints require:

```text
Authorization: Bearer <MODELPORT_TOKEN>
```

By default the backend reads the token name from `config.yaml`:

```yaml
security:
  modelport_token: "MODELPORT_TOKEN"
```

That means the actual token value comes from your environment:

```bash
MODELPORT_TOKEN=dev-modelport-token
```

If the header is missing or invalid, ModelPort returns `401`.

## Dashboard Authentication

All `/admin/*` and `/analytics/*` endpoints require a second, dashboard-only token:

```text
Authorization: Bearer <MODELPORT_DASHBOARD_TOKEN>
```

The token name is configured in `config.yaml`:

```yaml
security:
  modelport_token: "MODELPORT_TOKEN"
  dashboard_token: "MODELPORT_DASHBOARD_TOKEN"
```

The two tokens are not interchangeable: the proxy token is rejected on admin/analytics routes and vice versa. Set both in the root `.env`, and give the dashboard its copy in `dashboard/.env`:

```bash
NEXT_PUBLIC_MODELPORT_DASHBOARD_TOKEN=dev-dashboard-token
```

## Provider Credentials

Seeded providers can read credentials from environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`

The admin API also supports database-backed credentials. Supported sources are:

- `env`
- `database`

Relevant admin endpoints:

- `GET /admin/provider-credentials`
- `POST /admin/provider-credentials`
- `PATCH /admin/provider-credentials/{credential_id}`
- `GET /admin/provider-credentials/{credential_id}/secret`

## Default Credential Resolution

When multiple credentials exist for a provider, ModelPort prefers:

1. enabled and configured credentials marked as default
2. enabled and configured credentials
3. enabled default credentials
4. any enabled credential

## Local Providers

Local OpenAI-compatible providers such as Ollama can be configured without an API key. The health-check and proxy paths explicitly allow anonymous access for local endpoints.
