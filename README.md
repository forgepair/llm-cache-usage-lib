# llm-cache-usage

A small, dependency-light library for parsing, merging, and costing LLM
providers' prompt-cache usage fields correctly -- starting with
Anthropic's `cache_creation_input_tokens`/`cache_read_input_tokens`.

## Why I built this

Two distinct bug classes recur constantly across gateway/observability
projects that consume these fields:

1. **Streaming merge bugs.** Usage fields arrive incrementally across a
   stream, and a later, authoritative update (e.g.
   `cache_creation_input_tokens: 0`, meaning "no cache write actually
   happened") gets treated as "no update" instead of the real final
   value -- leaving a stale earlier positive number in place. This
   produces negative "uncached tokens" when computed as
   `prompt_tokens - cache_read - cache_creation`.
2. **Per-model pricing-multiplier bugs.** Cache-read/write pricing is
   *not* a flat percentage of a model's base price across every model --
   providers now ship per-model exceptions -- so hardcoded multipliers
   silently misbill as new model variants ship.

This isn't hypothetical. Independently re-searched each of these
projects (2026-09-12) and found this bug class recurring dozens of
times, not once per project:

- **LiteLLM**: at least 3 distinct, dated instances spanning nearly a
  year -- `#15263` (closed), `#34497` (open), and `#40736` (open, filed
  the day before this library was started). `#40736` is a real,
  reproduced negative-billing bug: `58354 - 58352 - 58352 = -58350`
  uncached tokens, when the correct answer is `2`. This library's own
  test suite reproduces that exact bug against BerriAI's own pasted
  fixture, then proves the fix against it.
- **`router-for-me/CLIProxyAPI`**: at least 15 distinct issues/PRs
  touching cache-token-field handling.
- **mlflow**: multiple open issues on cache-token extraction, plus
  several already-merged fixes for the same underlying class.
- **vercel/ai**: 10+ distinct closed/open issues across Anthropic,
  Bedrock, and OpenAI-compatible paths.
- **higress**: 5 distinct issues on Bedrock cache read/write token
  category preservation.

No existing shared library fills this gap -- every one of the above
projects independently reimplements this parsing/merging logic in-house,
and the `llm-cache-usage` name was unclaimed on both PyPI and npm as of
2026-09-12.

### A concrete, currently-live example of bug class 2

Checked directly against Anthropic's live pricing docs
(`platform.claude.com/docs/en/build-with-claude/prompt-caching`,
2026-09-12): Claude Fable 5.1 and Mythos 5.1 get a special 0.025x
cache-read multiplier (vs. the standard 0.1x every other model uses) --
widely reported as "4x cheaper" cache reads. That framing is misleading
for actual per-token cost, because Fable 5.1's base input price
($10/MTok) is 5x higher than Sonnet 5's ($2/MTok):

- Fable 5.1 cache-read price: $10 x 0.025 = **$0.25/MTok**
- Sonnet 5 cache-read price: $2 x 0.10 = **$0.20/MTok**

Fable 5.1's cache reads are nominally *more* expensive per token than
Sonnet 5's, despite the much-touted multiplier cut. Anyone building
cost-routing logic around the "4x cheaper" headline without checking the
real per-token number would misroute traffic. Anthropic added its first
per-model pricing exception on 2026-09-01 -- any project that assumed
"cache reads are always 0.1x base price" broke quietly on that date.

## What it does

- **Field-presence-aware usage merging** for streaming responses: a
  field present in a chunk (with any value, including `0`) replaces the
  running value; a field *absent* from a chunk leaves the running value
  untouched. This is the exact fix the LiteLLM issue itself proposes.
- **A per-model pricing table**, not a hardcoded flat multiplier,
  covering Anthropic's real per-model exceptions.

## Install

```
pip install llm-cache-usage
```

## Use

```python
from llm_cache_usage import merge_usage_events, uncached_input_tokens, cost_from_usage

merged = merge_usage_events([start_chunk, final_chunk])
uncached_input_tokens(merged)          # correct even after an explicit 0 update
cost_from_usage("claude-sonnet-5", merged)
```

## Verification

`tests/test_merge.py` uses the exact `start_usage`/`final_usage` fixture
BerriAI pasted into `litellm#40736`'s own "Deterministic source-level
reproduction" section -- not synthesized data. It first reproduces the
naive/buggy merge (confirms our repro matches the issue's own reported
`-58350`), then proves the fix against the issue's own expected `2`, plus
the omitted-field-preserves-prior-value case the issue names as a
required regression test. `tests/test_pricing.py` checks the Fable 5.1 /
Sonnet 5 comparison above against real numbers.

## Known open items

- Anthropic-only so far. Not yet checked whether OpenAI's cache pricing
  or Google's context caching have similar per-model exceptions or the
  same streaming-merge fragility.
- Python only so far -- several of the affected projects above (vercel/ai,
  CLIProxyAPI) are JS/TS, and this may be worth porting.
- Scope decision not yet made: keep this as a standalone library vs.
  contributing fixes directly upstream to the affected projects (the
  latter has more direct impact but doesn't prevent the next unrelated
  project from hitting the same bug independently).
- Not yet published to PyPI.

## License

MIT
