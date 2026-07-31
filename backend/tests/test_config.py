from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_config, read_env_bool, resolve_database_url


def test_resolve_database_url_relative_to_config_dir(tmp_path: Path) -> None:
    config_dir = tmp_path / "repo"
    config_dir.mkdir()

    resolved = resolve_database_url(
        "sqlite:///./data/modelport.db",
        config_dir=config_dir,
    )

    assert resolved == f"sqlite:///{(config_dir / 'data' / 'modelport.db').resolve().as_posix()}"


def test_load_config_resolves_sqlite_path_against_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        'database:\n  url: "sqlite:///./data/modelport.db"\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    expected = (tmp_path / "data" / "modelport.db").resolve().as_posix()
    assert config.database.url == f"sqlite:///{expected}"


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_read_env_bool_accepts_true_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("FEATURE_ENABLED", value)

    assert read_env_bool("FEATURE_ENABLED", default=False) is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_read_env_bool_accepts_false_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("FEATURE_ENABLED", value)

    assert read_env_bool("FEATURE_ENABLED", default=True) is False


def test_read_env_bool_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_ENABLED", "sometimes")

    with pytest.raises(ValueError, match="FEATURE_ENABLED"):
        read_env_bool("FEATURE_ENABLED", default=True)
