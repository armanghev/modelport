from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from modelport_agent_config.modelport import ModelPortProfile

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_SCHEMA = "https://json.schemastore.org/claude-code-settings.json"

MODELPORT_ENV_KEYS = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ENABLE_TOOL_SEARCH",
)

_TIER_SHELL_EXPORTS = (
    ("Sonnet", "sonnet_model", "ANTHROPIC_DEFAULT_SONNET_MODEL"),
    ("Opus", "opus_model", "ANTHROPIC_DEFAULT_OPUS_MODEL"),
    ("Haiku", "haiku_model", "ANTHROPIC_DEFAULT_HAIKU_MODEL"),
)


class ConfigScope(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    LOCAL = "local"


@dataclass(frozen=True)
class ApplyResult:
    settings_path: Path
    backup_path: Path | None
    keys_written: tuple[str, ...]


def merge_settings(existing: dict, patch: dict) -> dict:
    merged = dict(existing)
    if "env" in patch:
        env = dict(existing.get("env") or {})
        env.update(patch["env"])
        merged["env"] = env
    if "model" in patch:
        merged["model"] = patch["model"]
    if "$schema" not in merged and "$schema" in patch:
        merged["$schema"] = patch["$schema"]
    return merged


def strip_modelport_env(env: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in env.items() if key not in MODELPORT_ENV_KEYS}


class ClaudeCodeAdapter:
    id = "claude-code"
    display_name = "Claude Code"
    description = "Anthropic Claude Code CLI (~/.claude/settings.json)"

    def config_path(self, scope: ConfigScope, project_dir: Path) -> Path:
        if scope is ConfigScope.GLOBAL:
            return CLAUDE_DIR / "settings.json"
        if scope is ConfigScope.PROJECT:
            return project_dir / ".claude" / "settings.json"
        return project_dir / ".claude" / "settings.local.json"

    def detect_installed(self) -> bool:
        return CLAUDE_DIR.exists() or shutil.which("claude") is not None

    def load_settings(self, path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def build_settings_patch(self, profile: ModelPortProfile) -> dict:
        env: dict[str, str] = {
            "ANTHROPIC_BASE_URL": profile.base_url,
            "ANTHROPIC_AUTH_TOKEN": profile.token,
            "ENABLE_TOOL_SEARCH": "true" if profile.enable_tool_search else "false",
        }
        if profile.model:
            env["ANTHROPIC_MODEL"] = profile.model
        if profile.sonnet_model:
            env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = profile.sonnet_model
        if profile.opus_model:
            env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = profile.opus_model
        if profile.haiku_model:
            env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = profile.haiku_model

        patch: dict = {
            "$schema": SETTINGS_SCHEMA,
            "env": env,
        }
        if profile.model:
            patch["model"] = profile.model
        return patch

    def apply(self, profile: ModelPortProfile, scope: ConfigScope, project_dir: Path) -> ApplyResult:
        path = self.config_path(scope, project_dir)
        path.parent.mkdir(parents=True, exist_ok=True)

        backup_path: Path | None = None
        if path.is_file():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup_path = path.with_suffix(path.suffix + f".modelport-backup-{stamp}")
            shutil.copy2(path, backup_path)

        existing = self.load_settings(path)
        existing_env = existing.get("env") if isinstance(existing.get("env"), dict) else {}
        cleaned_env = strip_modelport_env({str(k): str(v) for k, v in existing_env.items()})
        cleaned = dict(existing)
        if cleaned_env:
            cleaned["env"] = cleaned_env
        elif "env" in cleaned:
            del cleaned["env"]

        patch = self.build_settings_patch(profile)
        merged = merge_settings(cleaned, patch)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")

        keys_written = tuple(patch.get("env", {}).keys())
        if "model" in patch:
            keys_written = (*keys_written, "model")
        return ApplyResult(settings_path=path, backup_path=backup_path, keys_written=keys_written)

    def print_post_apply_hints(self, profile: ModelPortProfile, result: ApplyResult) -> None:
        print(f"\nWrote ModelPort settings to {result.settings_path}")
        if result.backup_path:
            print(f"Previous file backed up to {result.backup_path}")
        print("\nRestart Claude Code so env changes take effect.")
        if profile.model:
            print(f"Default model: {profile.model}")
        for label, model_id in profile.anthropic_tier_overrides():
            print(f"{label} tier model: {model_id}")
        print("\nShell exports (optional, for terminals outside Claude Code):")
        print(f'  export ANTHROPIC_BASE_URL="{profile.base_url}"')
        print(f'  export ANTHROPIC_AUTH_TOKEN="{profile.token}"')
        if profile.model:
            print(f'  export ANTHROPIC_MODEL="{profile.model}"')
        for _label, attr, env_key in _TIER_SHELL_EXPORTS:
            value = getattr(profile, attr)
            if value:
                print(f'  export {env_key}="{value}"')
