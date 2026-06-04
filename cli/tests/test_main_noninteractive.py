import argparse
from pathlib import Path

import pytest

from modelport_agent_config import main as main_module
from modelport_agent_config.modelport import ModelPortRuntime, ServerConfig


def _runtime() -> ModelPortRuntime:
    return ModelPortRuntime(
        repo_root=Path("/tmp/modelport"),
        config_path=Path("/tmp/modelport/config.yaml"),
        env_path=None,
        server=ServerConfig(host="127.0.0.1", port=13243),
        token_env="MODELPORT_TOKEN",
        provider_ids=("openrouter", "gemini"),
    )


def test_collect_profile_from_args_does_not_require_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELPORT_TOKEN", "tok")
    args = argparse.Namespace(
        base_url="http://127.0.0.1:13243",
        token=None,
        provider=None,
        scope=None,
        model="models/gemini-2.5-flash",
        sonnet_model=None,
        opus_model=None,
        haiku_model=None,
        disable_tool_search=False,
    )
    profile, _scope = main_module.collect_profile_from_args(args, _runtime())
    assert profile.model == "models/gemini-2.5-flash"
    assert profile.provider_id is None
