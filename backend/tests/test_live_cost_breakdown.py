from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.database import ApiRequest, PricingOverride, get_provider_by_slug
from app.pricing.rate_card import RateCard, TierRates
from app.routing.provider_router import ResolvedProviderRoute
from app.tracking.usage_service import UsageSnapshot


def test_log_tracked_proxy_request_writes_cache_breakdown(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
        assert provider is not None
        card = RateCard(
            standard=TierRates(
                input_per_1m=Decimal("3"),
                output_per_1m=Decimal("15"),
                cache_read_per_1m=Decimal("0.3"),
                cache_write_5m_per_1m=Decimal("3.75"),
            ),
            source="manual",
        )
        session.add(
            PricingOverride(
                provider_id=provider.id,
                model="claude-sonnet-4-6",
                input_per_1m_usd=3.0,
                output_per_1m_usd=15.0,
                rate_card_json=card.model_dump_json(),
                source="manual",
                enabled=True,
            )
        )
        session.commit()

        from app.api.proxy_common import log_tracked_proxy_request
        from app.routing.provider_router import select_provider_credential

        credential = select_provider_credential(provider)
        route = ResolvedProviderRoute(
            requested_model="claude-sonnet-4-6",
            upstream_model="claude-sonnet-4-6",
            provider=provider,
            credential=credential,
        )

        usage = UsageSnapshot(
            uncached_input_tokens=50,
            cache_read_tokens=9000,
            cache_write_5m_tokens=1000,
            cache_write_1h_tokens=0,
            output_tokens=300,
            total_tokens=10350,
            token_source="provider_reported",
        )

        log_tracked_proxy_request(
            session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name="test",
            resolved_route=route,
            requested_model="claude-sonnet-4-6",
            duration_ms=10,
            status_code=200,
            streamed=False,
            request_payload={"model": "claude-sonnet-4-6"},
            response_payload={"id": "msg_test"},
            usage_snapshot=usage,
        )

        record = session.scalars(select(ApiRequest).order_by(ApiRequest.created_at.desc())).first()

    assert record is not None
    assert record.uncached_input_tokens == 50
    assert record.cache_read_tokens == 9000
    assert record.cache_write_5m_tokens == 1000
    assert record.cost_input_usd == 0.00015
    assert record.cost_cache_read_usd == 0.0027
    assert record.cost_cache_write_usd == 0.00375
    assert record.cost_output_usd == 0.0045
    assert record.estimated_cost_usd == 0.0111
    assert record.pricing_source == "manual"
    assert record.context_tier == "standard"
