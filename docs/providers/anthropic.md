# Anthropic

Anthropic is implemented as an `anthropic_compatible` upstream provider.

## Default Seed

```yaml
anthropic:
  type: "anthropic_compatible"
  display_name: "Anthropic"
  base_url: "https://api.anthropic.com"
```

Use the Anthropic API root as `base_url` (not an OpenAI-style `/v1` suffix). ModelPort talks to Anthropic's native `v1/messages` and `v1/models` surfaces for this provider type.

## Supported Paths

When selected, Anthropic can serve:

- `POST /v1/messages` natively
- `GET /v1/models` natively
- `POST /v1/chat/completions` through ModelPort's translation layer (OpenAI-style clients onto Anthropic Messages)
- `POST /v1/responses` via local Responses API emulation against Anthropic upstreams

## Credential Setup

Set:

```bash
ANTHROPIC_API_KEY=...
```

Or create a database-backed provider credential through the admin API.

## Notes

- OpenAI-compatible-only endpoints such as embeddings, images, audio, legacy completions, and moderations return `501 Not Implemented` against Anthropic.
- Anthropic-only surfaces such as `POST /v1/messages/count_tokens`, batches, and files require an `anthropic_compatible` provider.
