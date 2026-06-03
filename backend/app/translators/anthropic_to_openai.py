from __future__ import annotations

import json
from typing import Any

from app.schemas.anthropic import (
    AnthropicContentBlock,
    AnthropicMessage,
    AnthropicMessageCreate,
    AnthropicTextBlock,
    AnthropicToolDefinition,
    AnthropicToolResultBlock,
    AnthropicToolUseBlock,
)


def flatten_text_blocks(blocks: list[AnthropicTextBlock]) -> str:
    return "\n".join(block.text for block in blocks if block.text)


def normalize_content(content: str | list[AnthropicTextBlock]) -> str:
    if isinstance(content, str):
        return content
    return flatten_text_blocks(content)


def normalize_tool_result_content(content: str | list[AnthropicTextBlock]) -> str:
    if isinstance(content, str):
        return content
    return flatten_text_blocks(content)


def _content_blocks(content: str | list[AnthropicContentBlock]) -> list[AnthropicContentBlock]:
    if isinstance(content, str):
        return [AnthropicTextBlock(type="text", text=content)]
    return list(content)


def _is_text_only_blocks(blocks: list[AnthropicContentBlock]) -> bool:
    return all(isinstance(block, AnthropicTextBlock) for block in blocks)


def translate_tools(tools: list[AnthropicToolDefinition]) -> list[dict[str, Any]]:
    translated: list[dict[str, Any]] = []
    for tool in tools:
        function_payload: dict[str, Any] = {
            "name": tool.name,
            "parameters": tool.input_schema,
        }
        if tool.description:
            function_payload["description"] = tool.description
        translated.append({"type": "function", "function": function_payload})
    return translated


def translate_tool_choice(tool_choice: dict[str, Any] | None) -> str | dict[str, Any] | None:
    if tool_choice is None:
        return None

    choice_type = tool_choice.get("type")
    if choice_type == "auto":
        return "auto"
    if choice_type == "any":
        return "required"
    if choice_type == "tool":
        name = tool_choice.get("name")
        if isinstance(name, str) and name:
            return {"type": "function", "function": {"name": name}}
    return "auto"


def translate_assistant_message(blocks: list[AnthropicContentBlock]) -> dict[str, Any]:
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in blocks:
        if isinstance(block, AnthropicTextBlock):
            text_parts.append(block.text)
        elif isinstance(block, AnthropicToolUseBlock):
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    },
                }
            )

    message: dict[str, Any] = {"role": "assistant"}
    if text_parts:
        message["content"] = "\n".join(text_parts)
    elif tool_calls:
        message["content"] = None
    else:
        message["content"] = ""

    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def translate_user_message(blocks: list[AnthropicContentBlock]) -> list[dict[str, Any]]:
    translated_messages: list[dict[str, Any]] = []
    pending_text: list[str] = []

    for block in blocks:
        if isinstance(block, AnthropicTextBlock):
            pending_text.append(block.text)
            continue

        if isinstance(block, AnthropicToolResultBlock):
            if pending_text:
                translated_messages.append(
                    {
                        "role": "user",
                        "content": "\n".join(pending_text),
                    }
                )
                pending_text = []

            translated_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": block.tool_use_id,
                    "content": normalize_tool_result_content(block.content),
                }
            )

    if pending_text:
        translated_messages.append({"role": "user", "content": "\n".join(pending_text)})

    return translated_messages


def translate_message(message: AnthropicMessage) -> list[dict[str, Any]]:
    if isinstance(message.content, str):
        return [{"role": message.role, "content": message.content}]

    blocks = _content_blocks(message.content)
    if _is_text_only_blocks(blocks):
        text_blocks = [block for block in blocks if isinstance(block, AnthropicTextBlock)]
        return [{"role": message.role, "content": flatten_text_blocks(text_blocks)}]

    if message.role == "assistant":
        return [translate_assistant_message(blocks)]

    return translate_user_message(blocks)


def translate_anthropic_message_to_openai(
    payload: AnthropicMessageCreate,
    upstream_model: str,
) -> dict:
    translated_messages: list[dict[str, Any]] = []

    if payload.system:
        system_text = normalize_content(payload.system)
        if system_text:
            translated_messages.append({"role": "system", "content": system_text})

    for message in payload.messages:
        translated_messages.extend(translate_message(message))

    translated_payload: dict[str, Any] = {
        "model": upstream_model,
        "messages": translated_messages,
        "stream": payload.stream,
    }
    if payload.max_tokens is not None:
        translated_payload["max_tokens"] = payload.max_tokens
    if payload.tools:
        translated_payload["tools"] = translate_tools(payload.tools)
    tool_choice = translate_tool_choice(payload.tool_choice)
    if tool_choice is not None:
        translated_payload["tool_choice"] = tool_choice
    return translated_payload
