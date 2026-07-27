from modelport_agent_config.model_picker import (
    _model_options_for_tab,
    build_provider_tabs,
    filter_models_for_provider,
    routed_model_id,
)
from modelport_agent_config.modelport import ProviderModel


def _catalog() -> dict[str, list[ProviderModel]]:
    return {
        "openrouter": [
            ProviderModel(id="anthropic/claude-sonnet-4", display_name="Claude Sonnet 4"),
            ProviderModel(id="openai/gpt-4o-mini", display_name="GPT-4o mini"),
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


def test_filter_models_for_provider_matches_display_name() -> None:
    models = _catalog()["openrouter"]
    filtered = filter_models_for_provider(models, query="gpt-4o")
    assert [model.id for model in filtered] == ["openai/gpt-4o-mini"]


def test_filter_models_for_provider_empty_query_returns_all() -> None:
    models = _catalog()["openrouter"]
    assert filter_models_for_provider(models, query="  ") == list(models)


def test_routed_model_id_returns_catalog_id() -> None:
    model = _catalog()["gemini"][0]
    assert routed_model_id(model) == "models/gemini-2.5-flash"


def test_model_options_for_tab_uses_catalog_models() -> None:
    tabs = build_provider_tabs(_catalog(), ("openrouter",))
    options = _model_options_for_tab(tabs[0])
    assert options[0] == ("anthropic/claude-sonnet-4", "Claude Sonnet 4")


def test_model_options_for_tab_falls_back_to_suggestions() -> None:
    from modelport_agent_config.model_picker import ProviderTab

    tab = ProviderTab(provider_id="gemini", models=())
    options = _model_options_for_tab(tab)
    assert ("models/gemini-2.5-flash", "models/gemini-2.5-flash") in options
