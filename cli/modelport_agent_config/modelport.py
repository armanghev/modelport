from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 13243
DEFAULT_TOKEN_ENV = "MODELPORT_TOKEN"
PROVIDER_HEADER = "X-ModelPort-Provider"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class ModelPortRuntime:
    repo_root: Path
    config_path: Path
    env_path: Path | None
    server: ServerConfig
    token_env: str
    provider_ids: tuple[str, ...]


@dataclass
class ModelPortProfile:
    """Values shared by every agent adapter."""

    base_url: str
    token: str
    provider_id: str
    model: str | None = None
    sonnet_model: str | None = None
    opus_model: str | None = None
    haiku_model: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    enable_tool_search: bool = True

    def routing_headers(self) -> dict[str, str]:
        headers = {PROVIDER_HEADER: self.provider_id}
        headers.update(self.extra_headers)
        return headers

    def format_custom_headers(self) -> str:
        lines = [f"{name}: {value}" for name, value in self.routing_headers().items()]
        return "\n".join(lines)

    def anthropic_tier_overrides(self) -> list[tuple[str, str]]:
        """Sonnet / Opus / Haiku overrides configured for Claude Code."""
        tiers: list[tuple[str, str]] = []
        if self.sonnet_model:
            tiers.append(("Sonnet", self.sonnet_model))
        if self.opus_model:
            tiers.append(("Opus", self.opus_model))
        if self.haiku_model:
            tiers.append(("Haiku", self.haiku_model))
        return tiers


@dataclass(frozen=True)
class ProviderModel:
    id: str
    display_name: str | None = None
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    supported_parameters: tuple[str, ...] = ()
    architecture_modality: str | None = None


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / "config.yaml").is_file() and (directory / "backend").is_dir():
            return directory
    return current


def load_dotenv_values(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def load_modelport_runtime(repo_root: Path | None = None) -> ModelPortRuntime:
    root = repo_root or find_repo_root()
    config_path = root / "config.yaml"
    raw: dict[str, Any] = {}
    if config_path.is_file():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = loaded

    server_raw = raw.get("server") if isinstance(raw.get("server"), dict) else {}
    security_raw = raw.get("security") if isinstance(raw.get("security"), dict) else {}
    providers_raw = raw.get("providers") if isinstance(raw.get("providers"), dict) else {}

    host = str(server_raw.get("host", DEFAULT_HOST))
    port = int(server_raw.get("port", DEFAULT_PORT))
    token_env = str(security_raw.get("modelport_token", DEFAULT_TOKEN_ENV))
    provider_ids = tuple(str(key) for key in providers_raw.keys())

    env_path = root / ".env"
    return ModelPortRuntime(
        repo_root=root,
        config_path=config_path,
        env_path=env_path if env_path.is_file() else None,
        server=ServerConfig(host=host, port=port),
        token_env=token_env,
        provider_ids=provider_ids,
    )


def default_base_url(runtime: ModelPortRuntime) -> str:
    host = runtime.server.host
    if host in {"0.0.0.0", "::"}:
        host = DEFAULT_HOST
    return f"http://{host}:{runtime.server.port}"


def resolve_token(runtime: ModelPortRuntime, override: str | None = None) -> str | None:
    if override:
        return override.strip() or None
    env_value = os.environ.get(runtime.token_env, "").strip()
    if env_value:
        return env_value
    if runtime.env_path:
        dotenv = load_dotenv_values(runtime.env_path)
        value = dotenv.get(runtime.token_env, "").strip()
        if value:
            return value
    return None


def normalize_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        raise ValueError("Base URL must start with http:// or https://")
    return url


def fetch_provider_models(base_url: str, timeout: float = 4.0) -> dict[str, list[ProviderModel]]:
    endpoint = f"{base_url.rstrip('/')}/admin/providers/models"
    request = Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {}

    providers = payload.get("providers")
    if not isinstance(providers, list):
        return {}

    catalog: dict[str, list[ProviderModel]] = {}
    for entry in providers:
        if not isinstance(entry, dict):
            continue
        provider_id = str(entry.get("provider_id", "")).strip().lower()
        if not provider_id:
            continue
        models_raw = entry.get("models")
        if not isinstance(models_raw, list):
            continue
        models: list[ProviderModel] = []
        for model in models_raw:
            if not isinstance(model, dict):
                continue
            model_id = str(model.get("id", "")).strip()
            if not model_id:
                continue
            display = model.get("display_name") or model.get("name")
            architecture = model.get("architecture")
            arch_modality = None
            if isinstance(architecture, dict):
                raw_modality = architecture.get("modality")
                if isinstance(raw_modality, str) and raw_modality.strip():
                    arch_modality = raw_modality.strip()

            def _tuple_field(key: str) -> tuple[str, ...]:
                raw = model.get(key)
                if not isinstance(raw, list):
                    return ()
                return tuple(str(item).strip() for item in raw if str(item).strip())

            models.append(
                ProviderModel(
                    id=model_id,
                    display_name=str(display).strip() if display else None,
                    input_modalities=_tuple_field("input_modalities"),
                    output_modalities=_tuple_field("output_modalities"),
                    supported_parameters=_tuple_field("supported_parameters"),
                    architecture_modality=arch_modality,
                )
            )
        if models:
            catalog[provider_id] = models
    return catalog


def probe_proxy(base_url: str, token: str, timeout: float = 4.0) -> tuple[bool, str]:
    endpoint = f"{base_url.rstrip('/')}/v1/models"
    request = Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-ModelPort-Provider": "openrouter",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return True, "Proxy accepted the token."
            return False, f"Unexpected status {response.status}."
    except HTTPError as exc:
        if exc.code == 401:
            return False, "Invalid MODELPORT_TOKEN (401)."
        return False, f"HTTP {exc.code}: {exc.reason}"
    except URLError as exc:
        return False, f"Could not reach proxy: {exc.reason}"
    except TimeoutError:
        return False, "Timed out connecting to the proxy."
