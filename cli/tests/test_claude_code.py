from pathlib import Path

from modelport_agent_config.agents.claude_code import ClaudeCodeAdapter, merge_settings, strip_modelport_env
from modelport_agent_config.agents.base import ConfigScope
from modelport_agent_config.modelport import ModelPortProfile


def test_merge_settings_preserves_unrelated_keys():
    existing = {"permissions": {"allow": ["Bash(ls)"]}, "env": {"FOO": "bar"}}
    patch = {"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:13243"}, "model": "gpt-test"}
    merged = merge_settings(existing, patch)
    assert merged["permissions"] == existing["permissions"]
    assert merged["env"]["FOO"] == "bar"
    assert merged["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:13243"
    assert merged["model"] == "gpt-test"


def test_strip_modelport_env():
    env = {
        "ANTHROPIC_BASE_URL": "http://old",
        "MY_FLAG": "1",
    }
    cleaned = strip_modelport_env(env)
    assert cleaned == {"MY_FLAG": "1"}


def test_apply_writes_settings(tmp_path: Path):
    adapter = ClaudeCodeAdapter()
    profile = ModelPortProfile(
        base_url="http://127.0.0.1:13243",
        token="test-token",
        provider_id="openrouter",
        model="anthropic/claude-sonnet-4",
    )
    result = adapter.apply(profile, ConfigScope.PROJECT, tmp_path)
    assert result.settings_path == tmp_path / ".claude" / "settings.json"
    payload = result.settings_path.read_text(encoding="utf-8")
    assert "ANTHROPIC_BASE_URL" in payload
    assert "X-ModelPort-Provider: openrouter" in payload
    assert "anthropic/claude-sonnet-4" in payload
