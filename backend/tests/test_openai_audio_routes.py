from __future__ import annotations

from fastapi.testclient import TestClient

from app.compatibility.capabilities import PROXY_ROUTE_CAPABILITIES


def test_proxy_route_capabilities_include_openai_audio_families() -> None:
    routes = {capability.route for capability in PROXY_ROUTE_CAPABILITIES}
    assert "/v1/audio/transcriptions" in routes
    assert "/v1/audio/translations" in routes
    assert "/v1/audio/speech" in routes


def test_audio_transcriptions_route_proxies_multipart_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_audio_transcription(provider, api_key, *, form_fields, files):
        captured["form_fields"] = form_fields
        captured["files"] = files
        return {
            "text": "Hello, thanks for calling support.",
            "usage": {
                "type": "tokens",
                "input_tokens": 124,
                "output_tokens": 12,
                "total_tokens": 136,
            },
        }

    monkeypatch.setattr("app.api.openai.create_audio_transcription", fake_create_audio_transcription)

    response = client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer test-local-token"},
        data={
            "provider": "openai",
            "model": "gpt-4o-transcribe",
            "response_format": "json",
        },
        files={"file": ("audio.mp3", b"mp3-bytes", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert captured["form_fields"] == {
        "model": "gpt-4o-transcribe",
        "response_format": "json",
    }
    assert captured["files"]["file"][1] == b"mp3-bytes"
    assert response.json()["text"] == "Hello, thanks for calling support."


def test_audio_translations_route_proxies_multipart_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_audio_translation(provider, api_key, *, form_fields, files):
        captured["form_fields"] = form_fields
        captured["files"] = files
        return {"text": "Hello, my name is Wolfgang and I come from Germany."}

    monkeypatch.setattr("app.api.openai.create_audio_translation", fake_create_audio_translation)

    response = client.post(
        "/v1/audio/translations",
        headers={"Authorization": "Bearer test-local-token"},
        data={
            "provider": "openai",
            "model": "whisper-1",
            "response_format": "json",
        },
        files={"file": ("audio.mp3", b"mp3-bytes", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert captured["form_fields"] == {
        "model": "whisper-1",
        "response_format": "json",
    }
    assert response.json()["text"] == "Hello, my name is Wolfgang and I come from Germany."


def test_audio_speech_route_proxies_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_audio_speech(provider, api_key, payload):
        captured["payload"] = payload
        return b"audio-bytes", "audio/mpeg"

    monkeypatch.setattr("app.api.openai.create_audio_speech", fake_create_audio_speech)

    response = client.post(
        "/v1/audio/speech",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-4o-mini-tts",
            "input": "The quick brown fox jumped over the lazy dog.",
            "voice": "alloy",
            "response_format": "mp3",
        },
    )

    assert response.status_code == 200
    assert captured["payload"] == {
        "model": "gpt-4o-mini-tts",
        "input": "The quick brown fox jumped over the lazy dog.",
        "voice": "alloy",
        "response_format": "mp3",
    }
    assert response.content == b"audio-bytes"
    assert response.headers["content-type"] == "audio/mpeg"


def test_audio_speech_route_rejects_anthropic_provider(client: TestClient) -> None:
    response = client.post(
        "/v1/audio/speech",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "gpt-4o-mini-tts",
            "input": "Hello",
            "voice": "alloy",
        },
    )

    assert response.status_code == 501
