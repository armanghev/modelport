from modelport_agent_config.model_picker import (
    build_provider_tabs,
    filter_models_for_provider,
    routed_model_id,
)
from modelport_agent_config.modelport import ProviderModel


def _catalog() -> dict[str, list[ProviderModel]]:
    return {
        "openrouter": [
            ProviderModel(id="anthropic/claude-sonnet-4", display_name="Claude Sonnet 4"),
        ],
        "gemini": [
            ProviderModel(id="models/gemini-2.5-flash", display_name="Gemini 2.5 Flash"),
        ],
    }


def test_build_provider_tabs_uses_runtime_order() -> None:
    tabs = build_provider_tabs(_catalog(), ("gemini", "openrouter", "anthropic"))
    assert [tab.provider_id for tab in tabs] == ["gemini", "openrouter"]


def test_filter_models_for_provider_matches_query() -> None:
    models = _catalog()["openrouter"]
    filtered = filter_models_for_provider(models, query="sonnet")
    assert len(filtered) == 1
    assert filtered[0].id == "anthropic/claude-sonnet-4"


def test_routed_model_id_returns_catalog_id() -> None:
    model = _catalog()["gemini"][0]
    assert routed_model_id(model) == "models/gemini-2.5-flash"
