from __future__ import annotations

import copy
import json
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import Response

PROXY_PATH_PREFIX = "/v1/"
PROXY_OPENAPI_PATH = "/openapi/proxy.json"
PROXY_DOCS_PATH = "/docs/proxy"

OPENAPI_DESCRIPTION = (
    "ModelPort proxy API. OpenAI-compatible clients should use /v1/chat/completions and "
    "/v1/models. Anthropic-compatible clients should use /v1/messages."
)


def collect_schema_refs(node: Any, refs: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.removeprefix("#/components/schemas/"))
        for value in node.values():
            collect_schema_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            collect_schema_refs(item, refs)


def prune_component_schemas(schema: dict) -> dict:
    components = schema.get("components")
    if not isinstance(components, dict):
        return schema

    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return schema

    referenced: set[str] = set()
    collect_schema_refs(schema.get("paths", {}), referenced)

    expanded = set(referenced)
    while True:
        newly_found: set[str] = set()
        for name in expanded:
            component = schemas.get(name)
            if component is not None:
                collect_schema_refs(component, newly_found)
        newly_found -= expanded
        if not newly_found:
            break
        expanded |= newly_found

    components["schemas"] = {
        name: schemas[name] for name in sorted(expanded) if name in schemas
    }
    return schema


def filter_proxy_paths(schema: dict) -> dict:
    filtered = copy.deepcopy(schema)
    filtered["paths"] = {
        path: operations
        for path, operations in schema.get("paths", {}).items()
        if path.startswith(PROXY_PATH_PREFIX)
    }
    proxy_tags = {tag["name"] for tag in filtered.get("tags", []) if tag["name"] == "proxy"}
    if proxy_tags:
        filtered["tags"] = [tag for tag in filtered.get("tags", []) if tag["name"] in proxy_tags]
    filtered["info"] = {
        **filtered.get("info", {}),
        "title": "ModelPort Proxy API",
        "description": OPENAPI_DESCRIPTION,
    }
    return prune_component_schemas(filtered)


def openapi_json_response(content: dict) -> Response:
    return Response(
        content=json.dumps(content, indent=2),
        media_type="application/json; charset=utf-8",
    )


def configure_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        bearer_scheme = schema.get("components", {}).get("securitySchemes", {}).get("BearerAuth")
        if bearer_scheme is not None:
            bearer_scheme["description"] = (
                "ModelPort proxy token. Set MODELPORT_TOKEN in your environment and send it as a Bearer token."
            )

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    def build_proxy_openapi_response() -> Response:
        return openapi_json_response(filter_proxy_paths(app.openapi()))

    @app.get(PROXY_OPENAPI_PATH, include_in_schema=False)
    def proxy_openapi_json() -> Response:
        return build_proxy_openapi_response()

    @app.get(PROXY_DOCS_PATH, include_in_schema=False)
    def proxy_docs() -> str:
        return get_swagger_ui_html(
            openapi_url=PROXY_OPENAPI_PATH,
            title="ModelPort Proxy API",
        )
