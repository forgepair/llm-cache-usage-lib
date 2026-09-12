"""Pricing numbers verified directly against platform.claude.com/docs/en/
build-with-claude/prompt-caching on 2026-09-12.
"""

from llm_cache_usage.pricing import PRICING, cache_read_cost, cost_from_usage


def test_fable_5_1_has_the_special_low_read_multiplier():
    assert PRICING["claude-fable-5-1"].cache_read_multiplier == 0.025
    assert PRICING["claude-sonnet-5"].cache_read_multiplier == 0.10


def test_fable_5_1_cache_reads_are_nominally_more_expensive_than_sonnet_5():
    """The brief's core, counterintuitive finding: despite the widely-touted
    "4x cheaper" multiplier, Fable 5.1's much higher base price means its
    cache-read $/MTok is still higher than Sonnet 5's, not lower."""
    fable_cost = cache_read_cost("claude-fable-5-1", 1_000_000)
    sonnet_cost = cache_read_cost("claude-sonnet-5", 1_000_000)

    assert fable_cost == 0.25
    assert sonnet_cost == 0.20
    assert fable_cost > sonnet_cost


def test_cost_from_usage_uses_the_real_litellm_fixture():
    # The corrected (post-merge-fix) usage from test_merge.py's fixture.
    usage = {
        "input_tokens": 2,
        "cache_read_input_tokens": 58352,
        "cache_creation_input_tokens": 0,
    }
    costs = cost_from_usage("claude-sonnet-5", usage)
    assert costs["cache_write_cost"] == 0.0
    # 58352 cached tokens at $0.20/MTok
    assert round(costs["cache_read_cost"], 6) == round(58352 * 0.20 / 1_000_000, 6)
    # 2 uncached tokens at $2/MTok base price
    assert round(costs["uncached_input_cost"], 6) == round(2 * 2.00 / 1_000_000, 6)
