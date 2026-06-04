from __future__ import annotations

from app.routing.model_prefixes import (
    infer_provider_from_model,
    normalize_upstream_for_provider,
)

KNOWN = {"openai", "anthropic", "gemini", "openrouter", "ollama"}


def test_infer_openrouter_vendor_prefixed_model() -> None:
    selection = infer_provider_from_model("google/gemini-2.5-flash", KNOWN)
    assert selection is not None
    assert selection.provider_id == "openrouter"
    assert selection.upstream_model == "google/gemini-2.5-flash"


def test_infer_openrouter_owned_model_without_double_prefix() -> None:
    selection = infer_provider_from_model("openrouter/auto", KNOWN)
    assert selection is not None
    assert selection.provider_id == "openrouter"
    assert selection.upstream_model == "openrouter/auto"


def test_infer_openrouter_provider_prefixed_vendor_model() -> None:
    selection = infer_provider_from_model("openrouter/google/gemini-2.5-flash", KNOWN)
    assert selection is not None
    assert selection.provider_id == "openrouter"
    assert selection.upstream_model == "google/gemini-2.5-flash"


def test_infer_gemini_models_prefix() -> None:
    selection = infer_provider_from_model("models/gemini-2.5-flash", KNOWN)
    assert selection is not None
    assert selection.provider_id == "gemini"
    assert selection.upstream_model == "models/gemini-2.5-flash"


def test_infer_gemini_provider_prefixed_model() -> None:
    selection = infer_provider_from_model("gemini/models/gemini-2.5-flash", KNOWN)
    assert selection is not None
    assert selection.provider_id == "gemini"
    assert selection.upstream_model == "models/gemini-2.5-flash"


def test_infer_direct_provider_prefix_prefers_configured_provider() -> None:
    selection = infer_provider_from_model("openai/gpt-4.1", KNOWN)
    assert selection is not None
    assert selection.provider_id == "openai"
    assert selection.upstream_model == "gpt-4.1"


def test_infer_bare_model_returns_none() -> None:
    assert infer_provider_from_model("gpt-4.1", KNOWN) is None


def test_infer_unknown_openrouter_vendor_prefix() -> None:
    selection = infer_provider_from_model("nvidia/nemotron-3.5-content-safety:free", KNOWN)
    assert selection is not None
    assert selection.provider_id == "openrouter"
    assert selection.upstream_model == "nvidia/nemotron-3.5-content-safety:free"


def test_normalize_openrouter_owned_model_keeps_prefix() -> None:
    assert (
        normalize_upstream_for_provider("openrouter", "openrouter/auto", KNOWN)
        == "openrouter/auto"
    )


def test_normalize_openrouter_provider_prefixed_vendor_model() -> None:
    assert (
        normalize_upstream_for_provider(
            "openrouter",
            "openrouter/google/gemini-2.5-flash",
            KNOWN,
        )
        == "google/gemini-2.5-flash"
    )


def test_normalize_gemini_provider_prefixed_model() -> None:
    assert (
        normalize_upstream_for_provider(
            "gemini",
            "gemini/models/gemini-2.5-flash",
            KNOWN,
        )
        == "models/gemini-2.5-flash"
    )
