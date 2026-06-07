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


def test_responses_route_streams_openai_upstream_sse(
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
