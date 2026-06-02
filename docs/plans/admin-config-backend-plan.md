# ModelPort Admin Config Backend Plan

## Summary

Build the first backend slice that powers dashboard editing for admin/configuration data only. `config.yaml` will seed initial data on first startup, then SQLite becomes the runtime source of truth for mutable admin state. Request analytics, logs, and cost summaries remain read-only and derived for now.

The backend will expose FastAPI `GET`, `POST`, and `PATCH` routes for providers, provider credentials, model aliases, routing rules, pricing overrides, and settings. Provider API keys can be stored in SQLite using reversible encryption, revealed only through an explicit secret endpoint, and edited from the dashboard.

## Key Backend Changes

- Add a minimal backend dependency manifest if missing: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `cryptography`, `pyyaml`, `pytest`, and `httpx`.
- Implement SQLite initialization in `backend/app/database.py` with SQLAlchemy 2.x, `create_all()` startup creation, and a small `schema_version` table set to version `1`.
- Implement a config seed loader that imports `config.yaml` only when the admin tables are empty. After seeding, runtime reads come from SQLite.
- Add admin/config tables:
  - `providers`: `id`, `display_name`, `provider_type`, `base_url`, `enabled`, timestamps.
  - `provider_credentials`: `id`, `provider_id`, `display_name`, `source`, `api_key_env`, `encrypted_api_key`, `key_hint`, `is_default`, `enabled`, timestamps.
  - `model_aliases`: `alias`, `provider_id`, `model`, `credential_id`, `description`, `is_default`, `enabled`, timestamps.
  - `routing_rules`: `id`, `match`, `priority`, `primary_provider_id`, `primary_alias`, `fallback_provider_ids_json`, `enabled`, timestamps.
  - `pricing_overrides`: `id`, `provider_id`, `model`, `input_per_1m_usd`, `output_per_1m_usd`, `currency`, `enabled`, timestamps.
  - `app_settings`: `key`, `value_json`, timestamps.
- Seed `providers`, env-sourced `provider_credentials`, and `model_aliases` from the existing `config.yaml`. Each configured provider gets one default env credential when `api_key_env` is present.
- Use provider credential `display_name` to differentiate multiple keys/accounts for the same provider. `api_key_env` is editable only for `source="env"` credentials.
- Use `PROXY_ENCRYPTION_KEY` for reversible encryption of database-sourced keys. App startup may proceed without it if only env credentials exist, but creating, revealing, or using `source="database"` credentials must fail with a clear configuration error when the key is missing.
- Editing an env-sourced credential’s actual secret from the dashboard converts it to `source="database"` and stores the encrypted key. Editing only the env variable name keeps it as `source="env"`.

## Admin API Contracts

- `GET /admin/settings`
  - Returns a composed dashboard settings payload with providers, credentials, aliases, routing rules, pricing, and preferences.
  - Never includes raw API keys.
- `GET /admin/providers`
  - Returns all providers and masked/default credential metadata.
- `POST /admin/providers`
  - Creates a provider with `id`, `display_name`, `provider_type`, `base_url`, and optional `enabled`.
- `PATCH /admin/providers/{provider_id}`
  - Updates editable provider fields: `display_name`, `provider_type`, `base_url`, and `enabled`.
- `GET /admin/provider-credentials`
  - Returns credential rows with `key_hint`, `configured`, `source`, `api_key_env`, `is_default`, and `enabled`.
  - Does not return raw secrets.
- `POST /admin/provider-credentials`
  - Creates an env credential or encrypted database credential.
  - Request supports `provider_id`, `display_name`, `source`, `api_key_env`, `api_key`, `is_default`, and `enabled`.
- `PATCH /admin/provider-credentials/{credential_id}`
  - Updates display name, env var name, default state, enabled state, or replaces the secret.
  - If `api_key` is supplied, encrypt and store it as a database credential.
- `GET /admin/provider-credentials/{credential_id}/secret`
  - Explicit reveal endpoint.
  - For database credentials, decrypt and return the full API key.
  - For env credentials, return the current process env value only if configured; otherwise return a missing-key response.
- `GET /admin/model-aliases`, `POST /admin/model-aliases`, `PATCH /admin/model-aliases/{alias}`
  - Manage alias-to-provider/model routing.
  - Optional `credential_id` allows an alias to target a specific provider account.
- `GET /admin/routing-rules`, `POST /admin/routing-rules`, `PATCH /admin/routing-rules/{rule_id}`
  - Manage match pattern, priority, primary provider/alias, fallback providers, and enabled state.
- `GET /admin/pricing`, `POST /admin/pricing`, `PATCH /admin/pricing/{pricing_id}`
  - Manage editable pricing overrides for dashboard cost estimation.
- `PATCH /admin/settings/default-routing`
  - Updates default provider/model/alias preferences in `app_settings`.
- `PATCH /admin/settings/tracking`
  - Updates tracking toggles such as request logging, cost tracking, and retention settings.
- `PATCH /admin/settings/appearance`
  - Updates dashboard preferences such as theme and refresh interval.

## Implementation Steps

1. Create backend dependency manifest and test configuration.
2. Implement SQLAlchemy engine and session setup with startup table creation.
3. Define ORM models for admin config tables and Pydantic request and response schemas in `backend/app/schemas/admin.py`.
4. Implement `config.yaml` seed import:
   - Read `database.url`, `providers`, `model_aliases`, and `defaults`.
   - Insert only when admin tables are empty.
   - Store provider keys as env-sourced credentials using the configured env var names.
5. Implement credential encryption helpers:
   - Use `cryptography.fernet.Fernet`.
   - Read key from `PROXY_ENCRYPTION_KEY`.
   - Store encrypted values as text.
   - Generate `key_hint` from the first and last visible characters without logging the full key.
6. Implement admin service functions:
   - Provider CRUD.
   - Credential create, update, and reveal.
   - Alias CRUD.
   - Routing rule CRUD.
   - Pricing CRUD.
   - Settings read and update.
7. Implement FastAPI app wiring:
   - `backend/app/main.py` creates the app.
   - Startup initializes DB and seeds config.
   - `backend/app/api/admin.py` registers `/admin/*` routes.
8. Add validation and invariants:
   - Provider IDs and aliases are stable lowercase slugs.
   - Only one default credential per provider.
   - Database credentials require encrypted key material.
   - Env credentials require `api_key_env`.
   - Broad admin responses never include raw secrets.

## Test Plan

- Unit test config seeding from `config.yaml`:
  - Providers are created.
  - Env credentials are created from `api_key_env`.
  - Model aliases point to seeded providers.
  - Re-running seed does not duplicate rows.
- Unit test credential encryption:
  - Stored DB value is ciphertext, not the raw key.
  - Reveal returns the original key when `PROXY_ENCRYPTION_KEY` is present.
  - Create and reveal fail clearly when encrypted credentials exist but the encryption key is missing.
- API test provider routes:
  - `GET /admin/providers` returns seeded providers.
  - `POST /admin/providers` creates a provider.
  - `PATCH /admin/providers/{id}` updates editable fields.
- API test credential routes:
  - `GET /admin/provider-credentials` returns masked credentials only.
  - `POST /admin/provider-credentials` creates env and database credentials.
  - `PATCH /admin/provider-credentials/{id}` can rotate a key.
  - `GET /admin/provider-credentials/{id}/secret` reveals only through the explicit route.
- API test alias, routing, pricing, and settings routes:
  - Create and patch each entity.
  - Invalid provider references return `400` or `404`.
  - Composed `GET /admin/settings` includes all admin sections and no raw secrets.

## Assumptions

- SQLite is the runtime source of truth after first seed.
- `config.yaml` is not edited by the dashboard.
- Analytics tables and proxy request handling are outside this backend slice.
- Soft disabling is preferred over deletion for dashboard actions in this phase.
- Full API key reveal is allowed only through a deliberate endpoint, never through list or settings responses.
- Env-sourced credentials can reveal the current process env value, but editing the actual secret stores it as an encrypted database credential.
