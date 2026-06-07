from __future__ import annotations

import json

from fastapi import HTTPException, status

from app.schemas.anthropic import (
    AnthropicMessageResponse,
    AnthropicResponseContentBlock,
    AnthropicResponseToolUseBlock,
    AnthropicUsage,
)

STOP_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
}


def format_sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def extract_text_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif item.get("type") == "output_text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
        return "\n".join(text_parts)
    return str(content)


def translate_tool_calls(message: dict) -> list[AnthropicResponseContentBlock | AnthropicResponseToolUseBlock]:
    content_blocks: list[AnthropicResponseContentBlock | AnthropicResponseToolUseBlock] = []

    content_text = extract_text_content(message.get("content"))
    if content_text:
        content_blocks.append(AnthropicResponseContentBlock(text=content_text))

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function_payload = tool_call.get("function")
            if not isinstance(function_payload, dict):
                continue

            arguments = function_payload.get("arguments", "{}")
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments)

            try:
                parsed_input = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                parsed_input = {}

            if not isinstance(parsed_input, dict):
                parsed_input = {}

            content_blocks.append(
                AnthropicResponseToolUseBlock(
                    id=str(tool_call.get("id") or ""),
                    name=str(function_payload.get("name") or ""),
                    input=parsed_input,
                )
            )

    if not content_blocks:
        content_blocks.append(AnthropicResponseContentBlock(text=""))

    return content_blocks


def translate_openai_chat_completion_to_anthropic(
    payload: dict,
    requested_model: str,
) -> AnthropicMessageResponse:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider returned no completion choices.",
        )

    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    if not isinstance(message, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider returned an invalid completion payload.",
        )

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None

    return AnthropicMessageResponse(
        id=str(payload.get("id") or "msg_generated"),
        model=requested_model,
        content=translate_tool_calls(message),
        stop_reason=STOP_REASON_MAP.get(str(finish_reason), "end_turn") if finish_reason else "end_turn",
        stop_sequence=None,
        usage=AnthropicUsage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
        ),
    )


def translate_anthropic_message_to_openai_response(
    payload: dict,
    requested_model: str,
) -> dict:
    content = payload.get("content")
    if not isinstance(content, list):
        content = []

    output_content: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        block_type = item.get("type")
        if block_type == "text" and isinstance(item.get("text"), str):
            output_content.append({"type": "output_text", "text": item["text"]})

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)

    return {
        "id": f"resp_{payload.get('id') or 'generated'}",
        "object": "response",
        "status": "completed",
        "model": requested_model,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": output_content,
            }
        ],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


class AnthropicStreamTranslator:
    def __init__(self, *, requested_model: str, input_tokens: int) -> None:
        self.requested_model = requested_model
        self.input_tokens = input_tokens
        self.response_id = "msg_generated"
        self.stop_reason = "end_turn"
        self.output_tokens = 0
        self.message_started = False
        self.next_content_index = 0
        self.open_block_index: int | None = None
        self.open_block_type: str | None = None
        self.openai_tool_index_to_content_index: dict[int, int] = {}
        self.pending_tool_metadata: dict[int, dict[str, str]] = {}
        self.current_openai_tool_index: int | None = None
        self.text_parts: list[str] = []
        self.completion_reason: str | None = None

    def _ensure_message_start(self) -> list[str]:
        if self.message_started:
            return []

        self.message_started = True
        return [
            format_sse_event(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": self.response_id,
                        "type": "message",
                        "role": "assistant",
                        "model": self.requested_model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": self.input_tokens,
                            "output_tokens": 0,
                        },
                    },
                },
            )
        ]

    def _close_open_block(self) -> list[str]:
        if self.open_block_index is None:
            return []

        events = [
            format_sse_event(
                "content_block_stop",
                {"type": "content_block_stop", "index": self.open_block_index},
            )
        ]
        self.open_block_index = None
        self.open_block_type = None
        self.current_openai_tool_index = None
        return events

    def _open_text_block(self) -> list[str]:
        if self.open_block_type == "text" and self.open_block_index is not None:
            return []

        events = self._close_open_block()
        index = self.next_content_index
        self.next_content_index += 1
        self.open_block_index = index
        self.open_block_type = "text"
        events.append(
            format_sse_event(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        )
        return events

    def _open_tool_use_block(self, openai_tool_index: int, tool_id: str, name: str) -> list[str]:
        if openai_tool_index in self.openai_tool_index_to_content_index:
            return []

        if not name:
            return []

        events = self._close_open_block()
        index = self.next_content_index
        self.next_content_index += 1
        self.openai_tool_index_to_content_index[openai_tool_index] = index
        self.open_block_index = index
        self.open_block_type = "tool_use"
        self.current_openai_tool_index = openai_tool_index
        resolved_id = tool_id or f"call_{openai_tool_index}"
        events.append(
            format_sse_event(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {
                        "type": "tool_use",
                        "id": resolved_id,
                        "name": name,
                        "input": {},
                    },
                },
            )
        )
        return events

    def _merge_tool_metadata(self, openai_tool_index: int, tool_id: str, tool_name: str) -> dict[str, str]:
        metadata = self.pending_tool_metadata.setdefault(
            openai_tool_index,
            {"id": "", "name": ""},
        )
        if tool_id:
            metadata["id"] = tool_id
        if tool_name:
            metadata["name"] = tool_name
        return metadata

    def _consume_tool_call_deltas(self, delta: dict) -> list[str]:
        events: list[str] = []
        tool_calls = delta.get("tool_calls")
        if not isinstance(tool_calls, list):
            return events

        sorted_tool_calls = sorted(
            [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)],
            key=lambda tool_call: int(tool_call.get("index", 0)),
        )

        for position, tool_call in enumerate(sorted_tool_calls):
            openai_tool_index = int(tool_call.get("index", 0))
            function_payload = tool_call.get("function")
            if not isinstance(function_payload, dict):
                function_payload = {}

            tool_id = str(tool_call.get("id") or "")
            tool_name = str(function_payload.get("name") or "")
            metadata = self._merge_tool_metadata(openai_tool_index, tool_id, tool_name)

            arguments_fragment = function_payload.get("arguments")
            has_arguments = isinstance(arguments_fragment, str) and bool(arguments_fragment)

            if (
                has_arguments
                and self.current_openai_tool_index is not None
                and openai_tool_index != self.current_openai_tool_index
            ):
                events.extend(self._close_open_block())
                self.current_openai_tool_index = None

            if openai_tool_index not in self.openai_tool_index_to_content_index:
                if self.open_block_index is not None and not has_arguments:
                    continue

                events.extend(
                    self._open_tool_use_block(
                        openai_tool_index,
                        metadata["id"],
                        metadata["name"],
                    )
                )

            if has_arguments:
                content_index = self.openai_tool_index_to_content_index.get(openai_tool_index)
                if content_index is not None:
                    events.append(
                        format_sse_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": content_index,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": arguments_fragment,
                                },
                            },
                        )
                    )

            next_tool_call = (
                sorted_tool_calls[position + 1] if position + 1 < len(sorted_tool_calls) else None
            )
            if (
                next_tool_call is not None
                and int(next_tool_call.get("index", 0)) != openai_tool_index
                and has_arguments
                and self.open_block_index is not None
            ):
                events.extend(self._close_open_block())
                self.current_openai_tool_index = None

        return events

    def consume_chunk(self, chunk: dict) -> list[str]:
        events: list[str] = []
        if chunk.get("id"):
            self.response_id = str(chunk["id"])

        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return events

        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        delta = first_choice.get("delta") if isinstance(first_choice, dict) else {}
        finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
        usage = chunk.get("usage") if isinstance(chunk.get("usage"), dict) else {}

        events.extend(self._ensure_message_start())

        if isinstance(delta, dict):
            events.extend(self._consume_tool_call_deltas(delta))

            content_text = ""
            raw_content = delta.get("content")
            if isinstance(raw_content, str):
                content_text = raw_content
            elif isinstance(raw_content, list):
                content_text = extract_text_content(raw_content)

            if content_text:
                events.extend(self._open_text_block())
                self.text_parts.append(content_text)
                events.append(
                    format_sse_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": self.open_block_index,
                            "delta": {"type": "text_delta", "text": content_text},
                        },
                    )
                )

        if finish_reason:
            self.completion_reason = str(finish_reason)
            self.stop_reason = STOP_REASON_MAP.get(str(finish_reason), "end_turn")
        if usage:
            self.output_tokens = int(usage.get("completion_tokens", self.output_tokens) or self.output_tokens)

        return events

    def finish_events(self) -> list[str]:
        events = self._ensure_message_start()
        events.extend(self._close_open_block())
        events.extend(
            [
                format_sse_event(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": self.stop_reason,
                            "stop_sequence": None,
                        },
                        "usage": {"output_tokens": self.output_tokens},
                    },
                ),
                format_sse_event("message_stop", {"type": "message_stop"}),
            ]
        )
        return events


OPENAI_FINISH_REASON_BY_ANTHROPIC_STOP_REASON = {
    "end_turn": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


def translate_anthropic_message_to_openai_chat_completion(
    payload: dict,
    *,
    requested_model: str,
) -> dict:
    content = payload.get("content")
    if not isinstance(content, list):
        content = []

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        block_type = item.get("type")
        if block_type == "text" and isinstance(item.get("text"), str):
            text_parts.append(item["text"])
        elif block_type == "tool_use":
            tool_calls.append(
                {
                    "id": str(item.get("id") or ""),
                    "type": "function",
                    "function": {
                        "name": str(item.get("name") or ""),
                        "arguments": json.dumps(item.get("input", {})),
                    },
                }
            )

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    finish_reason = OPENAI_FINISH_REASON_BY_ANTHROPIC_STOP_REASON.get(
        str(payload.get("stop_reason") or ""),
        "stop",
    )

    message: dict[str, object] = {
        "role": "assistant",
        "content": "\n".join(text_parts) if text_parts else None,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    return {
        "id": str(payload.get("id") or "chatcmpl_generated"),
        "object": "chat.completion",
        "model": requested_model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def translate_anthropic_stream_event_to_openai_chunks(
    line: str,
    *,
    state: dict[str, object],
    requested_model: str,
) -> list[dict]:
    if not line.startswith("data:"):
        return []

    raw_payload = line.removeprefix("data:").strip()
    if not raw_payload:
        return []

    try:
        payload = json.loads(raw_payload)
    except ValueError:
        return []

    if not isinstance(payload, dict):
        return []

    event_type = payload.get("type")
    chunks: list[dict] = []

    if event_type == "message_start":
        message = payload.get("message")
        if isinstance(message, dict):
            message_id = str(message.get("id") or "chatcmpl_generated")
            state["id"] = message_id
            usage = message.get("usage")
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens")
                if isinstance(input_tokens, int):
                    state["prompt_tokens"] = input_tokens
        return chunks

    if "tool_indices" not in state:
        state["tool_indices"] = {}

    tool_indices = state["tool_indices"]
    if not isinstance(tool_indices, dict):
        tool_indices = {}
        state["tool_indices"] = tool_indices

    chunk_id = str(state.get("id") or "chatcmpl_generated")

    if event_type == "content_block_start":
        content_block = payload.get("content_block")
        index = payload.get("index")
        if (
            isinstance(content_block, dict)
            and content_block.get("type") == "tool_use"
            and isinstance(index, int)
        ):
            tool_indices[index] = index
            chunks.append(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": index,
                                        "id": str(content_block.get("id") or f"call_{index}"),
                                        "type": "function",
                                        "function": {
                                            "name": str(content_block.get("name") or ""),
                                            "arguments": "",
                                        },
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }
            )
        return chunks

    if event_type == "content_block_delta":
        index = payload.get("index")
        delta = payload.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            chunks.append(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": delta["text"]},
                            "finish_reason": None,
                        }
                    ],
                }
            )
        elif (
            isinstance(delta, dict)
            and delta.get("type") == "input_json_delta"
            and isinstance(delta.get("partial_json"), str)
            and isinstance(index, int)
        ):
            chunks.append(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": index,
                                        "type": "function",
                                        "function": {
                                            "arguments": delta["partial_json"],
                                        },
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }
            )
        return chunks

    if event_type == "message_delta":
        usage = payload.get("usage")
        if isinstance(usage, dict):
            output_tokens = usage.get("output_tokens")
            if isinstance(output_tokens, int):
                state["completion_tokens"] = output_tokens
        delta = payload.get("delta")
        stop_reason = None
        if isinstance(delta, dict):
            stop_reason = delta.get("stop_reason")
        finish_reason = OPENAI_FINISH_REASON_BY_ANTHROPIC_STOP_REASON.get(str(stop_reason or ""), "stop")
        chunks.append(
            {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "model": requested_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": int(state.get("prompt_tokens", 0) or 0),
                    "completion_tokens": int(state.get("completion_tokens", 0) or 0),
                    "total_tokens": int(state.get("prompt_tokens", 0) or 0)
                    + int(state.get("completion_tokens", 0) or 0),
                },
            }
        )
        return chunks

    return chunks


def format_openai_response_sse_event(event_type: str, payload: dict) -> str:
    event_payload = {"type": event_type, **payload}
    return f"event: {event_type}\ndata: {json.dumps(event_payload, separators=(',', ':'))}\n\n"


def _build_emulated_openai_response_from_stream_state(
    state: dict[str, object],
    *,
    requested_model: str,
) -> dict:
    anthropic_message = {
        "id": str(state.get("anthropic_message_id") or "generated"),
        "type": "message",
        "role": "assistant",
        "model": requested_model,
        "content": [{"type": "text", "text": "".join(state.get("text_parts") or [])}],
        "stop_reason": str(state.get("stop_reason") or "end_turn"),
        "usage": {
            "input_tokens": int(state.get("prompt_tokens", 0) or 0),
            "output_tokens": int(state.get("completion_tokens", 0) or 0),
        },
    }
    return translate_anthropic_message_to_openai_response(
        anthropic_message,
        requested_model=requested_model,
    )


def _emit_openai_response_completed_event(
    state: dict[str, object],
    *,
    requested_model: str,
) -> list[str]:
    if state.get("completed_emitted"):
        return []

    final_response = _build_emulated_openai_response_from_stream_state(
        state,
        requested_model=requested_model,
    )
    state["final_response"] = final_response
    state["response_id"] = final_response["id"]
    state["completed_emitted"] = True
    return [
        format_openai_response_sse_event(
            "response.completed",
            {"response": final_response},
        )
    ]


def translate_anthropic_stream_line_to_openai_response_sse(
    line: str,
    *,
    state: dict[str, object],
    requested_model: str,
) -> list[str]:
    if not line.startswith("data:"):
        return []

    raw_payload = line.removeprefix("data:").strip()
    if not raw_payload:
        return []

    try:
        payload = json.loads(raw_payload)
    except ValueError:
        return []

    if not isinstance(payload, dict):
        return []

    event_type = payload.get("type")
    if event_type == "message_start":
        message = payload.get("message")
        if not isinstance(message, dict):
            return []

        message_id = str(message.get("id") or "generated")
        state["anthropic_message_id"] = message_id
        state["response_id"] = f"resp_{message_id}"
        state["text_parts"] = []
        usage = message.get("usage")
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens")
            if isinstance(input_tokens, int):
                state["prompt_tokens"] = input_tokens

        return [
            format_openai_response_sse_event(
                "response.created",
                {
                    "response": {
                        "id": state["response_id"],
                        "object": "response",
                        "status": "in_progress",
                        "model": requested_model,
                        "output": [],
                    }
                },
            )
        ]

    if event_type == "content_block_delta":
        delta = payload.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            text = delta["text"]
            text_parts = state.setdefault("text_parts", [])
            if isinstance(text_parts, list):
                text_parts.append(text)
            return [
                format_openai_response_sse_event(
                    "response.output_text.delta",
                    {
                        "output_index": 0,
                        "content_index": 0,
                        "delta": text,
                    },
                )
            ]
        return []

    if event_type == "message_delta":
        delta = payload.get("delta")
        if isinstance(delta, dict):
            stop_reason = delta.get("stop_reason")
            if stop_reason:
                state["stop_reason"] = stop_reason
        usage = payload.get("usage")
        if isinstance(usage, dict):
            output_tokens = usage.get("output_tokens")
            if isinstance(output_tokens, int):
                state["completion_tokens"] = output_tokens
        return _emit_openai_response_completed_event(state, requested_model=requested_model)

    if event_type == "message_stop":
        return _emit_openai_response_completed_event(state, requested_model=requested_model)

    return []
