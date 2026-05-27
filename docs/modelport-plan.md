# Local AI Proxy Plan

## Project Name

**Local AI Proxy**

A local server that can translate between OpenAI-compatible and Anthropic-compatible API formats, allowing tools like Claude Code, OpenAI SDK apps, custom agents, and local model clients to use different providers through one switchable proxy.

---

## 1. Main Goal

Build a local server that supports both major AI API formats:

- OpenAI-compatible API
- Anthropic-compatible API

The proxy should let a client send a request in one format and route it to a provider that may use the same or a different format.

Example:

```txt
Claude Code
  -> Anthropic-style request to local proxy
  -> Proxy converts request to OpenAI-style
  -> Gemini/OpenAI/OpenRouter receives it
  -> Proxy converts response back to Anthropic-style
  -> Claude Code receives a normal response
```

The main target is making it easy to use models like Gemini, GPT, OpenRouter models, Ollama, LM Studio, or Anthropic through one local endpoint.

---

## 2. Main Use Cases

### Use Case 1: Use Gemini or GPT in Claude Code

Claude Code expects Anthropic-compatible requests.

The proxy should expose:

```txt
POST /v1/messages
```

Claude Code sends an Anthropic-style request, then the proxy translates it to an OpenAI-compatible backend such as Gemini, OpenAI, or OpenRouter.

### Use Case 2: Use Claude through OpenAI-style apps

Some tools only support OpenAI-compatible APIs.

The proxy should expose:

```txt
POST /v1/chat/completions
```

Then it can translate OpenAI-style requests to Anthropic-compatible requests.

### Use Case 3: Switch providers easily

The user should be able to switch providers through:

1. The request body model name
2. An environment variable
3. The config file default

Example:

```bash
export PROXY_MODEL=gemini
```

or:

```json
{
  "model": "gpt",
  "messages": []
}
```

---

## 3. Recommended Tech Stack

### Backend

Use:

```txt
Python + FastAPI + httpx + pydantic
```

FastAPI is better than Django or Next.js for this project because:

- It is lightweight.
- Streaming responses are easier to handle.
- Python has strong SDK support for AI providers.
- It is simple to run locally.
- The code structure stays clean for request/response translation.

### Main Packages

```txt
fastapi
uvicorn
httpx
pydantic
python-dotenv
pyyaml
sse-starlette
```

Optional later:

```txt
rich
pytest
pytest-asyncio
ruff
mypy
```

---

## 4. High-Level Architecture

```txt
Client
  -> Local Proxy Server
  -> Endpoint Handler
  -> Request Format Detector
  -> Model Alias Resolver
  -> Provider Router
  -> Request Translator
  -> Provider Client
  -> Response Translator
  -> Client
```

Example flow:

```txt
Claude Code
  -> POST /v1/messages
  -> Anthropic request detected
  -> model alias resolved: claude-sonnet -> gemini-2.5-pro
  -> provider selected: Gemini OpenAI-compatible endpoint
  -> Anthropic request translated to OpenAI request
  -> Gemini responds
  -> OpenAI response translated to Anthropic response
  -> Claude Code receives response
```

---

## 5. Compatibility Types

The proxy should support these backend provider types first:

```txt
openai_compatible
anthropic_compatible
```

Later it can support:

```txt
gemini_native
ollama_native
custom
```

The first version should avoid native Gemini because Gemini already supports OpenAI compatibility. That makes the first version much easier.

---

## 6. Supported Providers

### OpenAI-Compatible Providers

These providers should be supported through the same adapter:

- OpenAI
- Gemini OpenAI-compatible endpoint
- OpenRouter
- Groq
- Together AI
- Fireworks AI
- DeepInfra
- Mistral
- Perplexity
- Ollama OpenAI-compatible endpoint
- LM Studio OpenAI-compatible endpoint
- vLLM OpenAI-compatible server

### Anthropic-Compatible Providers

These should be supported through an Anthropic adapter:

- Anthropic Claude API
- Ollama Anthropic-compatible endpoint
- Poe Anthropic-compatible API
- MiniMax Anthropic-compatible API
- Any local or cloud gateway exposing `/v1/messages`

---

## 7. Endpoints to Implement

### Phase 1 Endpoints

These are required for the first useful version:

```txt
POST /v1/messages
GET  /v1/models
GET  /health
```

### Phase 2 Endpoints

Add OpenAI compatibility:

```txt
POST /v1/chat/completions
GET  /v1/models
```

### Phase 3 Endpoints

Optional later:

```txt
POST /v1/responses
POST /v1/embeddings
```

---

## 8. Config File Design

Use a `config.yaml` file.

Example:

```yaml
server:
  host: "127.0.0.1"
  port: 8000

security:
  require_auth: false
  local_auth_token_env: "LOCAL_PROXY_AUTH_TOKEN"

defaults:
  input_format: "anthropic"
  provider: "openrouter"
  model: "openai/gpt-4.1"
  stream: true

providers:
  openai:
    type: "openai_compatible"
    base_url: "https://api.openai.com/v1"
    api_key_env: "OPENAI_API_KEY"

  gemini:
    type: "openai_compatible"
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai"
    api_key_env: "GEMINI_API_KEY"

  openrouter:
    type: "openai_compatible"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"
    extra_headers:
      HTTP-Referer: "http://localhost:8000"
      X-Title: "Local AI Proxy"

  anthropic:
    type: "anthropic_compatible"
    base_url: "https://api.anthropic.com"
    api_key_env: "ANTHROPIC_API_KEY"

model_aliases:
  claude-sonnet:
    provider: "openrouter"
    model: "anthropic/claude-sonnet-4"

  gpt:
    provider: "openai"
    model: "gpt-4.1"

  gemini:
    provider: "gemini"
    model: "gemini-2.5-pro"

  local:
    provider: "ollama"
    model: "llama3.1"
```

---

## 9. Environment Variables

Example `.env` file:

```bash
OPENAI_API_KEY="your-openai-key"
GEMINI_API_KEY="your-gemini-key"
OPENROUTER_API_KEY="your-openrouter-key"
ANTHROPIC_API_KEY="your-anthropic-key"
LOCAL_PROXY_AUTH_TOKEN="local-token"
PROXY_MODEL="gemini"
```

Model switching priority:

```txt
1. Request body model
2. PROXY_MODEL environment variable
3. config.yaml defaults.model
```

Provider switching priority:

```txt
1. Model alias provider
2. Request provider override, if allowed
3. PROXY_PROVIDER environment variable
4. config.yaml defaults.provider
```

---

## 10. Folder Structure

```txt
local-ai-proxy/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── settings.py
│   ├── router.py
│   ├── auth.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── openai_compatible.py
│   │   └── anthropic_compatible.py
│   ├── translators/
│   │   ├── __init__.py
│   │   ├── anthropic_to_openai.py
│   │   ├── openai_to_anthropic.py
│   │   ├── anthropic_stream_to_openai.py
│   │   └── openai_stream_to_anthropic.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── anthropic.py
│   │   └── openai.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── errors.py
│   │   ├── logging.py
│   │   └── ids.py
│   └── tests/
│       ├── test_anthropic_to_openai.py
│       ├── test_openai_to_anthropic.py
│       └── test_model_aliases.py
├── config.yaml
├── .env.example
├── requirements.txt
├── README.md
└── PLAN.md
```

---

## 11. Request Translation

### Anthropic Request Example

```json
{
  "model": "gemini",
  "max_tokens": 4096,
  "system": "You are a helpful coding assistant.",
  "messages": [
    {
      "role": "user",
      "content": "Write a Python function that adds two numbers."
    }
  ]
}
```

### Translated OpenAI Request

```json
{
  "model": "gemini-2.5-pro",
  "max_tokens": 4096,
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful coding assistant."
    },
    {
      "role": "user",
      "content": "Write a Python function that adds two numbers."
    }
  ]
}
```

### Anthropic to OpenAI Field Mapping

| Anthropic Field | OpenAI Field | Notes |
|---|---|---|
| `model` | `model` | Resolve through aliases first |
| `system` | `messages[0].role = system` | OpenAI puts system in messages |
| `messages` | `messages` | Convert content blocks to strings or arrays |
| `max_tokens` | `max_tokens` | Usually direct mapping |
| `temperature` | `temperature` | Direct mapping |
| `top_p` | `top_p` | Direct mapping |
| `stop_sequences` | `stop` | Rename field |
| `stream` | `stream` | Direct mapping, but stream events must be translated |
| `tools` | `tools` | Needs schema conversion |
| `tool_choice` | `tool_choice` | Needs conversion |

---

## 12. Response Translation

### OpenAI Response Example

```json
{
  "id": "chatcmpl_123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gemini-2.5-pro",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here is the function..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### Translated Anthropic Response

```json
{
  "id": "msg_123",
  "type": "message",
  "role": "assistant",
  "model": "gemini",
  "content": [
    {
      "type": "text",
      "text": "Here is the function..."
    }
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 10,
    "output_tokens": 20
  }
}
```

### OpenAI to Anthropic Finish Reason Mapping

| OpenAI Finish Reason | Anthropic Stop Reason |
|---|---|
| `stop` | `end_turn` |
| `length` | `max_tokens` |
| `tool_calls` | `tool_use` |
| `content_filter` | `stop_sequence` or error |
| `null` | `null` |

---

## 13. Streaming Plan

Streaming is required for a smooth Claude Code experience.

### Anthropic Streaming Events

Anthropic streams events like:

```txt
message_start
content_block_start
content_block_delta
content_block_stop
message_delta
message_stop
```

### OpenAI Streaming Events

OpenAI-compatible APIs stream chunks like:

```txt
chat.completion.chunk
```

### Needed Translation

The proxy should convert OpenAI streaming chunks into Anthropic SSE events when the client hits `/v1/messages`.

Example flow:

```txt
OpenAI chunk with delta.content
  -> Anthropic content_block_delta event
```

Basic stream output order:

```txt
message_start
content_block_start
content_block_delta
content_block_delta
content_block_delta
content_block_stop
message_delta
message_stop
```

Start by supporting text streaming only. Add tool streaming later.

---

## 14. Tool Call Plan

Tool calls are one of the hardest parts, especially for Claude Code.

### Anthropic Tool Format

Anthropic uses content blocks like:

```json
{
  "type": "tool_use",
  "id": "toolu_123",
  "name": "read_file",
  "input": {
    "path": "main.py"
  }
}
```

### OpenAI Tool Format

OpenAI uses tool calls like:

```json
{
  "tool_calls": [
    {
      "id": "call_123",
      "type": "function",
      "function": {
        "name": "read_file",
        "arguments": "{\"path\": \"main.py\"}"
      }
    }
  ]
}
```

### Translation Rules

Anthropic to OpenAI:

```txt
Anthropic tool_use block
  -> OpenAI assistant message with tool_calls
```

OpenAI to Anthropic:

```txt
OpenAI tool_calls
  -> Anthropic content block with type tool_use
```

Tool results:

```txt
Anthropic tool_result
  -> OpenAI tool role message
```

```txt
OpenAI tool role message
  -> Anthropic user message containing tool_result block
```

### First Tool Support Target

Support basic tool calls with:

- Tool name
- Tool input schema
- Tool call id
- Tool result content

Do not start with advanced streamed tool call deltas.

---

## 15. Auth Plan

Since this is a local server, auth can be optional.

### Local Development Mode

```yaml
security:
  require_auth: false
```

### Protected Local Mode

```yaml
security:
  require_auth: true
  local_auth_token_env: "LOCAL_PROXY_AUTH_TOKEN"
```

Accept headers like:

```txt
Authorization: Bearer local-token
x-api-key: local-token
anthropic-api-key: local-token
```

This makes it work with different clients.

---

## 16. Claude Code Setup

Claude Code can point to the local proxy through environment variables.

Example:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_AUTH_TOKEN="local-token"
export PROXY_MODEL="gemini"
claude
```

The proxy receives Claude Code requests at:

```txt
POST /v1/messages
```

Then routes them to the selected backend provider.

---

## 17. OpenAI SDK Setup

OpenAI-compatible clients should point to:

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
export OPENAI_API_KEY="local-token"
```

Then use:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="local-token",
)

response = client.chat.completions.create(
    model="claude-sonnet",
    messages=[
        {"role": "user", "content": "Hello"}
    ],
)
```

The proxy can route `claude-sonnet` to Anthropic, OpenRouter, or another backend.

---

## 18. Error Handling

The proxy should normalize provider errors.

Examples:

```txt
Missing API key
Invalid model alias
Provider timeout
Provider returned invalid response
Unsupported tool call format
Streaming translation failed
```

For Anthropic endpoints, return Anthropic-style errors.

For OpenAI endpoints, return OpenAI-style errors.

### Error Response Strategy

If the request came through:

```txt
/v1/messages
```

Return an Anthropic-style error.

If the request came through:

```txt
/v1/chat/completions
```

Return an OpenAI-style error.

---

## 19. Logging Plan

Log enough to debug issues, but never log API keys.

Good things to log:

```txt
request_id
input_format
output_provider
model_alias
resolved_model
stream_enabled
status_code
latency_ms
error_type
```

Do not log by default:

```txt
full prompts
full completions
API keys
auth headers
file contents
```

Add a debug option later:

```yaml
logging:
  log_prompts: false
  log_responses: false
```

---

## 20. Testing Plan

### Unit Tests

Test translators:

```txt
Anthropic simple text -> OpenAI simple text
OpenAI simple text -> Anthropic simple text
Anthropic system prompt -> OpenAI system message
OpenAI finish_reason -> Anthropic stop_reason
Tool use conversion
Tool result conversion
Model alias resolution
```

### Integration Tests

Test real endpoints with mock provider responses:

```txt
POST /v1/messages
POST /v1/chat/completions
stream=false
stream=true
invalid model
missing API key
```

### Manual Tests

Use curl:

```bash
curl http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-token" \
  -d '{
    "model": "gemini",
    "max_tokens": 500,
    "messages": [
      {"role": "user", "content": "Say hello"}
    ]
  }'
```

---

## 21. Build Milestones

### Milestone 1: Basic Server

Features:

- FastAPI app
- `/health`
- Config loader
- `.env` loader
- Basic logging

Done when:

```txt
GET /health returns ok
config.yaml loads successfully
```

---

### Milestone 2: Provider Config and Model Aliases

Features:

- Load providers from config
- Load model aliases
- Resolve model names
- Choose provider from alias/default/env

Done when:

```txt
model "gemini" resolves to provider "gemini" and model "gemini-2.5-pro"
```

---

### Milestone 3: Anthropic to OpenAI Non-Streaming

Features:

- Implement `/v1/messages`
- Translate Anthropic request to OpenAI request
- Send to OpenAI-compatible provider
- Translate OpenAI response to Anthropic response

Done when:

```txt
Claude-style curl request returns Anthropic-style response from Gemini/OpenAI/OpenRouter
```

---

### Milestone 4: Claude Code Basic Support

Features:

- Support Claude Code headers
- Support model remapping
- Handle common Claude Code request fields
- Return responses Claude Code accepts

Done when:

```txt
Claude Code can make a basic request through the local proxy
```

---

### Milestone 5: Streaming Text Responses

Features:

- Support `stream: true`
- Translate OpenAI chunks to Anthropic SSE events
- Support text-only streaming

Done when:

```txt
Claude Code receives streamed text from Gemini/OpenAI/OpenRouter
```

---

### Milestone 6: Basic Tool Calls

Features:

- Convert Anthropic tools to OpenAI tools
- Convert OpenAI tool calls to Anthropic tool_use blocks
- Convert tool results both directions

Done when:

```txt
Claude Code can perform a basic tool call loop without breaking
```

---

### Milestone 7: OpenAI Endpoint Support

Features:

- Add `/v1/chat/completions`
- Translate OpenAI requests to Anthropic requests when needed
- Support OpenAI-style clients

Done when:

```txt
OpenAI SDK can use the proxy and route requests to Anthropic/OpenRouter/Gemini
```

---

### Milestone 8: Polish and DX

Features:

- Better README
- Better errors
- Better logs
- Tests
- Example configs
- Dockerfile
- CLI helper

Done when:

```txt
A new user can clone the repo, add keys, run the server, and connect Claude Code
```

---

## 22. First Version Scope

The first version should include:

```txt
Included:
- FastAPI server
- config.yaml
- .env support
- /health
- /v1/messages
- Anthropic to OpenAI-compatible translation
- OpenAI-compatible provider client
- model aliases
- OpenAI/Gemini/OpenRouter support
- non-streaming responses

Not included yet:
- streaming
- tool calls
- /v1/chat/completions
- native Gemini
- embeddings
- image input
- audio input
```

This first version is enough to prove the core idea.

---

## 23. Risks and Problems to Expect

### Claude Code May Require More Anthropic Features

Claude Code may use fields that basic examples do not cover. The proxy should log unknown fields so support can be added later.

### Streaming Is Format-Sensitive

Even if normal responses work, streaming may break if the event format is slightly wrong. Build streaming carefully after non-streaming works.

### Tool Calls Are Not Identical

Anthropic and OpenAI tool formats are similar but not the same. Tool use and tool result messages need careful translation.

### Provider Differences

Some OpenAI-compatible providers do not support every OpenAI feature. The proxy should handle missing features gracefully.

Examples:

```txt
Provider does not support tools
Provider does not support system messages
Provider does not support JSON schema
Provider has different model token limits
```

---

## 24. Future Features

Possible future improvements:

```txt
- Web dashboard for switching models
- CLI command to switch model aliases
- Per-client routing rules
- Request history viewer
- Cost tracking
- Token usage tracking
- Automatic fallback provider
- Load balancing across providers
- Local-only mode with Ollama/LM Studio
- Native Gemini adapter
- Anthropic-compatible server for OpenAI-only tools
- OpenAI Responses API support
- MCP-aware routing
```

---

## 25. Example CLI Ideas

Later, add a small CLI:

```bash
proxy models
proxy use gemini
proxy use gpt
proxy use claude-sonnet
proxy start
proxy test
```

Example output:

```txt
Current model: gemini
Provider: gemini
Resolved model: gemini-2.5-pro
Base URL: https://generativelanguage.googleapis.com/v1beta/openai
```

---

## 26. Minimum Viable Product Checklist

```txt
[ ] Create FastAPI project
[ ] Add config.yaml
[ ] Add .env support
[ ] Add provider config loader
[ ] Add model alias resolver
[ ] Add OpenAI-compatible provider client
[ ] Add Anthropic request schema
[ ] Add OpenAI request schema
[ ] Add Anthropic -> OpenAI translator
[ ] Add OpenAI -> Anthropic translator
[ ] Add POST /v1/messages
[ ] Add GET /v1/models
[ ] Add /health
[ ] Test with curl
[ ] Test with Gemini OpenAI-compatible endpoint
[ ] Test with OpenAI
[ ] Test with OpenRouter
[ ] Add Claude Code setup instructions
```

---

## 27. Recommended Build Order

Build in this exact order:

```txt
1. FastAPI app with /health
2. Config loader
3. Model alias resolver
4. OpenAI-compatible provider client
5. Anthropic -> OpenAI request translator
6. OpenAI -> Anthropic response translator
7. POST /v1/messages non-streaming
8. Test with curl
9. Test with Claude Code
10. Add streaming
11. Add tool calls
12. Add /v1/chat/completions
13. Add OpenAI -> Anthropic routing
14. Add tests and polish
```

---

## 28. Final Target Architecture

```txt
Claude Code
OpenAI SDK apps
Anthropic SDK apps
Custom agents
Cursor-like tools
Local scripts
        |
        v
Local AI Proxy
        |
        +--> OpenAI
        +--> Gemini OpenAI-compatible API
        +--> OpenRouter
        +--> Anthropic
        +--> Ollama
        +--> LM Studio
        +--> vLLM
```

The final product should feel like a local universal AI adapter.

