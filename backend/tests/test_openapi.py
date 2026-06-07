from __future__ import annotations

from fastapi.testclient import TestClient


def test_openapi_includes_bearer_auth_for_proxy_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    security_schemes = schema["components"]["securitySchemes"]
    assert "BearerAuth" in security_schemes
    assert security_schemes["BearerAuth"]["scheme"] == "bearer"

    for path in (
        "/v1/models",
        "/v1/models/{model}",
        "/v1/chat/completions",
        "/v1/responses",
        "/v1/responses/{response_id}",
        "/v1/responses/{response_id}/input_items",
        "/v1/responses/{response_id}/cancel",
        "/v1/messages",
        "/v1/messages/batches",
        "/v1/messages/batches/{message_batch_id}",
        "/v1/messages/batches/{message_batch_id}/cancel",
        "/v1/messages/batches/{message_batch_id}/results",
        "/v1/embeddings",
        "/v1/messages/count_tokens",
    ):
        for operation in schema["paths"][path].values():
            assert operation["security"] == [{"BearerAuth": []}]


def test_openapi_documents_modelport_provider_header(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    for path in (
        "/v1/models",
        "/v1/models/{model}",
        "/v1/chat/completions",
        "/v1/responses",
        "/v1/responses/{response_id}",
        "/v1/responses/{response_id}/input_items",
        "/v1/responses/{response_id}/cancel",
        "/v1/messages",
        "/v1/messages/batches",
        "/v1/messages/batches/{message_batch_id}",
        "/v1/messages/batches/{message_batch_id}/cancel",
        "/v1/messages/batches/{message_batch_id}/results",
        "/v1/embeddings",
        "/v1/messages/count_tokens",
    ):
        for operation in schema["paths"][path].values():
            header_params = [
                parameter
                for parameter in operation.get("parameters", [])
                if parameter.get("in") == "header"
                and parameter.get("name") == "X-ModelPort-Provider"
            ]
            assert len(header_params) == 1
            assert "provider override" in header_params[0]["description"].lower()


def test_proxy_openapi_filters_to_v1_routes(client: TestClient) -> None:
    for path in ("/openapi/proxy.json", "/openapi/proxy"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert len(response.text.strip()) > 0

        schema = response.json()
        assert schema["info"]["title"] == "ModelPort Proxy API"
        assert set(schema["paths"]) == {
            "/v1/chat/completions",
            "/v1/embeddings",
            "/v1/messages",
            "/v1/messages/batches",
            "/v1/messages/batches/{message_batch_id}",
            "/v1/messages/batches/{message_batch_id}/cancel",
            "/v1/messages/batches/{message_batch_id}/results",
            "/v1/messages/count_tokens",
            "/v1/models",
            "/v1/models/{model}",
            "/v1/responses",
            "/v1/responses/{response_id}",
            "/v1/responses/{response_id}/cancel",
            "/v1/responses/{response_id}/input_items",
        }
        assert "ProviderResponse" not in schema.get("components", {}).get("schemas", {})


def test_openapi_json_is_non_empty(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert len(response.text.strip()) > 0
    assert len(response.json().get("paths", {})) > 0


def test_proxy_docs_page_is_available(client: TestClient) -> None:
    response = client.get("/docs/proxy")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
