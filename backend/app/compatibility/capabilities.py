from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProxyRouteCapability:
    route: str
    methods: tuple[str, ...]
    client_protocol: str
    upstream_provider_types: tuple[str, ...]
    streaming: str
    storage: str


PROXY_ROUTE_CAPABILITIES: tuple[ProxyRouteCapability, ...] = (
    ProxyRouteCapability(
        route="/v1/chat/completions",
        methods=("POST",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="bidirectional_translation",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/messages",
        methods=("POST",),
        client_protocol="anthropic",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="bidirectional_translation",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/models",
        methods=("GET",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="none",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/models/{model}",
        methods=("GET",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="none",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/responses",
        methods=("POST",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="upstream_passthrough_or_emulated",
        storage="proxy_response_resource",
    ),
    ProxyRouteCapability(
        route="/v1/responses/{response_id}",
        methods=("GET",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="none",
        storage="proxy_response_resource",
    ),
    ProxyRouteCapability(
        route="/v1/responses/{response_id}/input_items",
        methods=("GET",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="none",
        storage="proxy_response_resource",
    ),
    ProxyRouteCapability(
        route="/v1/responses/{response_id}/cancel",
        methods=("POST",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible", "anthropic_compatible"),
        streaming="none",
        storage="proxy_response_resource",
    ),
    ProxyRouteCapability(
        route="/v1/embeddings",
        methods=("POST",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible",),
        streaming="none",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/completions",
        methods=("POST",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible",),
        streaming="upstream_passthrough",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/moderations",
        methods=("POST",),
        client_protocol="openai",
        upstream_provider_types=("openai_compatible",),
        streaming="none",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/messages/count_tokens",
        methods=("POST",),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="none",
        storage="none",
    ),
    ProxyRouteCapability(
        route="/v1/messages/batches",
        methods=("POST", "GET"),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="none",
        storage="upstream_passthrough",
    ),
    ProxyRouteCapability(
        route="/v1/messages/batches/{message_batch_id}",
        methods=("GET", "DELETE"),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="none",
        storage="upstream_passthrough",
    ),
    ProxyRouteCapability(
        route="/v1/messages/batches/{message_batch_id}/cancel",
        methods=("POST",),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="none",
        storage="upstream_passthrough",
    ),
    ProxyRouteCapability(
        route="/v1/messages/batches/{message_batch_id}/results",
        methods=("GET",),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="jsonlines_passthrough",
        storage="upstream_passthrough",
    ),
    ProxyRouteCapability(
        route="/v1/files",
        methods=("POST", "GET"),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="none",
        storage="upstream_passthrough",
    ),
    ProxyRouteCapability(
        route="/v1/files/{file_id}",
        methods=("GET", "DELETE"),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="none",
        storage="upstream_passthrough",
    ),
    ProxyRouteCapability(
        route="/v1/files/{file_id}/content",
        methods=("GET",),
        client_protocol="anthropic",
        upstream_provider_types=("anthropic_compatible",),
        streaming="binary_passthrough",
        storage="upstream_passthrough",
    ),
)


def get_proxy_route_capability(route: str) -> ProxyRouteCapability | None:
    for capability in PROXY_ROUTE_CAPABILITIES:
        if capability.route == route:
            return capability
    return None
