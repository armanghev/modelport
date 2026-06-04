from __future__ import annotations

from app.analytics_service import model_display_name, normalize_client_name


def test_normalize_client_name_detects_claude_code_cli_user_agent() -> None:
    assert normalize_client_name("claude-cli/2.1.92 (external, cli)") == "Claude Code"
    assert normalize_client_name("claude-code/2.1.131 (cli)") == "Claude Code"
    assert normalize_client_name("Claude-Code/1.0") == "Claude Code"


def test_model_display_name_strips_redundant_provider_prefix() -> None:
    display_names = {
        "google/gemini-2.5-pro": "Google: Gemini 2.5 Pro",
    }

    assert model_display_name("gemini", "gemini-2.5-pro", display_names) == "Gemini 2.5 Pro"
