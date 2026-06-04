from __future__ import annotations

from dataclasses import dataclass

from modelport_agent_config.modelport import ProviderModel
from modelport_agent_config.prompts import _dim, _interactive_available, print_step, prompt_text

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


def routed_model_id(provider_id: str, model: ProviderModel) -> str:
    """Return the model id stored for Claude Code; backend infers provider from it."""
    _ = provider_id
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
                    return routed_model_id(provider_id, models[m_choice - 1])
                if m_choice == custom_index:
                    custom = prompt_text("Model id")
                    return custom or None
            print("  Enter 0 to skip, a list number, or the custom option number.")


# Model rows shown between scroll hints (not counting hint lines themselves).
MODEL_PAGE_SIZE = 6
# Start scrolling before the cursor reaches the last visible row.
SCROLL_MARGIN = 2


def _list_window_height() -> int:
    """Total list window rows: model page plus room for ↑/↓ hints."""
    return MODEL_PAGE_SIZE + 2


def _select_provider_model_interactive(
    label: str,
    tabs: list[ProviderTab],
    *,
    skip_label: str,
) -> str | None:
    from prompt_toolkit.application import Application
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Dimension, HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style as PtStyle

    if not tabs:
        return None

    provider_index = 0
    list_index = 0
    list_scroll_offset = 0
    search_query = ""
    custom_model_input = ""
    page_size = MODEL_PAGE_SIZE

    def is_on_custom_row() -> bool:
        items = menu_items()
        if not items or list_index < 0 or list_index >= len(items):
            return False
        return items[list_index][0] == _CUSTOM_SENTINEL

    def current_tab() -> ProviderTab:
        return tabs[provider_index]

    def menu_items() -> list[tuple[str, str]]:
        """(sentinel_or_model_id, display_line)"""
        items: list[tuple[str, str]] = [(_SKIP_SENTINEL, skip_label)]
        tab = current_tab()
        models = filter_models_for_provider(tab.models, query=search_query)
        if not models:
            for model_id, desc in _suggested_models_for_provider(tab.provider_id):
                items.append((model_id, desc))
        else:
            for model in models:
                label_text = model.display_name or model.id
                if model.display_name and model.display_name != model.id:
                    label_text = f"{label_text} ({model.id})"
                items.append((model.id, label_text))
        items.append((_CUSTOM_SENTINEL, "Custom Model ID:"))
        return items

    def clamp_list_index() -> None:
        nonlocal list_index
        count = len(menu_items())
        if list_index >= count:
            list_index = max(0, count - 1)

    def ensure_list_visible() -> None:
        nonlocal list_scroll_offset
        if list_index < list_scroll_offset:
            list_scroll_offset = max(0, list_index - SCROLL_MARGIN)
        elif list_index >= list_scroll_offset + page_size - SCROLL_MARGIN:
            list_scroll_offset = list_index - page_size + SCROLL_MARGIN + 1
        total = len(menu_items())
        max_offset = max(0, total - page_size)
        if list_scroll_offset > max_offset:
            list_scroll_offset = max_offset

    def reset_list_view() -> None:
        nonlocal list_index, list_scroll_offset
        list_index = 0
        list_scroll_offset = 0

    def reset_provider_view() -> None:
        nonlocal search_query, custom_model_input
        search_query = ""
        custom_model_input = ""
        reset_list_view()

    def render_header() -> FormattedText:
        lines: list[tuple[str, str]] = []
        lines.append(("class:title", f"{label}\n\n"))

        tab_line: list[tuple[str, str]] = []
        for index, tab in enumerate(tabs):
            name = tab.provider_id
            count = len(tab.models)
            label_text = f" {name} ({count}) " if count else f" {name} "
            if index == provider_index:
                tab_line.append(("class:tab.active", label_text))
            else:
                tab_line.append(("class:tab", label_text))
            if index < len(tabs) - 1:
                tab_line.append(("", " "))
        lines.extend(tab_line)
        lines.append(("", "\n"))

        if is_on_custom_row():
            lines.append(("class:instruction", "Type your model id below · Enter confirm\n"))
            lines.append(
                (
                    "class:instruction",
                    "←/→ switch provider · ↑/↓ navigate · Esc cancel\n",
                )
            )
        elif search_query:
            lines.append(("class:instruction", f"Search: {search_query}\n"))
            lines.append(
                (
                    "class:instruction",
                    "←/→ or Tab switch provider · ↑/↓ navigate · Enter select · Esc cancel\n",
                )
            )
        else:
            lines.append(("class:instruction", "Type to search models in this provider\n"))
            lines.append(
                (
                    "class:instruction",
                    "←/→ or Tab switch provider · ↑/↓ navigate · Enter select · Esc cancel\n",
                )
            )
        return FormattedText(lines)

    def render_list() -> FormattedText:
        items = menu_items()
        total = len(items)
        lines: list[tuple[str, str]] = []

        if total > page_size:
            if list_scroll_offset > 0:
                lines.append(("class:instruction", f"  ↑ {list_scroll_offset} more above\n"))
            else:
                lines.append(("", "\n"))

        end = min(total, list_scroll_offset + page_size)
        for index in range(list_scroll_offset, end):
            value, display = items[index]
            selected = index == list_index
            prefix = "› " if selected else "  "
            style = "class:highlighted" if selected else ""
            if value == _CUSTOM_SENTINEL and selected:
                cursor = "▏" if custom_model_input else "_"
                typed = custom_model_input or ""
                lines.append((style, f"{prefix}Custom Model ID: {typed}{cursor}\n"))
            else:
                lines.append((style, f"{prefix}{display}\n"))

        remaining = total - end
        if remaining > 0:
            lines.append(("class:instruction", f"  ↓ {remaining} more below\n"))

        return FormattedText(lines)

    result: dict[str, str | None] = {"value": None}

    kb = KeyBindings()

    @kb.add("tab")
    @kb.add("right")
    def _next_provider(event) -> None:
        nonlocal provider_index
        provider_index = (provider_index + 1) % len(tabs)
        reset_provider_view()
        event.app.invalidate()

    @kb.add("s-tab")
    @kb.add("left")
    def _prev_provider(event) -> None:
        nonlocal provider_index
        provider_index = (provider_index - 1) % len(tabs)
        reset_provider_view()
        event.app.invalidate()

    @kb.add("up")
    def _up(event) -> None:
        nonlocal list_index
        list_index = max(0, list_index - 1)
        ensure_list_visible()
        event.app.invalidate()

    @kb.add("down")
    def _down(event) -> None:
        nonlocal list_index
        list_index = min(len(menu_items()) - 1, list_index + 1)
        ensure_list_visible()
        event.app.invalidate()

    @kb.add("enter")
    def _enter(event) -> None:
        items = menu_items()
        if not items:
            return
        value, _display = items[list_index]
        if value == _SKIP_SENTINEL:
            result["value"] = None
            event.app.exit()
            return
        if value == _CUSTOM_SENTINEL:
            trimmed = custom_model_input.strip()
            if trimmed:
                result["value"] = trimmed
                event.app.exit()
            return
        tab = current_tab()
        models = filter_models_for_provider(tab.models, query=search_query)
        if models:
            for model in models:
                if model.id == value:
                    result["value"] = routed_model_id(tab.provider_id, model)
                    event.app.exit()
                    return
        result["value"] = value
        event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event) -> None:
        raise KeyboardInterrupt()

    @kb.add("backspace")
    def _backspace(event) -> None:
        nonlocal search_query, custom_model_input
        if is_on_custom_row():
            if custom_model_input:
                custom_model_input = custom_model_input[:-1]
                event.app.invalidate()
            return
        if search_query:
            search_query = search_query[:-1]
            reset_list_view()
            clamp_list_index()
            event.app.invalidate()

    @kb.add(" ")
    def _space(event) -> None:
        nonlocal search_query, custom_model_input
        if is_on_custom_row():
            custom_model_input += " "
            event.app.invalidate()
            return
        search_query += " "
        reset_list_view()
        clamp_list_index()
        event.app.invalidate()

    @kb.add("<any>")
    def _type_char(event) -> None:
        nonlocal search_query, custom_model_input
        if not (event.data and len(event.data) == 1 and event.data.isprintable()):
            return
        if event.data.isspace():
            return
        if is_on_custom_row():
            custom_model_input += event.data
            event.app.invalidate()
            return
        search_query += event.data
        reset_list_view()
        clamp_list_index()
        event.app.invalidate()

    header_window = Window(
        content=FormattedTextControl(lambda: render_header()),
        always_hide_cursor=True,
        dont_extend_height=True,
    )
    list_window = Window(
        content=FormattedTextControl(lambda: render_list()),
        always_hide_cursor=True,
        height=Dimension(max=_list_window_height(), preferred=_list_window_height()),
        dont_extend_height=True,
    )
    app = Application(
        layout=Layout(HSplit([header_window, list_window])),
        key_bindings=kb,
        full_screen=False,
        style=PtStyle.from_dict(
            {
                "title": "bold",
                "tab": "",
                "tab.active": "bold reverse",
                "instruction": "fg:ansibrightblack",
                "highlighted": "bold fg:ansicyan",
            }
        ),
    )
    app.run()
    return result["value"]


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

    try:
        return _select_provider_model_interactive(label, tabs, skip_label=skip_label)
    except ImportError:
        return _select_provider_model_numeric(label, tabs, skip_label=skip_label)
