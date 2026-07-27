from __future__ import annotations

from dataclasses import dataclass

import questionary
from questionary import Choice

from modelport_agent_config.modelport import ProviderModel
from modelport_agent_config.prompts import (
    _STYLE,
    _dim,
    _interactive_available,
    print_step,
    prompt_text,
)

_SKIP_SENTINEL = "__skip__"
_CUSTOM_SENTINEL = "__custom__"


@dataclass(frozen=True)
class ProviderTab:
    provider_id: str
    models: tuple[ProviderModel, ...]


def build_provider_tabs(
    catalog: dict[str, list[ProviderModel]],
    provider_ids: tuple[str, ...],
) -> list[ProviderTab]:
    ordered_ids = list(provider_ids) or sorted(catalog.keys())
    tabs: list[ProviderTab] = []
    seen: set[str] = set()
    for provider_id in ordered_ids:
        normalized = provider_id.strip().lower()
        if not normalized or normalized in seen:
            continue
        models = catalog.get(normalized)
        if not models:
            continue
        seen.add(normalized)
        tabs.append(ProviderTab(provider_id=normalized, models=tuple(models)))
    for provider_id in sorted(catalog.keys()):
        if provider_id in seen:
            continue
        models = catalog[provider_id]
        if models:
            tabs.append(ProviderTab(provider_id=provider_id, models=tuple(models)))
    return tabs


def filter_models_for_provider(
    models: tuple[ProviderModel, ...] | list[ProviderModel],
    *,
    query: str = "",
) -> list[ProviderModel]:
    needle = query.strip().lower()
    if not needle:
        return list(models)
    filtered: list[ProviderModel] = []
    for model in models:
        haystacks = [model.id.lower()]
        if model.display_name:
            haystacks.append(model.display_name.lower())
        if any(needle in hay for hay in haystacks):
            filtered.append(model)
    return filtered


def routed_model_id(model: ProviderModel) -> str:
    """Return the model id stored for Claude Code; backend infers provider from it."""
    return model.id


def _suggested_models_for_provider(provider_id: str) -> list[tuple[str, str]]:
    if provider_id == "openrouter":
        return [
            ("anthropic/claude-sonnet-4", "anthropic/claude-sonnet-4"),
            ("anthropic/claude-opus-4", "anthropic/claude-opus-4"),
            ("openai/gpt-4o-mini", "openai/gpt-4o-mini"),
        ]
    if provider_id == "anthropic":
        return [
            ("claude-sonnet-4-20250514", "claude-sonnet-4-20250514"),
            ("claude-3-5-haiku-20241022", "claude-3-5-haiku-20241022"),
        ]
    if provider_id == "gemini":
        return [
            ("models/gemini-2.5-flash", "models/gemini-2.5-flash"),
        ]
    if provider_id == "ollama":
        return [("qwen2.5-coder:latest", "qwen2.5-coder:latest")]
    return []


def _empty_tabs(provider_ids: tuple[str, ...]) -> list[ProviderTab]:
    ids = list(provider_ids) or ["openrouter"]
    return [ProviderTab(provider_id=pid.strip().lower(), models=()) for pid in ids if pid.strip()]


def _model_option_label(model_id: str, description: str | None) -> str:
    if description and description != model_id:
        return f"{description} ({model_id})"
    return description or model_id


def _model_options_for_tab(tab: ProviderTab) -> list[tuple[str, str]]:
    """(value, description) pairs for the model step."""
    if tab.models:
        return [
            (routed_model_id(model), model.display_name or model.id)
            for model in tab.models
        ]
    return _suggested_models_for_provider(tab.provider_id)


def _select_provider_model_numeric(
    label: str,
    tabs: list[ProviderTab],
    *,
    skip_label: str,
) -> str | None:
    print_step(label)
    print(f"  0. {skip_label}")
    provider_options = [(tab.provider_id, tab.provider_id) for tab in tabs]
    for index, (provider_id, _) in enumerate(provider_options, start=1):
        tab = next(t for t in tabs if t.provider_id == provider_id)
        suffix = f" ({len(tab.models)} models)" if tab.models else ""
        print(f"  {index}. Provider: {provider_id}{suffix}")

    while True:
        raw = input("Choose provider number (0 to skip): ").strip()
        if raw == "0":
            return None
        if not raw.isdigit():
            print("  Enter 0 to skip or a provider number.")
            continue
        choice = int(raw)
        if not 1 <= choice <= len(provider_options):
            print("  That number is not on the list.")
            continue
        provider_id = provider_options[choice - 1][0]
        tab = next(t for t in tabs if t.provider_id == provider_id)
        models = list(tab.models)
        if not models:
            suggestions = _suggested_models_for_provider(provider_id)
            if suggestions:
                print_step(f"Models for {provider_id}")
                print(f"  0. {skip_label}")
                for m_index, (model_id, desc) in enumerate(suggestions, start=1):
                    print(f"  {m_index}. {desc}")
                custom_index = len(suggestions) + 1
                print(f"  {custom_index}. Custom Model ID:")
                while True:
                    raw_model = input("Choose a number: ").strip()
                    if raw_model == "0":
                        return None
                    if raw_model.isdigit():
                        m_choice = int(raw_model)
                        if 1 <= m_choice <= len(suggestions):
                            return suggestions[m_choice - 1][0]
                        if m_choice == custom_index:
                            custom = prompt_text("Model id")
                            return custom or None
                    print("  Enter 0 to skip, a list number, or the custom option number.")
            custom = prompt_text(f"Model id for {provider_id}")
            return custom or None

        print_step(f"Models for {provider_id}")
        print(f"  0. {skip_label}")
        for m_index, model in enumerate(models, start=1):
            line = f"  {m_index}. {model.display_name or model.id}"
            if model.display_name and model.display_name != model.id:
                line += _dim(f"  ({model.id})")
            print(line)
        custom_index = len(models) + 1
        print(f"  {custom_index}. Custom Model ID:")
        while True:
            raw_model = input("Choose a number: ").strip()
            if raw_model == "0":
                return None
            if raw_model.isdigit():
                m_choice = int(raw_model)
                if 1 <= m_choice <= len(models):
                    return routed_model_id(models[m_choice - 1])
                if m_choice == custom_index:
                    custom = prompt_text("Model id")
                    return custom or None
            print("  Enter 0 to skip, a list number, or the custom option number.")


def _select_provider_model_questionary(
    label: str,
    tabs: list[ProviderTab],
    *,
    skip_label: str,
) -> str | None:
    if not tabs:
        return None

    provider_choices: list[Choice] = [Choice(title=skip_label, value=_SKIP_SENTINEL)]
    for tab in tabs:
        suffix = f" ({len(tab.models)} models)" if tab.models else ""
        provider_choices.append(
            Choice(title=f"{tab.provider_id}{suffix}", value=tab.provider_id)
        )

    provider_result = questionary.select(
        label,
        choices=provider_choices,
        style=_STYLE,
        use_arrow_keys=True,
        use_jk_keys=True,
        use_search_filter=len(provider_choices) > 12,
        instruction="↑/↓ navigate · enter select",
    ).ask()
    if provider_result is None:
        raise KeyboardInterrupt()
    if provider_result == _SKIP_SENTINEL:
        return None

    tab = next(t for t in tabs if t.provider_id == provider_result)
    options = _model_options_for_tab(tab)

    model_choices: list[Choice] = [Choice(title=skip_label, value=_SKIP_SENTINEL)]
    model_choices.extend(
        Choice(title=_model_option_label(value, description), value=value)
        for value, description in options
    )
    model_choices.append(Choice(title="Custom Model ID:", value=_CUSTOM_SENTINEL))

    searchable = len(options) > 8
    model_result = questionary.select(
        f"Model for {tab.provider_id}",
        choices=model_choices,
        style=_STYLE,
        use_arrow_keys=True,
        use_jk_keys=not searchable,
        use_search_filter=searchable,
        instruction=(
            "type to filter · ↑/↓ navigate · enter select"
            if searchable
            else "↑/↓ navigate · enter select"
        ),
    ).ask()
    if model_result is None:
        raise KeyboardInterrupt()
    if model_result == _SKIP_SENTINEL:
        return None
    if model_result == _CUSTOM_SENTINEL:
        custom = prompt_text("Model id")
        return custom or None
    return str(model_result)


def select_provider_model_optional(
    label: str,
    catalog: dict[str, list[ProviderModel]],
    provider_ids: tuple[str, ...],
    *,
    skip_label: str = "Skip (keep agent default)",
) -> str | None:
    tabs = build_provider_tabs(catalog, provider_ids)
    if not tabs:
        tabs = _empty_tabs(provider_ids)

    if not _interactive_available():
        return _select_provider_model_numeric(label, tabs, skip_label=skip_label)

    return _select_provider_model_questionary(label, tabs, skip_label=skip_label)
