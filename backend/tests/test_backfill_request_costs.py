from __future__ import annotations

from sqlalchemy import select

from app.backfill_request_costs import backfill_request_costs
from app.database import ApiRequest

from tests.test_helpers import provider_uuid, seed_pricing


def test_backfill_request_costs_updates_existing_rows(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ApiRequest(
                input_format="anthropic",
                output_format="anthropic",
                endpoint="/v1/messages",
                client_name="curl/8.7.1",
                requested_model="gpt-4.1",
                resolved_model="gpt-4.1",
                provider="openai",
                input_tokens=1_000_000,
                output_tokens=500_000,
                total_tokens=1_500_000,
                token_source="provider_reported",
                estimated_cost_usd=None,
                pricing_source=None,
                duration_ms=100,
                status_code=200,
                streamed=False,
            )
        )
        session.commit()

    seed_pricing(
        client,
        provider_slug="openai",
        model="gpt-4.1",
        input_per_1m_usd=2.0,
        output_per_1m_usd=8.0,
    )

    summary = backfill_request_costs(session_factory)
    assert summary["updated"] >= 1

    with session_factory() as session:
        record = session.scalar(
            select(ApiRequest).where(
                ApiRequest.provider == "openai",
                ApiRequest.input_tokens == 1_000_000,
            )
        )
    assert record is not None
    assert record.estimated_cost_usd == 6.0
    assert record.pricing_source == "fixture"


def test_backfill_clears_stale_negative_estimated_cost(client) -> None:
    from app.database import PricingOverride

    openrouter_uuid = provider_uuid(client, "openrouter")
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        session.add(
            ApiRequest(
                input_format="openai",
                output_format="openai",
                endpoint="/v1/chat/completions",
                client_name="curl/8.7.1",
                requested_model="openrouter/auto",
                resolved_model="openrouter/auto",
                provider="openrouter",
                input_tokens=41,
                output_tokens=0,
                total_tokens=41,
                token_source="provider_reported",
                estimated_cost_usd=-41.0,
                pricing_source="admin_override",
                duration_ms=100,
                status_code=200,
                streamed=False,
            )
        )
        session.add(
            PricingOverride(
                provider_id=openrouter_uuid,
                model="openrouter/auto",
                input_per_1m_usd=-1_000_000.0,
                output_per_1m_usd=-1_000_000.0,
                currency="USD",
                enabled=True,
            )
        )
        session.commit()

    summary = backfill_request_costs(session_factory)
    assert summary["updated"] >= 1

    with session_factory() as session:
        record = session.scalar(
            select(ApiRequest).where(
                ApiRequest.provider == "openrouter",
                ApiRequest.requested_model == "openrouter/auto",
            )
        )
    assert record is not None
    assert record.estimated_cost_usd is None
    assert record.pricing_source is None
