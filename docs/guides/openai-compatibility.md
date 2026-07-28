# OpenAI Compatibility

ModelPort exposes these OpenAI-style surfaces today:

- `POST /v1/chat/completions`
- `GET /v1/models`
- `POST /v1/responses`
- `POST /v1/embeddings`
- Images, audio, legacy completions, and moderations (OpenAI-compatible upstreams only)

These are intended for OpenAI-compatible clients and SDKs that can target a custom base URL.

## Base URL

Point your OpenAI-compatible client at:

```text
https://127.0.0.1:13243/v1
```

And send:

```text
Authorization: Bearer <MODELPORT_TOKEN>
```

## Supported Chat Fields

The implemented chat schema supports:

- `model`
- `provider`
- `fallback_providers`
- `messages`
- `max_tokens`
- `stream`
- `tools`
- `tool_choice`

## Example

```bash
curl https://127.0.0.1:13243/v1/chat/completions \
  -H "Authorization: Bearer $MODELPORT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openrouter/anthropic/claude-sonnet-4",
    "messages": [
      { "role": "user", "content": "Summarize what ModelPort does." }
    ]
  }'
```

## Notes

- Streaming is supported.
- Tool definitions and tool-call responses are supported in the current chat-completions path.
- `POST /v1/responses` works for both OpenAI-compatible and Anthropic-compatible providers. Against Anthropic upstreams, ModelPort emulates the Responses API locally.
- `POST /v1/embeddings`, images, audio, legacy completions, and moderations require an OpenAI-compatible upstream provider. Selecting an Anthropic-compatible provider returns `501 Not Implemented`.
