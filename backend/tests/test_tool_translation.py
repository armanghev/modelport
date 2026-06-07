from __future__ import annotations

import json

from app.schemas.anthropic import (
    AnthropicMessage,
    AnthropicMessageCreate,
    AnthropicTextBlock,
    AnthropicToolDefinition,
    AnthropicToolResultBlock,
    AnthropicToolUseBlock,
)
from app.schemas.openai import (
    OpenAIChatCompletionCreate,
    OpenAIChatMessage,
    OpenAIFunctionCall,
    OpenAIFunctionDefinition,
    OpenAIToolCall,
    OpenAIToolDefinition,
)
from app.translators.anthropic_to_openai import translate_anthropic_message_to_openai
from app.translators.openai_request_to_anthropic import translate_openai_chat_completion_request_to_anthropic
from app.translators.openai_to_anthropic import (
    AnthropicStreamTranslator,
    translate_anthropic_stream_event_to_openai_chunks,
    translate_openai_chat_completion_to_anthropic,
)


def test_translate_streaming_payload_requests_usage_in_final_chunk() -> None:
    payload = AnthropicMessageCreate(
        model="gemini-2.5-pro",
        max_tokens=1024,
        stream=True,
        messages=[AnthropicMessage(role="user", content="hello")],
    )

    translated = translate_anthropic_message_to_openai(payload, upstream_model="models/gemini-2.5-pro")

    assert translated["stream"] is True
    assert translated["stream_options"] == {"include_usage": True}


def test_translate_tools_and_tool_choice_to_openai_payload() -> None:
    payload = AnthropicMessageCreate(
        model="gemini-2.5-pro",
        max_tokens=1024,
        messages=[AnthropicMessage(role="user", content="Write a file")],
        tools=[
            AnthropicToolDefinition(
                name="Write",
                description="Write a file",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            )
        ],
        tool_choice={"type": "auto"},
    )

    translated = translate_anthropic_message_to_openai(payload, upstream_model="models/gemini-2.5-pro")

    assert translated["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "Write",
                "description": "Write a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            },
        }
    ]
    assert translated["tool_choice"] == "auto"


def test_translate_tool_choice_none_to_openai_payload() -> None:
    payload = AnthropicMessageCreate(
        model="gemini-2.5-pro",
        max_tokens=1024,
        messages=[AnthropicMessage(role="user", content="Write a file")],
        tool_choice={"type": "none"},
    )

    translated = translate_anthropic_message_to_openai(payload, upstream_model="models/gemini-2.5-pro")

    assert translated["tool_choice"] == "none"


def test_translate_tool_use_and_tool_result_history_to_openai_messages() -> None:
    payload = AnthropicMessageCreate(
        model="gemini-2.5-pro",
        messages=[
            AnthropicMessage(role="user", content="List files"),
            AnthropicMessage(
                role="assistant",
                content=[
                    AnthropicToolUseBlock(
                        type="tool_use",
                        id="toolu_123",
                        name="Glob",
                        input={"pattern": "*.py"},
                    )
                ],
            ),
            AnthropicMessage(
                role="user",
                content=[
                    AnthropicToolResultBlock(
                        type="tool_result",
                        tool_use_id="toolu_123",
                        content="found.py",
                    )
                ],
            ),
        ],
    )

    translated = translate_anthropic_message_to_openai(payload, upstream_model="models/gemini-2.5-pro")

    assert translated["messages"] == [
        {"role": "user", "content": "List files"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "toolu_123",
                    "type": "function",
                    "function": {
                        "name": "Glob",
                        "arguments": json.dumps({"pattern": "*.py"}),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "toolu_123", "content": "found.py"},
    ]


def test_translate_openai_tool_calls_to_anthropic_tool_use_response() -> None:
    response = translate_openai_chat_completion_to_anthropic(
        {
            "id": "chatcmpl_tool",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "Write",
                                    "arguments": json.dumps({"path": "claude.html", "contents": "<html>"}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        },
        requested_model="gemini-2.5-pro",
    )

    assert response.stop_reason == "tool_use"
    assert len(response.content) == 1
    assert response.content[0].type == "tool_use"
    assert response.content[0].id == "call_abc"
    assert response.content[0].name == "Write"
    assert response.content[0].input == {"path": "claude.html", "contents": "<html>"}


def test_translate_openai_tool_choice_none_to_anthropic_request() -> None:
    payload = OpenAIChatCompletionCreate(
        model="gpt-4.1",
        messages=[OpenAIChatMessage(role="user", content="hello")],
        tool_choice="none",
    )

    translated = translate_openai_chat_completion_request_to_anthropic(payload)

    assert translated.tool_choice == {"type": "none"}


def test_translate_openai_request_preserves_sampling_and_stop_parameters() -> None:
    payload = OpenAIChatCompletionCreate(
        model="gpt-4.1",
        messages=[OpenAIChatMessage(role="user", content="hello")],
        temperature=0.4,
        top_p=0.8,
        stop=["END", "STOP"],
    )

    translated = translate_openai_chat_completion_request_to_anthropic(payload)

    assert translated.temperature == 0.4
    assert translated.top_p == 0.8
    assert translated.stop_sequences == ["END", "STOP"]


def test_translate_openai_request_concatenates_system_and_developer_messages() -> None:
    payload = OpenAIChatCompletionCreate(
        model="gpt-4.1",
        messages=[
            OpenAIChatMessage(role="system", content="System"),
            OpenAIChatMessage(role="developer", content="Developer"),
            OpenAIChatMessage(role="user", content="hello"),
        ],
    )

    translated = translate_openai_chat_completion_request_to_anthropic(payload)

    assert translated.system == "System\n\nDeveloper"
    assert translated.messages == [AnthropicMessage(role="user", content="hello")]


def test_stream_translator_emits_tool_use_events() -> None:
    translator = AnthropicStreamTranslator(requested_model="gemini-2.5-pro", input_tokens=50)

    events = translator.consume_chunk(
        {
            "id": "chatcmpl_stream_tool",
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_abc",
                                "type": "function",
                                "function": {"name": "Write", "arguments": ""},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        }
    )
    events.extend(
        translator.consume_chunk(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "arguments": json.dumps({"path": "claude.html"}),
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"completion_tokens": 15},
            }
        )
    )
    events.extend(translator.finish_events())

    body = "".join(events)
    assert "event: message_start" in body
    assert '"type": "tool_use"' in body
    assert '"name": "Write"' in body
    assert '"partial_json"' in body
    assert '"stop_reason": "tool_use"' in body
    assert "event: message_stop" in body


def test_stream_translator_emits_parallel_tool_use_events_in_order() -> None:
    translator = AnthropicStreamTranslator(requested_model="gemini-2.5-pro", input_tokens=50)

    events = translator.consume_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_bash",
                                "type": "function",
                                "function": {"name": "Bash", "arguments": ""},
                            },
                            {
                                "index": 1,
                                "id": "call_read",
                                "type": "function",
                                "function": {"name": "Read", "arguments": ""},
                            },
                            {
                                "index": 2,
                                "id": "call_search",
                                "type": "function",
                                "function": {"name": "WebSearch", "arguments": ""},
                            },
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        }
    )
    events.extend(
        translator.consume_chunk(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": json.dumps({"command": "ls"})},
                                },
                                {
                                    "index": 1,
                                    "function": {"arguments": json.dumps({"file_path": "claude.html"})},
                                },
                                {
                                    "index": 2,
                                    "function": {"arguments": json.dumps({"query": "react version"})},
                                },
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        )
    )
    events.extend(translator.finish_events())

    body = "".join(events)
    bash_delta_index = body.find('"partial_json": "{\\"command\\": \\"ls\\"}"')
    read_start_index = body.find('"name": "Read"')
    assert bash_delta_index != -1
    assert read_start_index != -1
    assert bash_delta_index < read_start_index

    assert body.count("event: content_block_start") == 3
    assert body.count("event: content_block_stop") == 3
    assert '"name": "Bash"' in body
    assert '"name": "Read"' in body
    assert '"name": "WebSearch"' in body


def test_translate_parallel_openai_tool_calls_to_anthropic_response() -> None:
    response = translate_openai_chat_completion_to_anthropic(
        {
            "id": "chatcmpl_parallel",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_bash",
                                "type": "function",
                                "function": {
                                    "name": "Bash",
                                    "arguments": json.dumps({"command": "ls"}),
                                },
                            },
                            {
                                "id": "call_read",
                                "type": "function",
                                "function": {
                                    "name": "Read",
                                    "arguments": json.dumps({"file_path": "claude.html"}),
                                },
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30},
        },
        requested_model="gemini-2.5-pro",
    )

    assert response.stop_reason == "tool_use"
    assert len(response.content) == 2
    assert response.content[0].name == "Bash"
    assert response.content[0].input == {"command": "ls"}
    assert response.content[1].name == "Read"
    assert response.content[1].input == {"file_path": "claude.html"}


def test_translate_anthropic_tool_stream_to_openai_chunks() -> None:
    state: dict[str, object] = {}

    assert (
        translate_anthropic_stream_event_to_openai_chunks(
            'data: {"type":"message_start","message":{"id":"msg_123","usage":{"input_tokens":12}}}',
            state=state,
            requested_model="claude-sonnet-4-5",
        )
        == []
    )

    start_chunks = translate_anthropic_stream_event_to_openai_chunks(
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_123","name":"Write","input":{}}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert start_chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "Write"

    delta_chunks = translate_anthropic_stream_event_to_openai_chunks(
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"path\\":\\"out.txt\\"}"}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert delta_chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == '{"path":"out.txt"}'

    final_chunks = translate_anthropic_stream_event_to_openai_chunks(
        'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":7}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert final_chunks[0]["choices"][0]["finish_reason"] == "tool_calls"


def test_stream_translator_handles_tool_arguments_before_metadata() -> None:
    translator = AnthropicStreamTranslator(requested_model="gpt-4.1", input_tokens=10)

    events = translator.consume_chunk(
        {
            "id": "chatcmpl_delayed_meta",
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '{"path":"out.txt"}'},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        }
    )
    events.extend(
        translator.consume_chunk(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_delayed",
                                    "function": {"name": "Write"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"completion_tokens": 4},
            }
        )
    )
    events.extend(translator.finish_events())
    body = "".join(events)

    assert '"type": "tool_use"' in body
    assert '"name": "Write"' in body
    assert '"partial_json": "{\\"path\\":\\"out.txt\\"}"' in body


def test_translate_openai_request_with_tools_to_anthropic_internal_model() -> None:
    payload = OpenAIChatCompletionCreate(
        model="gpt-4o",
        messages=[
            OpenAIChatMessage(role="user", content="hello"),
            OpenAIChatMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    OpenAIToolCall(
                        id="call_1",
                        function=OpenAIFunctionCall(
                            name="Read",
                            arguments=json.dumps({"path": "README.md"}),
                        ),
                    )
                ],
            ),
            OpenAIChatMessage(role="tool", tool_call_id="call_1", content="readme contents"),
        ],
        tools=[
            OpenAIToolDefinition(
                function=OpenAIFunctionDefinition(
                    name="Read",
                    description="Read a file",
                    parameters={"type": "object"},
                )
            )
        ],
        tool_choice="auto",
    )

    translated = translate_openai_chat_completion_request_to_anthropic(payload)

    assert translated.tools is not None
    assert translated.tools[0].name == "Read"
    assert translated.tool_choice == {"type": "auto"}
    assert len(translated.messages) == 3
    assistant_content = translated.messages[1].content
    assert isinstance(assistant_content, list)
    assert assistant_content[0].type == "tool_use"
    user_content = translated.messages[2].content
    assert isinstance(user_content, list)
    assert user_content[0].type == "tool_result"
