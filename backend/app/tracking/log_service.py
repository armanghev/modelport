from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import ApiRequest


def create_api_request_log(
    session: Session,
    *,
    input_format: str,
    output_format: str,
    endpoint: str,
    client_name: str | None,
    requested_model: str | None,
    resolved_model: str | None,
    provider: str | None,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    token_source: str | None,
    estimated_cost_usd: float | None,
    pricing_source: str | None,
    duration_ms: int | None,
    status_code: int | None,
    error_message: str | None,
    streamed: bool,
    request_id: str | None,
    ttfb_ms: int | None = None,
    completion_reason: str | None = None,
) -> ApiRequest:
    record = ApiRequest(
        input_format=input_format,
        output_format=output_format,
        endpoint=endpoint,
        client_name=client_name,
        requested_model=requested_model,
        resolved_model=resolved_model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        token_source=token_source,
        estimated_cost_usd=estimated_cost_usd,
        pricing_source=pricing_source,
        ttfb_ms=ttfb_ms,
        duration_ms=duration_ms,
        status_code=status_code,
        completion_reason=completion_reason,
        error_message=error_message,
        streamed=streamed,
        request_id=request_id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
