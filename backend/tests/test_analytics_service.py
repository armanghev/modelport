from __future__ import annotations

from app.analytics_service import normalize_client_name


def test_normalize_client_name_detects_claude_code_cli_user_agent() -> None:
    assert normalize_client_name("claude-cli/2.1.92 (external, cli)") == "Claude Code"
    assert normalize_client_name("claude-code/2.1.131 (cli)") == "Claude Code"
    assert normalize_client_name("Claude-Code/1.0") == "Claude Code"
