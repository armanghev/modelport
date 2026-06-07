from __future__ import annotations

from fastapi.testclient import TestClient

from app.compatibility.capabilities import PROXY_ROUTE_CAPABILITIES


def test_proxy_route_capabilities_include_openai_image_families() -> None:
    routes = {capability.route for capability in PROXY_ROUTE_CAPABILITIES}
    assert "/v1/images/generations" in routes
    assert "/v1/images/edits" in routes
    assert "/v1/images/variations" in routes


def test_image_generations_route_proxies_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_image_generation(provider, api_key, payload):
        captured["payload"] = payload
        return {
            "created": 1730000000,
            "data": [{"b64_json": "abc123"}],
        }

    monkeypatch.setattr("app.api.openai.create_image_generation", fake_create_image_generation)

    response = client.post(
        "/v1/images/generations",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "openai",
            "model": "gpt-image-1",
            "prompt": "A watercolor lighthouse at sunset",
            "size": "1024x1024",
        },
    )

    assert response.status_code == 200
    assert captured["payload"] == {
        "model": "gpt-image-1",
        "prompt": "A watercolor lighthouse at sunset",
        "size": "1024x1024",
    }
    assert response.json()["data"][0]["b64_json"] == "abc123"


def test_image_generations_route_rejects_anthropic_provider(client: TestClient) -> None:
    response = client.post(
        "/v1/images/generations",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "gpt-image-1",
            "prompt": "A lighthouse",
        },
    )

    assert response.status_code == 501


def test_image_edits_route_proxies_multipart_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_image_edit(provider, api_key, *, form_fields, files):
        captured["form_fields"] = form_fields
        captured["files"] = files
        return {
            "created": 1730000000,
            "data": [{"b64_json": "edited123"}],
        }

    monkeypatch.setattr("app.api.openai.create_image_edit", fake_create_image_edit)

    response = client.post(
        "/v1/images/edits",
        headers={"Authorization": "Bearer test-local-token"},
        data={
            "provider": "openai",
            "model": "gpt-image-1",
            "prompt": "Add a red balloon",
        },
        files={"image": ("input.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 200
    assert captured["form_fields"] == {
        "model": "gpt-image-1",
        "prompt": "Add a red balloon",
    }
    assert captured["files"]["image"][0] == "input.png"
    assert captured["files"]["image"][1] == b"png-bytes"
    assert response.json()["data"][0]["b64_json"] == "edited123"


def test_image_variations_route_proxies_multipart_openai_compatible_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_image_variation(provider, api_key, *, form_fields, files):
        captured["form_fields"] = form_fields
        captured["files"] = files
        return {
            "created": 1730000000,
            "data": [{"url": "https://example.com/variation.png"}],
        }

    monkeypatch.setattr("app.api.openai.create_image_variation", fake_create_image_variation)

    response = client.post(
        "/v1/images/variations",
        headers={"Authorization": "Bearer test-local-token"},
        data={
            "provider": "openai",
            "model": "dall-e-2",
            "size": "1024x1024",
        },
        files={"image": ("square.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 200
    assert captured["form_fields"] == {
        "model": "dall-e-2",
        "size": "1024x1024",
    }
    assert response.json()["data"][0]["url"] == "https://example.com/variation.png"
