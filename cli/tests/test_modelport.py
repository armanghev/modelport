from pathlib import Path

import pytest

from modelport_agent_config import main as main_module
from modelport_agent_config.modelport import (
    ModelPortRuntime,
    ServerConfig,
    load_dotenv_values,
    resolve_token,
    resolve_token_with_source,
)


def _runtime(env_path: Path | None = None) -> ModelPortRuntime:
    return ModelPortRuntime(
        repo_root=Path("/tmp/modelport"),
        config_path=Path("/tmp/modelport/config.yaml"),
        env_path=env_path,
        server=ServerConfig(host="127.0.0.1", port=13243),
        token_env="MODELPORT_TOKEN",
        provider_ids=("openrouter",),
    )


def test_resolve_token_prefers_cli_override() -> None:
    runtime = _runtime()
    resolved = resolve_token_with_source(runtime, "from-flag")
    assert resolved is not None
    assert resolved.token == "from-flag"
    assert resolved.source == "command-line --token"


def test_resolve_token_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _runtime()
    monkeypatch.setenv("MODELPORT_TOKEN", "from-env")
    resolved = resolve_token_with_source(runtime)
    assert resolved is not None
    assert resolved.token == "from-env"
    assert "environment variable MODELPORT_TOKEN" in resolved.source


def test_resolve_token_reads_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text('MODELPORT_TOKEN="from-dotenv"\n', encoding="utf-8")
    runtime = _runtime(env_path=env_path)
    monkeypatch.delenv("MODELPORT_TOKEN", raising=False)
    resolved = resolve_token_with_source(runtime)
    assert resolved is not None
    assert resolved.token == "from-dotenv"
    assert resolved.source == str(env_path)


def test_resolve_token_cli_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _runtime()
    monkeypatch.setenv("MODELPORT_TOKEN", "from-env")
    assert resolve_token(runtime, "from-flag") == "from-flag"


def test_load_dotenv_values_ignores_comments_and_export_prefix(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text('\nexport MODELPORT_TOKEN="abc"\n# comment\nUNUSED=1\n', encoding="utf-8")
    values = load_dotenv_values(env_path)
    assert values["MODELPORT_TOKEN"] == "abc"
    assert "UNUSED" not in values or values["UNUSED"] == "1"


def test_main_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(main_module, "select_option", _interrupt)
    assert main_module.main([]) == 130
    assert "Cancelled." in capsys.readouterr().err
