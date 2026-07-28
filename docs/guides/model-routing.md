# Model Routing

ModelPort separates the client-facing endpoint format from the upstream provider that ultimately serves the request.

## How Provider Selection Works

Provider selection can come from:

- request body `provider`
- header `X-ModelPort-Provider`
- model-id inference

Fallback providers can be supplied with:

```json
{
  "fallback_providers": ["gemini", "ollama"]
}
```

## Model-ID Inference Rules

If you omit `provider`, ModelPort tries to infer it from the model id.

Implemented rules:

- `openai/gpt-4.1` routes to provider `openai` with upstream model `gpt-4.1`
- `gemini/models/gemini-2.5-flash` routes to provider `gemini`
- `models/gemini-2.5-flash` routes to provider `gemini`
- `openrouter/google/gemini-2.5-flash` routes to provider `openrouter` with upstream model `google/gemini-2.5-flash`
- `openrouter/auto` stays `openrouter/auto`
- vendor-style ids such as `google/gemini-2.5-flash` or `nvidia/nemotron-3.5-content-safety:free` route to `openrouter` when the vendor is not a configured ModelPort provider

Bare model ids such as `gpt-4.1` do **not** infer a provider. Those still require either `provider` or `X-ModelPort-Provider`.

## Examples

OpenRouter vendor model:

```json
{
  "model": "google/gemini-2.5-flash"
}
```

Gemini native OpenAI-compatibility path:

```json
{
  "model": "models/gemini-2.5-flash"
}
```

Explicit provider with a bare model id:

```json
{
  "provider": "openai",
  "model": "gpt-4.1"
}
```

## Fallback Behavior

When a provider returns a retryable proxy error before response data has been emitted, ModelPort can try the next provider in `fallback_providers`. This exists on both `POST /v1/messages` and `POST /v1/chat/completions`.
