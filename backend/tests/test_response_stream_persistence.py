from __future__ import annotations

import pytest

from app.responses.store import ingest_passthrough_response_stream_line


def test_ingest_passthrough_response_stream_line_tracks_created_and_completed() -> None:
    state: dict[str, object] = {}

    ingest_passthrough_response_stream_line(
        'data: {"type":"response.created","response":{"id":"resp_1","status":"in_progress"}}\n',
        state,
    )
    ingest_passthrough_response_stream_line(
        'data: {"type":"response.completed","response":{"id":"resp_1","status":"completed","output":[]}}\n',
        state,
    )

    assert state["response_id"] == "resp_1"
    assert state["status"] == "completed"
    assert isinstance(state["final_response"], dict)
