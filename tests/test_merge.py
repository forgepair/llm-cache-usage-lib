"""Regression fixtures taken verbatim from BerriAI/litellm#40736's own
"Deterministic source-level reproduction" section -- not synthesized.
"""

from llm_cache_usage.merge import (
    merge_usage_events,
    naive_merge_usage_events,
    uncached_input_tokens,
)

# Exact fixture from the issue.
START_USAGE = {
    "input_tokens": 2,
    "output_tokens": 1,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 58352,
    "cache_creation": {
        "ephemeral_5m_input_tokens": 58352,
        "ephemeral_1h_input_tokens": 0,
    },
}

FINAL_USAGE = {
    "input_tokens": 2,
    "output_tokens": 408,
    "cache_read_input_tokens": 58352,
    "cache_creation_input_tokens": 0,
    "cache_creation": {
        "ephemeral_5m_input_tokens": 0,
        "ephemeral_1h_input_tokens": 0,
    },
}


def test_naive_merge_reproduces_the_reported_bug():
    """Confirms our reproduction matches the issue's own reported result
    (-58350 uncached) before trusting the fix against it."""
    merged = naive_merge_usage_events([START_USAGE, FINAL_USAGE])
    assert merged["cache_creation_input_tokens"] == 58352  # stale positive, wrongly kept
    assert merged["cache_read_input_tokens"] == 58352

    prompt_tokens = 58354  # the issue's own reported physical prompt size
    uncached = prompt_tokens - merged["cache_read_input_tokens"] - merged["cache_creation_input_tokens"]
    assert uncached == -58350  # exactly the issue's reported (wrong) result


def test_fixed_merge_matches_issues_expected_output():
    merged = merge_usage_events([START_USAGE, FINAL_USAGE])
    assert merged["cache_creation_input_tokens"] == 0  # explicit 0 replaces the stale 58352
    assert merged["cache_read_input_tokens"] == 58352
    assert merged["input_tokens"] == 2
    assert merged["output_tokens"] == 408
    assert uncached_input_tokens(merged) == 2


def test_nested_cache_creation_breakdown_merges_too():
    merged = merge_usage_events([START_USAGE, FINAL_USAGE])
    assert merged["cache_creation"] == {
        "ephemeral_5m_input_tokens": 0,
        "ephemeral_1h_input_tokens": 0,
    }


def test_omitted_field_preserves_prior_value():
    """Issue's own required regression case #5: a chunk that doesn't
    mention a cache field at all must not clobber the running value."""
    later_chunk_no_cache_fields = {"output_tokens": 409}
    merged = merge_usage_events([START_USAGE, FINAL_USAGE, later_chunk_no_cache_fields])
    assert merged["cache_read_input_tokens"] == 58352
    assert merged["cache_creation_input_tokens"] == 0
    assert merged["output_tokens"] == 409


def test_prompt_tokens_style_fallback():
    usage = {"prompt_tokens": 58354, "cache_read_input_tokens": 58352, "cache_creation_input_tokens": 0}
    assert uncached_input_tokens(usage) == 2
