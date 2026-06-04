from __future__ import annotations

from app.database import ModelMetadata
from app.model_metadata_service import (
    OPENROUTER_MODELS_QUERY_PARAMS,
    OPENROUTER_MODELS_URL,
    MetadataLookup,
    apply_gemini_native_model_fields,
    enrich_provider_model,
    fetch_openrouter_models_api_payload,
    load_metadata_index,
    match_model_metadata,
    parse_openrouter_model,
    parse_openrouter_upstream_models,
)


def test_fetch_openrouter_models_api_payload_requests_all_output_modalities(
    monkeypatch,
) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": []}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setattr("app.model_metadata_service.httpx.Client", FakeClient)
    fetch_openrouter_models_api_payload()

    assert captured["url"] == OPENROUTER_MODELS_URL
    assert captured["kwargs"]["params"] == OPENROUTER_MODELS_QUERY_PARAMS


def test_parse_openrouter_model_treats_negative_pricing_as_unknown() -> None:
    record = parse_openrouter_model(
        {
            "id": "openai/o3-pro",
            "pricing": {"prompt": "-1", "completion": "-1"},
        }
    )

    assert record is not None
    assert record["input_per_1m_usd"] is None
    assert record["output_per_1m_usd"] is None


def test_parse_openrouter_model_extracts_metadata_fields() -> None:
    record = parse_openrouter_model(
        {
            "id": "openai/gpt-4.1",
            "canonical_slug": "openai/gpt-4.1",
            "name": "GPT-4.1",
            "description": "General-purpose model",
            "context_length": 128000,
            "architecture": {
                "modality": "text",
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "supported_parameters": ["tools", "response_format"],
            "pricing": {"prompt": "0.000002", "completion": "0.000008"},
        }
    )

    assert record is not None
    assert record["id"] == "openai/gpt-4.1"
    assert record["context_length"] == 128000
    assert record["input_per_1m_usd"] == 2.0
    assert record["output_per_1m_usd"] == 8.0
    assert "tools" in record["supported_parameters"]


def test_match_model_metadata_matches_gemini_models_prefix(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ModelMetadata(
                id="google/gemini-2.5-pro",
                canonical_slug="google/gemini-2.5-pro",
                name="Gemini 2.5 Pro",
                description="Flagship Gemini model",
                context_length=1_048_576,
                architecture_json="{}",
                input_modalities_json='["text"]',
                output_modalities_json='["text"]',
                supported_parameters_json='["tools"]',
                source="openrouter",
            )
        )
        session.commit()
        metadata_index = load_metadata_index(session)

    for model_id in ("models/gemini-2.5-pro", "gemini-2.5-pro"):
        match = match_model_metadata("gemini", model_id, metadata_index)
        assert match is not None
        assert match.id == "google/gemini-2.5-pro"


def test_match_model_metadata_prefers_vendor_on_ambiguous_suffix(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add_all(
            [
                ModelMetadata(
                    id="openai/gpt-4.1",
                    canonical_slug="openai/gpt-4.1",
                    name="GPT-4.1",
                    architecture_json="{}",
                    input_modalities_json="[]",
                    output_modalities_json="[]",
                    supported_parameters_json="[]",
                    source="openrouter",
                ),
                ModelMetadata(
                    id="meta-llama/gpt-4.1",
                    canonical_slug="meta-llama/gpt-4.1",
                    name="Unrelated",
                    architecture_json="{}",
                    input_modalities_json="[]",
                    output_modalities_json="[]",
                    supported_parameters_json="[]",
                    source="openrouter",
                ),
            ]
        )
        session.commit()
        metadata_index = load_metadata_index(session)

    match = match_model_metadata("openai", "gpt-4.1", metadata_index)
    assert match is not None
    assert match.id == "openai/gpt-4.1"


def test_parse_openrouter_upstream_models_preserves_rich_fields() -> None:
    models = parse_openrouter_upstream_models(
        {
            "data": [
                {
                    "id": "anthropic/claude-sonnet-4-6",
                    "name": "Claude Sonnet 4.6",
                    "description": "Balanced Claude model",
                    "context_length": 200000,
                    "architecture": {
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                    "supported_parameters": ["tools"],
                    "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                }
            ]
        }
    )

    assert len(models) == 1
    assert models[0]["id"] == "anthropic/claude-sonnet-4-6"
    assert models[0]["context_length"] == 200000
    parsed = models[0]["openrouter_metadata"]
    assert parsed["supported_parameters"] == ["tools"]
    assert parsed["input_per_1m_usd"] == 3.0


def test_enrich_provider_model_uses_inline_openrouter_metadata(client) -> None:
    from app.database import Provider
    from app.model_metadata_service import build_pricing_index, build_usage_index

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = session.get(Provider, "openai")
        assert provider is not None
        parsed = parse_openrouter_model(
            {
                "id": "openai/gpt-4.1",
                "name": "GPT-4.1",
                "description": "From live OpenRouter payload",
                "context_length": 128000,
                "supported_parameters": ["tools"],
                "pricing": {"prompt": "0.000002", "completion": "0.000008"},
            }
        )
        assert parsed is not None
        enriched = enrich_provider_model(
            provider=provider,
            raw_model={
                "id": "gpt-4.1",
                "display_name": None,
                "owned_by": "openai",
                "openrouter_metadata": parsed,
            },
            metadata_index=MetadataLookup(),
            pricing_index=build_pricing_index(session),
            usage_index=build_usage_index(session),
        )

    assert enriched["metadata_source"] == "openrouter"
    assert enriched["description"] == "From live OpenRouter payload"
    assert enriched["context_length"] == 128000
    assert enriched["supported_parameters"] == ["tools"]
    assert enriched["openrouter_id"] == "openai/gpt-4.1"


def test_match_model_metadata_normalizes_provider_prefixed_ids(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ModelMetadata(
                id="openai/gpt-4.1",
                canonical_slug="openai/gpt-4.1",
                name="GPT-4.1",
                architecture_json="{}",
                input_modalities_json='["text"]',
                output_modalities_json='["text"]',
                supported_parameters_json="[]",
                source="openrouter",
            )
        )
        session.commit()
        metadata_index = load_metadata_index(session)

    match = match_model_metadata("openai", "gpt-4.1", metadata_index)
    assert match is not None
    assert match.id == "openai/gpt-4.1"


def test_enrich_provider_model_merges_metadata_pricing_and_usage(client) -> None:
    from app.database import PricingOverride, Provider

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = session.get(Provider, "openai")
        assert provider is not None
        session.add(
            ModelMetadata(
                id="openai/gpt-4.1",
                canonical_slug="openai/gpt-4.1",
                name="GPT-4.1",
                description="Reference metadata",
                context_length=128000,
                architecture_json='{"modality":"text"}',
                input_modalities_json='["text"]',
                output_modalities_json='["text"]',
                supported_parameters_json='["tools"]',
                input_per_1m_usd=2.5,
                output_per_1m_usd=10.0,
                source="openrouter",
            )
        )
        session.add(
            PricingOverride(
                provider_id="openai",
                model="gpt-4.1",
                input_per_1m_usd=2.0,
                output_per_1m_usd=8.0,
                currency="USD",
                enabled=True,
            )
        )
        session.commit()

        metadata_index = load_metadata_index(session)
        from app.model_metadata_service import build_pricing_index, build_usage_index

        enriched = enrich_provider_model(
            provider=provider,
            raw_model={"id": "gpt-4.1", "display_name": None, "owned_by": "openai"},
            metadata_index=metadata_index,
            pricing_index=build_pricing_index(session),
            usage_index=build_usage_index(session),
        )

    assert enriched["metadata_source"] == "openrouter"
    assert enriched["context_length"] == 128000
    assert enriched["input_per_1m_usd"] == 2.0
    assert enriched["supported_parameters"] == ["tools"]
    assert enriched["display_name"] == "GPT-4.1"


def test_filter_gemini_catalog_models_excludes_non_chat_and_retired() -> None:
    from app.model_metadata_service import filter_gemini_catalog_models

    models = [
        {"id": "models/gemini-2.0-flash"},
        {"id": "models/gemini-2.5-flash"},
        {"id": "models/gemini-embedding-001"},
    ]
    native_index = {
        # Retired models may still advertise generateContent in the catalog API.
        "models/gemini-2.0-flash": {"supportedGenerationMethods": ["generateContent"]},
        "models/gemini-2.5-flash": {
            "supportedGenerationMethods": ["generateContent", "countTokens"],
        },
    }
    filtered = filter_gemini_catalog_models(models, native_index)
    assert [model["id"] for model in filtered] == ["models/gemini-2.5-flash"]


def test_filter_gemini_catalog_models_without_native_index() -> None:
    from app.model_metadata_service import filter_gemini_catalog_models

    models = [
        {"id": "models/gemini-2.0-flash"},
        {"id": "models/gemini-2.5-flash"},
    ]
    filtered = filter_gemini_catalog_models(models, None)
    assert [model["id"] for model in filtered] == ["models/gemini-2.5-flash"]


def test_apply_gemini_native_model_fields_merges_description_and_context() -> None:
    native_index = {
        "models/gemini-2.5-pro": {
            "name": "models/gemini-2.5-pro",
            "displayName": "Gemini 2.5 Pro",
            "description": "Our most capable model for complex tasks.",
            "inputTokenLimit": 1_048_576,
        }
    }
    models = apply_gemini_native_model_fields(
        [{"id": "models/gemini-2.5-pro", "display_name": None, "owned_by": "google"}],
        native_index,
    )

    assert models[0]["description"] == "Our most capable model for complex tasks."
    assert models[0]["display_name"] == "Gemini 2.5 Pro"
    assert models[0]["context_length"] == 1_048_576


def test_enrich_provider_model_uses_upstream_description_when_metadata_missing(client) -> None:
    from app.database import Provider

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = session.get(Provider, "gemini")
        assert provider is not None
        from app.model_metadata_service import build_pricing_index, build_usage_index

        enriched = enrich_provider_model(
            provider=provider,
            raw_model={
                "id": "models/gemini-2.5-pro",
                "display_name": "Gemini 2.5 Pro",
                "owned_by": "google",
                "description": "Provider-native description",
            },
            metadata_index=load_metadata_index(session),
            pricing_index=build_pricing_index(session),
            usage_index=build_usage_index(session),
        )

    assert enriched["description"] == "Provider-native description"
    assert enriched["display_name"] == "Gemini 2.5 Pro"
