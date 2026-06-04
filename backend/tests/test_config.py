from __future__ import annotations

from pathlib import Path

from app.config import load_config, resolve_database_url


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
