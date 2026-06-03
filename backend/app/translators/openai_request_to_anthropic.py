from __future__ import annotations

import json

from app.schemas.anthropic import (
    AnthropicContentBlock,
    AnthropicMessage,
    AnthropicMessageCreate,
    AnthropicTextBlock,
    AnthropicToolDefinition,
    AnthropicToolResultBlock,
    AnthropicToolUseBlock,
)
from app.schemas.openai import OpenAIChatCompletionCreate, OpenAITextPart


def flatten_openai_text_parts(parts: list[OpenAITextPart]) -> str:
    return "\n".join(part.text for part in parts if part.text)


def normalize_openai_content(content: str | list[OpenAITextPart] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return flatten_openai_text_parts(content)


def translate_openai_tool_choice(tool_choice: str | dict | None) -> dict | None:
    if tool_choice is None:
        return None
    if tool_choice == "auto":
        return {"type": "auto"}
    if tool_choice in {"required", "any"}:
        return {"type": "any"}
    if isinstance(tool_choice, dict):
        if tool_choice.get("type") == "function":
            function_payload = tool_choice.get("function")
            if isinstance(function_payload, dict):
                name = function_payload.get("name")
                if isinstance(name, str) and name:
                    return {"type": "tool", "name": name}
    return {"type": "auto"}


def translate_openai_tools(tools: list) -> list[AnthropicToolDefinition]:
    translated: list[AnthropicToolDefinition] = []
    for tool in tools:
        if tool.type != "function":
            continue
        translated.append(
            AnthropicToolDefinition(
                name=tool.function.name,
                description=tool.function.description,
                input_schema=tool.function.parameters,
            )
        )
    return translated


def translate_openai_assistant_message(message) -> AnthropicMessage:
    blocks: list[AnthropicContentBlock] = []
    normalized_content = normalize_openai_content(message.content)
    if normalized_content:
        blocks.append(AnthropicTextBlock(type="text", text=normalized_content))

    if message.tool_calls:
        for tool_call in message.tool_calls:
            try:
                parsed_input = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                parsed_input = {}
            if not isinstance(parsed_input, dict):
                parsed_input = {}

            blocks.append(
                AnthropicToolUseBlock(
                    type="tool_use",
                    id=tool_call.id,
                    name=tool_call.function.name,
                    input=parsed_input,
                )
            )

    if len(blocks) == 1 and isinstance(blocks[0], AnthropicTextBlock):
        return AnthropicMessage(role="assistant", content=blocks[0].text)

    return AnthropicMessage(role="assistant", content=blocks)


def translate_openai_chat_completion_request_to_anthropic(
    payload: OpenAIChatCompletionCreate,
) -> AnthropicMessageCreate:
    system_messages: list[str] = []
    messages: list[AnthropicMessage] = []
    pending_tool_results: list[AnthropicToolResultBlock] = []

    def flush_tool_results() -> None:
        if not pending_tool_results:
            return
        messages.append(AnthropicMessage(role="user", content=list(pending_tool_results)))
        pending_tool_results.clear()

    for message in payload.messages:
        if message.role == "system":
            normalized_content = normalize_openai_content(message.content)
            if normalized_content:
                system_messages.append(normalized_content)
            continue

        if message.role == "tool":
            pending_tool_results.append(
                AnthropicToolResultBlock(
                    type="tool_result",
                    tool_use_id=str(message.tool_call_id or ""),
                    content=normalize_openai_content(message.content),
                )
            )
            continue

        flush_tool_results()

        if message.role == "assistant" and message.tool_calls:
            messages.append(translate_openai_assistant_message(message))
            continue

        normalized_content = normalize_openai_content(message.content)
        messages.append(
            AnthropicMessage(
                role=message.role,
                content=normalized_content,
            )
        )

    flush_tool_results()

    system = "\n\n".join(system_messages) if system_messages else None
    tools = translate_openai_tools(payload.tools) if payload.tools else None
    tool_choice = translate_openai_tool_choice(payload.tool_choice)

    return AnthropicMessageCreate(
        provider=payload.provider,
        fallback_providers=payload.fallback_providers,
        model=payload.model,
        max_tokens=payload.max_tokens,
        system=system,
        messages=messages,
        stream=payload.stream,
        tools=tools or None,
        tool_choice=tool_choice,
    )
