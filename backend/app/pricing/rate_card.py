from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# Higher wins. A catalog re-import must never displace a hand-set card.
SOURCE_PRECEDENCE: dict[str, int] = {
    "manual": 100,
    "openrouter": 80,
    "litellm": 60,
    "local": 60,
    "legacy_seed": 20,
}


class TierRates(BaseModel):
    input_per_1m: Decimal
    output_per_1m: Decimal
    cache_read_per_1m: Decimal | None = None
    cache_write_5m_per_1m: Decimal | None = None
    cache_write_1h_per_1m: Decimal | None = None


class ToolCharge(BaseModel):
    name: str
    per_call_usd: Decimal


class RateCard(BaseModel):
    standard: TierRates | None = None
    above_threshold: TierRates | None = None
    context_threshold_tokens: int | None = None
    service_tiers: dict[str, TierRates] = Field(default_factory=dict)
    tools: list[ToolCharge] = Field(default_factory=list)
    operation_rates: dict[str, Decimal] = Field(default_factory=dict)
    source: str = "litellm"
    source_fetched_at: datetime | None = None

    def context_tier_for(self, input_tokens: int) -> str:
        if self.context_threshold_tokens is None:
            return "standard"
        if input_tokens > self.context_threshold_tokens:
            return "above_threshold"
        return "standard"

    def rates_for(self, *, context_tier: str, service_tier: str) -> TierRates | None:
        if service_tier != "standard":
            tier_rates = self.service_tiers.get(service_tier)
            if tier_rates is not None:
                return tier_rates
        if context_tier == "above_threshold" and self.above_threshold is not None:
            return self.above_threshold
        return self.standard


def source_rank(source: str | None) -> int:
    return SOURCE_PRECEDENCE.get(source or "", 0)
