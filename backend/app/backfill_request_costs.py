from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import load_config
from app.database import ApiRequest, build_session_factory
from app.pricing.calculator import RequestContext, price
from app.pricing.resolver import resolve_rate_card
from app.tracking.usage_service import UsageSnapshot


def backfill_request_costs(session_factory: sessionmaker[Session]) -> dict[str, int | float]:
    updated = 0
    skipped_no_pricing = 0
    skipped_no_provider = 0
    total_cost = 0.0

    with session_factory() as session:
        requests = session.scalars(select(ApiRequest).order_by(ApiRequest.created_at)).all()
        for record in requests:
            if not record.provider:
                skipped_no_provider += 1
                continue

            card = resolve_rate_card(
                session,
                provider_id=record.provider,
                resolved_model=record.resolved_model,
                requested_model=record.requested_model,
            )
            if card is None:
                if record.estimated_cost_usd is not None or record.pricing_source is not None:
                    record.estimated_cost_usd = None
                    record.pricing_source = None
                    updated += 1
                else:
                    skipped_no_pricing += 1
                continue

            if record.uncached_input_tokens is not None:
                usage = UsageSnapshot(
                    uncached_input_tokens=record.uncached_input_tokens or 0,
                    cache_read_tokens=record.cache_read_tokens or 0,
                    cache_write_5m_tokens=record.cache_write_5m_tokens or 0,
                    cache_write_1h_tokens=record.cache_write_1h_tokens or 0,
                    output_tokens=record.output_tokens,
                    total_tokens=record.total_tokens,
                    token_source=record.token_source,
                )
            else:
                usage = UsageSnapshot.flat(
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    total_tokens=record.total_tokens,
                    token_source=record.token_source,
                )

            breakdown = price(usage, card, RequestContext())
            estimated_cost_usd = float(breakdown.total_usd)
            pricing_source = card.source
            has_buckets = record.uncached_input_tokens is not None

            if (
                record.estimated_cost_usd != estimated_cost_usd
                or record.pricing_source != pricing_source
                or (
                    has_buckets
                    and (
                        record.cost_input_usd != float(breakdown.input_usd)
                        or record.cost_output_usd != float(breakdown.output_usd)
                        or record.cost_cache_read_usd != float(breakdown.cache_read_usd)
                        or record.cost_cache_write_usd != float(breakdown.cache_write_usd)
                        or record.cost_tools_usd != float(breakdown.tools_usd)
                        or record.context_tier != breakdown.context_tier
                        or record.service_tier != breakdown.service_tier
                    )
                )
            ):
                record.estimated_cost_usd = estimated_cost_usd
                record.pricing_source = pricing_source
                if has_buckets:
                    record.cost_input_usd = float(breakdown.input_usd)
                    record.cost_output_usd = float(breakdown.output_usd)
                    record.cost_cache_read_usd = float(breakdown.cache_read_usd)
                    record.cost_cache_write_usd = float(breakdown.cache_write_usd)
                    record.cost_tools_usd = float(breakdown.tools_usd)
                    record.context_tier = breakdown.context_tier
                    record.service_tier = breakdown.service_tier
                updated += 1
                total_cost += estimated_cost_usd

        session.commit()

    return {
        "total_requests": len(requests),
        "updated": updated,
        "skipped_no_pricing": skipped_no_pricing,
        "skipped_no_provider": skipped_no_provider,
        "total_cost_usd": round(total_cost, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="One-time backfill of api_requests.estimated_cost_usd.")
    parser.add_argument("--config", default="../config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    session_factory = build_session_factory(config.database.url)
    summary = backfill_request_costs(session_factory)
    print("Backfill complete:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
