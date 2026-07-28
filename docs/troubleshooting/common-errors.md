# Common Errors

## `401 Unauthorized`

Cause:

- missing `Authorization` header
- invalid bearer token

Fix:

- send `Authorization: Bearer <MODELPORT_TOKEN>`
- verify the token value loaded into the backend environment

## `400 Provider selection is required`

Cause:

- you used a bare model id such as `gpt-4.1` without `provider`
- ModelPort could not infer a provider from the model id

Fix:

- add `"provider": "openai"` in the request body
- or add `X-ModelPort-Provider`
- or use an inferable model id such as `openai/gpt-4.1`

## `503 No configured credential available for the selected provider`

Cause:

- the selected provider needs an API key and none is configured

Fix:

- set the provider env var such as `OPENAI_API_KEY`
- or create a database-backed credential with `/admin/provider-credentials`

## Anthropic upstream request problems

Cause:

- the Anthropic provider base URL is wrong
- the Anthropic credential is missing or invalid
- the upstream Anthropic request was rejected

Fix:

- set the provider base URL to the Anthropic API root, such as `https://api.anthropic.com`
- verify `ANTHROPIC_API_KEY` or the stored provider credential is configured
- verify the request includes Anthropic-required fields such as `max_tokens`
