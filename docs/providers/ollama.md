# Ollama

Ollama is supported as a local OpenAI-compatible provider.

## Default Seed

```yaml
ollama:
  type: "openai_compatible"
  display_name: "Ollama"
  base_url: "http://localhost:11434/v1"
```

## Behavior

- no API key is required by default
- health checks allow anonymous access for local providers
- `GET /v1/models` and `POST /v1/chat/completions` can route to Ollama
- `POST /v1/messages` can also target Ollama through the Anthropic-to-OpenAI translation layer

## Example

```json
{
  "provider": "ollama",
  "model": "llama3.1"
}
```
