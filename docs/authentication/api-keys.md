# API Keys

ModelPort has three separate authentication layers today:

1. a bearer token for clients calling the proxy (`MODELPORT_TOKEN`)
2. a dashboard login/session and compatible bearer token (`MODELPORT_DASHBOARD_TOKEN`)
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

Dashboard authentication is enabled by default:

```bash
MODELPORT_DASHBOARD_AUTH_ENABLED=true
MODELPORT_DASHBOARD_TOKEN=dev-dashboard-token
```

The browser submits the token to `/dashboard/auth/login` and receives a
session-only, HttpOnly, SameSite Strict cookie. HTTPS responses mark it Secure.
Rotating `MODELPORT_DASHBOARD_TOKEN` invalidates existing sessions.

External tools can continue to call `/admin/*` and `/analytics/*` with:

```text
Authorization: Bearer <MODELPORT_DASHBOARD_TOKEN>
```

The environment-variable names are configured in `config.yaml`:

```yaml
security:
  modelport_token: "MODELPORT_TOKEN"
  dashboard_token: "MODELPORT_DASHBOARD_TOKEN"
  dashboard_auth_enabled_env: "MODELPORT_DASHBOARD_AUTH_ENABLED"
```

The proxy and dashboard tokens are not interchangeable. Setting
`MODELPORT_DASHBOARD_AUTH_ENABLED=false` deliberately makes all `/admin/*` and
`/analytics/*` routes unauthenticated; only use that behind another trusted
access-control layer. Proxy authentication remains enforced either way.

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
