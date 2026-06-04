from __future__ import annotations

import re
from dataclasses import dataclass

from modelport_agent_config.modelport import ProviderModel

# Model ids containing any of these fragments are never offered to coding agents.
_ID_EXCLUDE_FRAGMENTS: tuple[str, ...] = (
    "embed",
    "embedding",
    "tts",
    "imagen",
    "veo/",
    "veo-",
    "native-audio",
    "live-preview",
    "/aqa",
    "flash-image",
    "pro-image",
    "image-preview",
    "preview-tts",
    "gemini-2.0",  # empty metadata + unreliable via OpenAI-compat path
)

# Mainstream chat families when upstream metadata is missing.
_EMPTY_METADATA_ALLOW_RE = re.compile(
    r"(claude|gpt[-/]|openai/|anthropic/|o[134](?:-mini)?|llama|qwen|mistral|deepseek|command)",
    re.IGNORECASE,
)

_GEMINI_CHAT_RE = re.compile(r"gemini-(?:2\.[5-9]|[3-9])", re.IGNORECASE)


@dataclass(frozen=True)
class ChatModelFilterResult:
    included: tuple[ProviderModel, ...]
    excluded_count: int


def _normalized(values: tuple[str, ...]) -> list[str]:
    return [value.strip().lower() for value in values if value.strip()]


def _id_is_excluded(model_id: str) -> bool:
    lower = model_id.lower()
    return any(fragment in lower for fragment in _ID_EXCLUDE_FRAGMENTS)


def _output_modalities_allow_chat(outputs: list[str]) -> bool | None:
    """True = chat-capable, False = not, None = no signal."""
    if not outputs:
        return None
    if any(value in {"embeddings", "embedding"} for value in outputs):
        return False
    if "speech" in outputs and "text" not in outputs:
        return False
    if "image" in outputs and "text" not in outputs:
        return False
    return "text" in outputs


def is_agent_chat_model(model: ProviderModel, *, agent_id: str = "claude-code") -> bool:
    """Whether a catalog model is suitable as a Claude Code / coding-agent default."""
    if agent_id != "claude-code":
        # Future agents can add their own rules; default to the same chat filter for now.
        pass

    if _id_is_excluded(model.id):
        return False

    outputs = _normalized(model.output_modalities)
    output_verdict = _output_modalities_allow_chat(outputs)
    if output_verdict is False:
        return False
    if output_verdict is True:
        return True

    architecture = (model.architecture_modality or "").lower()
    if "->text" in architecture and "embed" not in architecture:
        return True

    inputs = _normalized(model.input_modalities)
    if inputs and "text" in inputs and not outputs:
        # Text-in models without explicit output metadata (unusual); keep if not blocklisted.
        return True

    if not inputs and not outputs and not architecture:
        lower = model.id.lower()
        if _GEMINI_CHAT_RE.search(lower):
            return True
        if _EMPTY_METADATA_ALLOW_RE.search(lower):
            return True
        return False

    return False


def filter_chat_models(
    models: list[ProviderModel],
    *,
    agent_id: str = "claude-code",
) -> ChatModelFilterResult:
    included = [model for model in models if is_agent_chat_model(model, agent_id=agent_id)]
    return ChatModelFilterResult(
        included=tuple(included),
        excluded_count=max(0, len(models) - len(included)),
    )


def filter_catalog_for_agent(
    catalog: dict[str, list[ProviderModel]],
    *,
    agent_id: str = "claude-code",
) -> tuple[dict[str, list[ProviderModel]], int]:
    filtered: dict[str, list[ProviderModel]] = {}
    total_excluded = 0
    for provider_id, models in catalog.items():
        result = filter_chat_models(models, agent_id=agent_id)
        if result.included:
            filtered[provider_id] = list(result.included)
        total_excluded += result.excluded_count
    return filtered, total_excluded
