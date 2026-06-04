from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from modelport_agent_config.modelport import ModelPortProfile


class ConfigScope(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    LOCAL = "local"


@dataclass(frozen=True)
class ApplyResult:
    settings_path: Path
    backup_path: Path | None
    keys_written: tuple[str, ...]


class AgentAdapter(ABC):
    """Maps a ModelPort profile onto a specific CLI agent's config files."""

    id: str
    display_name: str
    description: str

    @abstractmethod
    def config_path(self, scope: ConfigScope, project_dir: Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def detect_installed(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load_settings(self, path: Path) -> dict:
        raise NotImplementedError

    @abstractmethod
    def build_settings_patch(self, profile: ModelPortProfile) -> dict:
        raise NotImplementedError

    @abstractmethod
    def apply(self, profile: ModelPortProfile, scope: ConfigScope, project_dir: Path) -> ApplyResult:
        raise NotImplementedError

    def print_post_apply_hints(self, profile: ModelPortProfile, result: ApplyResult) -> None:
        print(f"\nWrote ModelPort settings to {result.settings_path}")
        if result.backup_path:
            print(f"Previous file backed up to {result.backup_path}")
        print("\nRestart Claude Code so env changes take effect.")
        if profile.model:
            print(f"Default model: {profile.model}")
        for label, model_id in profile.anthropic_tier_overrides():
            print(f"{label} tier model: {model_id}")
