from modelport_agent_config.modelport import ModelPortProfile


def test_anthropic_tier_overrides_only_includes_set_values() -> None:
    profile = ModelPortProfile(
        base_url="http://127.0.0.1:13243",
        token="t",
        provider_id="gemini",
        sonnet_model="models/gemini-flash-latest",
        opus_model="models/gemini-3.1-pro-preview",
    )
    assert profile.anthropic_tier_overrides() == [
        ("Sonnet", "models/gemini-flash-latest"),
        ("Opus", "models/gemini-3.1-pro-preview"),
    ]


def test_anthropic_tier_overrides_empty_when_not_configured() -> None:
    profile = ModelPortProfile(
        base_url="http://127.0.0.1:13243",
        token="t",
        provider_id="openrouter",
    )
    assert profile.anthropic_tier_overrides() == []
