"""Field-presence-aware merging of streamed LLM usage snapshots.

Fixes the bug class reported in BerriAI/litellm#40736: a later usage
chunk explicitly reporting a field as 0 (e.g. "the cache write that was
in progress earlier did not happen after all") must replace an earlier
positive value for that field. The naive approach -- skip a field
whenever its new value is falsy -- silently keeps the stale positive
number and produces negative "uncached tokens" downstream.

Rule: a field present in a chunk (with any value, including 0) replaces
the running value. A field *absent* from a chunk leaves the running
value untouched. `None` is treated as absent, matching how these SDKs
represent "not reported this chunk" rather than "reported as null".
"""

from __future__ import annotations

from typing import Any


def merge_usage_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a sequence of streaming usage snapshots into a final usage dict.

    Nested dict-valued fields (e.g. Anthropic's `cache_creation` breakdown)
    are merged recursively with the same presence rule, key by key.
    """
    merged: dict[str, Any] = {}
    for event in events:
        _merge_into(merged, event)
    return merged


def _merge_into(merged: dict[str, Any], event: dict[str, Any]) -> None:
    for key, value in event.items():
        if value is None:
            continue
        if isinstance(value, dict):
            merged[key] = _merge_dict(merged.get(key), value)
        else:
            merged[key] = value


def _merge_dict(existing: Any, incoming: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    _merge_into(base, incoming)
    return base


def naive_merge_usage_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """The buggy merge this library replaces, reproduced for regression tests.

    Mirrors the actual upstream snippet quoted in litellm#40736: a field
    only updates the running value if the incoming value is truthy (> 0)
    or nothing has been seen yet -- so an explicit 0 after a positive
    value is silently discarded.
    """
    merged: dict[str, Any] = {}
    for event in events:
        for key, value in event.items():
            if value is None:
                continue
            if isinstance(value, dict):
                merged[key] = value
                continue
            if value or key not in merged:
                merged[key] = value
    return merged


def uncached_input_tokens(usage: dict[str, Any]) -> int:
    """Anthropic-native usage: `input_tokens` already excludes cached tokens."""
    if "input_tokens" in usage:
        return usage["input_tokens"]
    return (
        usage.get("prompt_tokens", 0)
        - usage.get("cache_read_input_tokens", 0)
        - usage.get("cache_creation_input_tokens", 0)
    )
