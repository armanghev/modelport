from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import load_config
from app.database import ApiRequest, build_session_factory
from app.tracking.cost_service import calculate_estimated_cost_usd
from app.tracking.pricing import resolve_pricing_override


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

            pricing = resolve_pricing_override(
                session,
                provider_id=record.provider,
                resolved_model=record.resolved_model,
                requested_model=record.requested_model,
            )
            estimated_cost_usd, pricing_source = calculate_estimated_cost_usd(
                pricing,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
            )
            if estimated_cost_usd is None:
                if record.estimated_cost_usd is not None or record.pricing_source is not None:
                    record.estimated_cost_usd = None
                    record.pricing_source = None
                    updated += 1
                else:
                    skipped_no_pricing += 1
                continue

            if (
                record.estimated_cost_usd != estimated_cost_usd
                or record.pricing_source != pricing_source
            ):
                record.estimated_cost_usd = estimated_cost_usd
                record.pricing_source = pricing_source
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
