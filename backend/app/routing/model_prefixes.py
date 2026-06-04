from __future__ import annotations

from dataclasses import dataclass

from app.model_metadata_service import OPENROUTER_VENDOR_BY_PROVIDER

# OpenRouter upstream model ids use vendor prefixes; "openrouter" is also a vendor namespace.
OPENROUTER_VENDOR_PREFIXES: frozenset[str] = frozenset(
    vendor for vendor in OPENROUTER_VENDOR_BY_PROVIDER.values() if vendor
) | {"openrouter"}


@dataclass(frozen=True, slots=True)
class ResolvedModelSelection:
    provider_id: str
    upstream_model: str


def _split_model_segments(model_id: str) -> list[str]:
    return [segment for segment in model_id.strip().split("/") if segment]


def normalize_upstream_for_provider(
    provider_id: str,
    requested_model: str,
    known_provider_ids: set[str],
) -> str:
    """Strip a leading ModelPort provider prefix when present."""
    _ = known_provider_ids
    segments = _split_model_segments(requested_model)
    if not segments:
        return requested_model.strip()

    provider = provider_id.strip().lower()
    if segments[0].lower() != provider:
        return requested_model.strip()

    if provider == "openrouter":
        if len(segments) >= 3:
            return "/".join(segments[1:])
        if len(segments) == 2:
            # OpenRouter-owned models such as openrouter/auto stay intact.
            return requested_model.strip()
        return requested_model.strip()

    if len(segments) == 1:
        return requested_model.strip()
    return "/".join(segments[1:])


def infer_provider_from_model(
    requested_model: str,
    known_provider_ids: set[str],
) -> ResolvedModelSelection | None:
    """Infer provider and upstream model when header/body provider is omitted."""
    model_id = requested_model.strip()
    if not model_id:
        return None

    segments = _split_model_segments(model_id)
    if not segments:
        return None

    first = segments[0].lower()
    known = {provider_id.strip().lower() for provider_id in known_provider_ids}

    if first in known:
        if first == "openrouter":
            if len(segments) >= 3:
                upstream_model = "/".join(segments[1:])
            else:
                upstream_model = model_id
            return ResolvedModelSelection(provider_id="openrouter", upstream_model=upstream_model)

        upstream_model = "/".join(segments[1:]) if len(segments) > 1 else model_id
        return ResolvedModelSelection(provider_id=first, upstream_model=upstream_model)

    if model_id.startswith("models/") and "gemini" in known:
        return ResolvedModelSelection(provider_id="gemini", upstream_model=model_id)

    if first in OPENROUTER_VENDOR_PREFIXES and "openrouter" in known:
        return ResolvedModelSelection(provider_id="openrouter", upstream_model=model_id)

    # OpenRouter hosts many vendor/model ids; unknown vendors still use vendor/model shape.
    if len(segments) >= 2 and "openrouter" in known:
        return ResolvedModelSelection(provider_id="openrouter", upstream_model=model_id)

    return None


__all__ = [
    "OPENROUTER_VENDOR_PREFIXES",
    "ResolvedModelSelection",
    "infer_provider_from_model",
    "normalize_upstream_for_provider",
]
