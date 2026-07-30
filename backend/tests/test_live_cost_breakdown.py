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


def test_log_tracked_proxy_request_uses_requested_service_tier(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
        assert provider is not None
        card = RateCard(
            standard=TierRates(input_per_1m=Decimal("3"), output_per_1m=Decimal("15")),
            service_tiers={
                "flex": TierRates(input_per_1m=Decimal("1"), output_per_1m=Decimal("5"))
            },
            source="manual",
        )
        session.add(
            PricingOverride(
                provider_id=provider.id,
                model="claude-flex",
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

        route = ResolvedProviderRoute(
            requested_model="claude-flex",
            upstream_model="claude-flex",
            provider=provider,
            credential=select_provider_credential(provider),
        )
        log_tracked_proxy_request(
            session,
            input_format="openai",
            output_format="openai",
            endpoint="/v1/chat/completions",
            client_name="test",
            resolved_route=route,
            requested_model="claude-flex",
            duration_ms=10,
            status_code=200,
            streamed=False,
            request_payload={"model": "claude-flex", "service_tier": "flex"},
            response_payload={"id": "chatcmpl_flex"},
            usage_snapshot=UsageSnapshot.flat(
                input_tokens=1_000,
                output_tokens=1_000,
                total_tokens=2_000,
                token_source="provider_reported",
            ),
        )
        record = session.scalars(select(ApiRequest).order_by(ApiRequest.created_at.desc())).first()

    assert record is not None
    assert record.service_tier == "flex"
    assert record.estimated_cost_usd == 0.006


def test_log_tracked_proxy_request_does_not_price_legacy_rates(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
        assert provider is not None
        session.add(
            PricingOverride(
                provider_id=provider.id,
                model="claude-legacy-rates",
                input_per_1m_usd=3.0,
                output_per_1m_usd=15.0,
                enabled=True,
            )
        )
        session.commit()

        from app.api.proxy_common import log_tracked_proxy_request
        from app.routing.provider_router import select_provider_credential

        route = ResolvedProviderRoute(
            requested_model="claude-legacy-rates",
            upstream_model="claude-legacy-rates",
            provider=provider,
            credential=select_provider_credential(provider),
        )
        log_tracked_proxy_request(
            session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name="test",
            resolved_route=route,
            requested_model="claude-legacy-rates",
            duration_ms=10,
            status_code=200,
            streamed=False,
            request_payload={"model": "claude-legacy-rates"},
            response_payload={"id": "msg_legacy"},
            usage_snapshot=UsageSnapshot.flat(
                input_tokens=100,
                output_tokens=10,
                total_tokens=110,
                token_source="provider_reported",
            ),
        )
        record = session.scalars(select(ApiRequest).order_by(ApiRequest.created_at.desc())).first()

    assert record is not None
    assert record.estimated_cost_usd is None
    assert record.pricing_source is None


def test_log_tracked_proxy_request_preserves_component_precision(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
        assert provider is not None
        card = RateCard(
            standard=TierRates(
                input_per_1m=Decimal("0.5"),
                output_per_1m=Decimal("0.5"),
            ),
            source="manual",
        )
        session.add(
            PricingOverride(
                provider_id=provider.id,
                model="claude-precision",
                input_per_1m_usd=0.5,
                output_per_1m_usd=0.5,
                rate_card_json=card.model_dump_json(),
                source="manual",
                enabled=True,
            )
        )
        session.commit()

        from app.api.proxy_common import log_tracked_proxy_request
        from app.routing.provider_router import select_provider_credential

        route = ResolvedProviderRoute(
            requested_model="claude-precision",
            upstream_model="claude-precision",
            provider=provider,
            credential=select_provider_credential(provider),
        )
        log_tracked_proxy_request(
            session,
            input_format="anthropic",
            output_format="anthropic",
            endpoint="/v1/messages",
            client_name="test",
            resolved_route=route,
            requested_model="claude-precision",
            duration_ms=10,
            status_code=200,
            streamed=False,
            request_payload={"model": "claude-precision"},
            response_payload={"id": "msg_precision"},
            usage_snapshot=UsageSnapshot.flat(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                token_source="provider_reported",
            ),
        )
        record = session.scalars(select(ApiRequest).order_by(ApiRequest.created_at.desc())).first()

    assert record is not None
    assert record.cost_input_usd == 0.0000005
    assert record.cost_output_usd == 0.0000005
    assert record.estimated_cost_usd == 0.000001
    assert record.cost_input_usd + record.cost_output_usd == record.estimated_cost_usd


def test_anthropic_messages_path_prices_cache_reads(client, app_config, monkeypatch) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        provider = get_provider_by_slug(session, "anthropic")
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

    def fake_create_anthropic_message(provider, api_key, payload):
        return {
            "id": "msg_cache_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 50,
                "output_tokens": 20,
                "cache_read_input_tokens": 9000,
                "cache_creation_input_tokens": 1000,
            },
        }

    monkeypatch.setattr(
        "app.api.anthropic.create_anthropic_message",
        fake_create_anthropic_message,
    )

    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-local-token"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 200

    from app.database import build_session_factory

    with build_session_factory(f"sqlite:///{app_config.parent / 'test.db'}")() as session:
        record = session.scalars(select(ApiRequest).order_by(ApiRequest.created_at.desc())).first()

    assert record is not None
    assert record.cache_read_tokens == 9000
    assert record.cache_write_5m_tokens == 1000
    assert record.uncached_input_tokens == 50
    assert record.input_tokens == 10050
    assert record.estimated_cost_usd == 0.0069
