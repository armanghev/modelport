from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.translators.openai_to_anthropic import (
    translate_anthropic_stream_line_to_openai_response_sse,
)


def test_translate_anthropic_stream_line_to_openai_response_sse_events() -> None:
    state: dict[str, object] = {}

    created = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"message_start","message":{"id":"msg_123","type":"message","role":"assistant","model":"claude-sonnet-4-5","content":[],"usage":{"input_tokens":6,"output_tokens":0}}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(created) == 1
    assert "event: response.created" in created[0]
    assert '"type":"response.created"' in created[0]
    assert state["response_id"] == "resp_msg_123"

    delta = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(delta) == 1
    assert "event: response.output_text.delta" in delta[0]
    assert '"delta":"Hello"' in delta[0]

    completed = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":3}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(completed) == 1
    assert "event: response.completed" in completed[0]
    final_response = state.get("final_response")
    assert isinstance(final_response, dict)
    assert final_response["status"] == "completed"
    assert final_response["output"][0]["content"][0]["text"] == "Hello"


def test_translate_anthropic_stream_line_to_openai_response_sse_tool_use_events() -> None:
    state: dict[str, object] = {}

    created = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"message_start","message":{"id":"msg_tool","type":"message","role":"assistant","model":"claude-sonnet-4-5","content":[],"usage":{"input_tokens":6,"output_tokens":0}}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(created) == 1
    assert "event: response.created" in created[0]

    added = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_123","name":"Write","input":{}}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(added) == 1
    assert "event: response.output_item.added" in added[0]
    assert '"type":"function_call"' in added[0]
    assert '"name":"Write"' in added[0]

    delta = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"path\\":\\"out.txt\\"}"}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(delta) == 1
    assert "event: response.function_call_arguments.delta" in delta[0]
    assert '"delta":"{\\"path\\":\\"out.txt\\"}"' in delta[0]

    stopped = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"content_block_stop","index":0}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(stopped) == 2
    assert "event: response.function_call_arguments.done" in stopped[0]
    assert "event: response.output_item.done" in stopped[1]

    completed = translate_anthropic_stream_line_to_openai_response_sse(
        'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":3}}',
        state=state,
        requested_model="claude-sonnet-4-5",
    )
    assert len(completed) == 1
    assert "event: response.completed" in completed[0]
    final_response = state.get("final_response")
    assert isinstance(final_response, dict)
    assert final_response["output"][0]["type"] == "function_call"
    assert final_response["output"][0]["name"] == "Write"
    assert final_response["output"][0]["arguments"] == '{"path":"out.txt"}'


def test_responses_route_streams_anthropic_tool_use_as_openai_response_sse(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_stream_response_events(provider, api_key, payload):
        captured["payload"] = payload
        yield "event: response.created\n"
        yield 'data: {"type":"response.created","response":{"id":"resp_stream_1","status":"in_progress"}}\n'
        yield "\n"
        yield "event: response.output_text.delta\n"
        yield 'data: {"type":"response.output_text.delta","delta":"Hello"}\n'
        yield "\n"
        yield "event: response.completed\n"
        yield 'data: {"type":"response.completed","response":{"id":"resp_stream_1","status":"completed"}}\n'
        yield "\n"

    monkeypatch.setattr("app.api.openai.stream_response_events", fake_stream_response_events)

    with client.stream(
        "POST",
        "/v1/responses",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-4.1",
            "input": "hello",
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert captured["payload"]["stream"] is True
    assert "event: response.output_text.delta" in body
    assert '"delta":"Hello"' in body
    assert "event: response.completed" in body


def test_responses_route_streams_anthropic_upstream_as_openai_response_sse(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_stream_anthropic_message_events(provider, api_key, payload):
        captured["payload"] = payload
        yield 'data: {"type":"message_start","message":{"id":"msg_stream_123","type":"message","role":"assistant","model":"claude-sonnet-4-5-20250929","content":[],"usage":{"input_tokens":6,"output_tokens":0}}}'
        yield 'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}'
        yield 'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}'

    monkeypatch.setattr(
        "app.api.openai.stream_anthropic_message_events",
        fake_stream_anthropic_message_events,
    )

    with client.stream(
        "POST",
        "/v1/responses",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "input": "hello",
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: response.created" in body
    assert "event: response.output_text.delta" in body
    assert '"delta":"Hello"' in body
    assert "event: response.completed" in body
    assert captured["payload"]["stream"] is True

    retrieve_response = client.get(
        "/v1/responses/resp_msg_stream_123",
        headers={"Authorization": "Bearer test-local-token"},
    )
    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["output"][0]["content"][0]["text"] == "Hello"


def test_responses_route_streams_anthropic_tool_use_as_openai_response_sse(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_anthropic_message_events(provider, api_key, payload):
        yield 'data: {"type":"message_start","message":{"id":"msg_stream_tool","type":"message","role":"assistant","model":"claude-sonnet-4-5-20250929","content":[],"usage":{"input_tokens":8,"output_tokens":0}}}'
        yield 'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_123","name":"Write","input":{}}}'
        yield 'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"path\\":\\"out.txt\\"}"}}'
        yield 'data: {"type":"content_block_stop","index":0}'
        yield 'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":4}}'

    monkeypatch.setattr(
        "app.api.openai.stream_anthropic_message_events",
        fake_stream_anthropic_message_events,
    )

    with client.stream(
        "POST",
        "/v1/responses",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "input": "write a file",
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: response.output_item.added" in body
    assert '"type":"function_call"' in body
    assert "event: response.function_call_arguments.delta" in body
    assert "event: response.function_call_arguments.done" in body
    assert "event: response.completed" in body

    retrieve_response = client.get(
        "/v1/responses/resp_msg_stream_tool",
        headers={"Authorization": "Bearer test-local-token"},
    )
    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["output"][0]["type"] == "function_call"
    assert retrieve_response.json()["output"][0]["name"] == "Write"


def test_responses_stream_persists_passthrough_metadata(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_stream_response_events(provider, api_key, payload):
        yield "event: response.created\n"
        yield (
            'data: {"type":"response.created","response":{"id":"resp_stream_persist",'
            '"status":"in_progress","model":"gpt-4.1","object":"response","output":[]}}\n'
        )
        yield "\n"
        yield "event: response.completed\n"
        yield (
            'data: {"type":"response.completed","response":{"id":"resp_stream_persist",'
            '"status":"completed","model":"gpt-4.1","object":"response","output":[]}}\n'
        )
        yield "\n"

    def fake_get_response(provider, api_key, response_id):
        return {
            "id": response_id,
            "object": "response",
            "status": "completed",
            "model": "gpt-4.1",
            "output": [],
        }

    monkeypatch.setattr("app.api.openai.stream_response_events", fake_stream_response_events)
    monkeypatch.setattr("app.api.openai.get_response", fake_get_response)

    with client.stream(
        "POST",
        "/v1/responses",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-4.1",
            "input": "hello",
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        assert "".join(response.iter_text())

    retrieve_response = client.get(
        "/v1/responses/resp_stream_persist",
        headers={"Authorization": "Bearer test-local-token"},
    )
    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["id"] == "resp_stream_persist"
