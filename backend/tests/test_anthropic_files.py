from __future__ import annotations

from fastapi.testclient import TestClient


def test_files_upload_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_create_file(provider, api_key, *, filename, content, content_type):
        captured["provider_id"] = provider.id
        captured["api_key"] = api_key
        captured["filename"] = filename
        captured["content"] = content
        captured["content_type"] = content_type
        return {
            "id": "file_123",
            "type": "file",
            "filename": filename,
            "mime_type": content_type,
            "size_bytes": len(content),
            "downloadable": False,
        }

    monkeypatch.setattr("app.api.anthropic.create_file", fake_create_file)

    response = client.post(
        "/v1/files",
        headers={"Authorization": "Bearer test-local-token"},
        data={"provider": "anthropic"},
        files={"file": ("document.pdf", b"pdf-bytes", "application/pdf")},
    )

    assert response.status_code == 200
    assert captured["provider_id"] == "anthropic"
    assert captured["filename"] == "document.pdf"
    assert captured["content"] == b"pdf-bytes"
    assert captured["content_type"] == "application/pdf"
    assert response.json()["id"] == "file_123"


def test_files_list_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_list_files(provider, api_key, *, after_id=None, before_id=None, limit=None, scope_id=None):
        captured.update(
            {
                "provider_id": provider.id,
                "after_id": after_id,
                "before_id": before_id,
                "limit": limit,
                "scope_id": scope_id,
            }
        )
        return {
            "data": [
                {
                    "id": "file_123",
                    "type": "file",
                    "filename": "document.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 9,
                    "downloadable": False,
                }
            ],
            "has_more": False,
        }

    monkeypatch.setattr("app.api.anthropic.list_files", fake_list_files)

    response = client.get(
        "/v1/files",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
        params={"limit": 5, "scope_id": "scope_1"},
    )

    assert response.status_code == 200
    assert captured["provider_id"] == "anthropic"
    assert captured["limit"] == 5
    assert captured["scope_id"] == "scope_1"
    assert response.json()["data"][0]["id"] == "file_123"


def test_files_retrieve_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_get_file(provider, api_key, file_id):
        assert file_id == "file_123"
        return {
            "id": "file_123",
            "type": "file",
            "filename": "document.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 9,
            "downloadable": False,
        }

    monkeypatch.setattr("app.api.anthropic.get_file", fake_get_file)

    response = client.get(
        "/v1/files/file_123",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "document.pdf"


def test_files_content_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    def fake_get_file_content(provider, api_key, file_id):
        assert file_id == "file_123"
        return b"pdf-bytes", "application/pdf"

    monkeypatch.setattr("app.api.anthropic.get_file_content", fake_get_file_content)

    response = client.get(
        "/v1/files/file_123/content",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content == b"pdf-bytes"


def test_files_delete_route_proxies_anthropic_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: dict = {}

    def fake_delete_file(provider, api_key, file_id):
        captured["file_id"] = file_id
        return {"id": file_id, "type": "file_deleted"}

    monkeypatch.setattr("app.api.anthropic.delete_file", fake_delete_file)

    response = client.delete(
        "/v1/files/file_123",
        headers={
            "Authorization": "Bearer test-local-token",
            "X-ModelPort-Provider": "anthropic",
        },
    )

    assert response.status_code == 200
    assert captured["file_id"] == "file_123"
    assert response.json()["type"] == "file_deleted"


def test_files_upload_route_rejects_openai_provider(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/files",
        headers={"Authorization": "Bearer test-local-token"},
        data={"provider": "openai"},
        files={"file": ("document.pdf", b"pdf-bytes", "application/pdf")},
    )

    assert response.status_code == 501
