# Export Threshold Contract Design

## Goal

Allow an export THRESHOLD Claim to enter KOSIS verification only when the 12-slot result explicitly separates the official observation from the threshold predicate.

## Decision

Keep the existing Claim Parse → Semantic Mapping → Catalog → Hard Guard pipeline. Add a deterministic slot-quality contract requiring `condition.operator`, `condition.threshold_value`, and `condition.threshold_unit`. Missing or unsupported predicates route to `CLAIM_PARSE_UNCERTAIN`; no threshold is inferred from arbitrary numbers in the sentence.

## Structured output

The OpenAI parser must emit an operator from `GT`, `GTE`, `LT`, or `LTE`, a numeric threshold serialized as text, and the threshold unit. The observation remains in `value`/`unit`. This keeps official values and Python calculation inputs distinct.

## Verification

The existing ten malformed export THRESHOLD records must all stop before KOSIS lookup. A complete synthetic threshold Claim must remain eligible. Focused tests, the ten-record batch, all unit tests, integration tests, and Goldset tests must pass.