import pytest

from modelport_agent_config import prompts


@pytest.fixture(autouse=True)
def _force_interactive_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "_interactive_available", lambda: True)


def test_select_option_returns_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuestion:
        def ask(self) -> str:
            return "project"

    monkeypatch.setattr(
        prompts.questionary,
        "select",
        lambda *args, **kwargs: FakeQuestion(),
    )
    result = prompts.select_option(
        "Settings scope",
        [
            ("global", "User-wide"),
            ("project", "Project"),
        ],
    )
    assert result == "project"


def test_select_option_custom_value(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuestion:
        def ask(self) -> str:
            return prompts._CUSTOM

    monkeypatch.setattr(
        prompts.questionary,
        "select",
        lambda *args, **kwargs: FakeQuestion(),
    )
    monkeypatch.setattr(prompts, "prompt_text", lambda *_args, **_kwargs: "custom-provider")
    result = prompts.select_option(
        "Provider",
        [("openrouter", "OpenRouter")],
        allow_custom=True,
    )
    assert result == "custom-provider"


def test_select_optional_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuestion:
        def ask(self) -> str:
            return prompts._SKIP

    monkeypatch.setattr(
        prompts.questionary,
        "select",
        lambda *args, **kwargs: FakeQuestion(),
    )
    result = prompts.select_optional(
        "Default model",
        [("anthropic/claude-sonnet-4", "Claude Sonnet 4")],
    )
    assert result is None


def test_select_option_cancelled_raises_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuestion:
        def ask(self) -> None:
            return None

    monkeypatch.setattr(
        prompts.questionary,
        "select",
        lambda *args, **kwargs: FakeQuestion(),
    )
    with pytest.raises(KeyboardInterrupt):
        prompts.select_option("Settings scope", [("global", "User-wide")])


def test_select_kwargs_disables_jk_when_searchable() -> None:
    kwargs = prompts._select_kwargs(item_count=15)
    assert kwargs["use_search_filter"] is True
    assert kwargs["use_jk_keys"] is False


def test_select_kwargs_allows_jk_for_short_lists() -> None:
    kwargs = prompts._select_kwargs(item_count=5)
    assert kwargs["use_search_filter"] is False
    assert kwargs["use_jk_keys"] is True


def test_select_option_numeric_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "_interactive_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")
    result = prompts.select_option(
        "Settings scope",
        [
            ("global", "User-wide"),
            ("project", "Project"),
        ],
    )
    assert result == "project"


def test_prompt_yes_no_requires_explicit_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter(["", "maybe", "n"])
    monkeypatch.setattr(prompts, "_interactive_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    assert prompts.prompt_yes_no("Continue?") is False


def test_prompt_yes_no_accepts_yes_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "_interactive_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    assert prompts.prompt_yes_no("Continue?") is True


def test_prompt_yes_no_uses_text_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuestion:
        def ask(self) -> str:
            return "n"

    monkeypatch.setattr(
        prompts.questionary,
        "text",
        lambda *args, **kwargs: FakeQuestion(),
    )
    assert prompts.prompt_yes_no("Continue?") is False
