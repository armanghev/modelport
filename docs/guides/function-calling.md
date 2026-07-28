# Function Calling

ModelPort currently supports basic tool and function-call translation in both directions between Anthropic-style clients and OpenAI-compatible upstream providers.

## Supported Translation

Implemented behavior includes:

- Anthropic `tools` to OpenAI `tools`
- Anthropic `tool_choice` to OpenAI `tool_choice`
- Anthropic tool-use history to OpenAI assistant/tool messages
- OpenAI tool calls back to Anthropic `tool_use` blocks
- streaming tool-call deltas back to Anthropic tool events

## Anthropic-Style Input Example

```json
{
  "model": "models/gemini-2.5-pro",
  "messages": [
    { "role": "user", "content": "Write a file" }
  ],
  "tools": [
    {
      "name": "Write",
      "description": "Write a file",
      "input_schema": {
        "type": "object",
        "properties": {
          "path": { "type": "string" }
        }
      }
    }
  ],
  "tool_choice": { "type": "auto" }
}
```

This is translated upstream into an OpenAI-compatible `tools` array with a `function` entry.

## Current Scope

> **Scope:** The implemented translation path is focused on chat-style tool calling. There is no separate Responses API or structured-output framework yet.
