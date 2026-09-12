"""Per-model cache pricing, not a hardcoded flat multiplier.

Verified directly against platform.claude.com/docs/en/build-with-claude/
prompt-caching, 2026-09-12. Every model uses a 1.25x write / 0.1x read
multiplier on its own base input price EXCEPT Claude Fable 5.1 and
Claude Mythos 5.1, which get a 0.025x cache-read multiplier instead --
introduced 2026-09-01 as Anthropic's first per-model pricing exception.
"""

from __future__ import annotations

from dataclasses import dataclass

from .merge import uncached_input_tokens


@dataclass(frozen=True)
class ModelPricing:
    base_input_per_mtok: float
    cache_write_multiplier: float
    cache_read_multiplier: float

    @property
    def cache_write_per_mtok(self) -> float:
        return self.base_input_per_mtok * self.cache_write_multiplier

    @property
    def cache_read_per_mtok(self) -> float:
        return self.base_input_per_mtok * self.cache_read_multiplier


# $/MTok base input price, and this model's cache write/read multipliers.
PRICING: dict[str, ModelPricing] = {
    "claude-fable-5-1": ModelPricing(10.00, 1.25, 0.025),
    "claude-mythos-5-1": ModelPricing(10.00, 1.25, 0.025),
    "claude-fable-5": ModelPricing(10.00, 1.25, 0.10),
    "claude-mythos-5": ModelPricing(10.00, 1.25, 0.10),
    "claude-opus-5": ModelPricing(5.00, 1.25, 0.10),
    "claude-opus-4-8": ModelPricing(5.00, 1.25, 0.10),
    "claude-sonnet-5": ModelPricing(2.00, 1.25, 0.10),
    "claude-sonnet-4-6": ModelPricing(3.00, 1.25, 0.10),
    "claude-haiku-4-5": ModelPricing(1.00, 1.25, 0.10),
}


def cache_read_cost(model: str, tokens: int) -> float:
    return PRICING[model].cache_read_per_mtok * tokens / 1_000_000


def cache_write_cost(model: str, tokens: int) -> float:
    return PRICING[model].cache_write_per_mtok * tokens / 1_000_000


def cost_from_usage(model: str, usage: dict[str, int]) -> dict[str, float]:
    """Full cost breakdown for one merged usage dict."""
    p = PRICING[model]
    uncached = uncached_input_tokens(usage)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    return {
        "uncached_input_cost": uncached * p.base_input_per_mtok / 1_000_000,
        "cache_read_cost": cache_read_cost(model, cache_read),
        "cache_write_cost": cache_write_cost(model, cache_write),
    }
