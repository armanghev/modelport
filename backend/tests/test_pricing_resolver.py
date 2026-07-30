from __future__ import annotations

from decimal import Decimal

from app.database import PricingOverride, get_provider_by_slug
from app.pricing.rate_card import RateCard, TierRates
from app.pricing.resolver import model_lookup_candidates, resolve_rate_card


def _card(rate: str, source: str) -> str:
    return RateCard(
        standard=TierRates(input_per_1m=Decimal(rate), output_per_1m=Decimal(rate)),
        source=source,
    ).model_dump_json()


def _add_override(session, provider_id: str, model: str, rate: str, source: str) -> None:
    session.add(
        PricingOverride(
            provider_id=provider_id,
            model=model,
            input_per_1m_usd=float(rate),
            output_per_1m_usd=float(rate),
            rate_card_json=_card(rate, source),
            source=source,
            enabled=True,
        )
    )


def test_manual_source_wins_over_litellm(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
        _add_override(session, provider.id, "claude-sonnet-5", "3", "litellm")
        _add_override(session, provider.id, "claude-sonnet-5", "99", "manual")
        session.commit()

    with session_factory() as session:
        card = resolve_rate_card(
            session,
            provider_id="anthropic",
            resolved_model="claude-sonnet-5",
            requested_model="claude-sonnet-5",
        )

    assert card is not None
    assert card.source == "manual"
    assert card.standard.input_per_1m == Decimal("99")


def test_resolves_through_models_prefix_variant(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "gemini")
        _add_override(session, provider.id, "gemini-3.5-flash", "1.5", "litellm")
        session.commit()

    with session_factory() as session:
        card = resolve_rate_card(
            session,
            provider_id="gemini",
            resolved_model="models/gemini-3.5-flash",
            requested_model="models/gemini-3.5-flash",
        )

    assert card is not None
    assert card.standard.input_per_1m == Decimal("1.5")


def test_returns_none_when_no_card_matches(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        card = resolve_rate_card(
            session,
            provider_id="openai",
            resolved_model="model-that-does-not-exist",
            requested_model="model-that-does-not-exist",
        )

    assert card is None


def test_ollama_falls_back_to_the_wildcard_card(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "ollama")
        _add_override(session, provider.id, "*", "0", "local")
        session.commit()

    with session_factory() as session:
        card = resolve_rate_card(
            session,
            provider_id="ollama",
            resolved_model="llama4:latest",
            requested_model="llama4:latest",
        )

    assert card is not None
    assert card.standard.input_per_1m == Decimal("0")


def test_candidates_include_prefix_and_alias_variants() -> None:
    candidates = model_lookup_candidates("gemini", "models/gemini-3.5-flash", None)

    assert "models/gemini-3.5-flash" in candidates
    assert "gemini-3.5-flash" in candidates
