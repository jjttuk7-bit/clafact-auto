# Claim Admission Router Design

## Goal

Route every numeric-sentence candidate through a controlled admission decision before
the 12-slot/KOSIS official-verification path.  Only KOSIS-eligible claims may invoke
the official engine.

## Decision contract

The router produces one of six labels with a stable reason code and audit trail:

- `KOSIS_PIPELINE_ELIGIBLE`: a single, present-tense statistical claim can proceed
  to 12-slot parsing and official KOSIS verification.
- `CONTEXT_REQUIRED`: title and a bounded neighbourhood must be supplied, then the
  reparsed result re-enters the router once.
- `MULTI_CLAIM_SPLIT_REQUIRED`: deterministic splitting creates child candidates;
  each child re-enters the router once.
- `NON_KOSIS_OR_PRIVATE`: record an external-source-review route; never invoke
  KOSIS for the claim.
- `FORECAST_OPINION_UNVERIFIABLE`: record an excluded automated-fact-check route.
- `NOT_A_VERIFIABLE_CLAIM`: record an excluded non-claim route.

`KOSIS_PIPELINE_ELIGIBLE` is an admission result, not an AUTO verdict.  The existing
official engine remains the only component allowed to produce `MATCH`, `MISMATCH`,
or an official-query `HOLD`.

## Processing flow

```text
numeric candidate
  -> Admission Router
  -> eligible: parse 12 slots -> shared OfficialEvidenceService -> verdict
  -> context required: bounded context reparse -> Admission Router (one retry)
  -> split required: split -> Admission Router per child (one split generation)
  -> excluded/external: terminal ADMISSION_ROUTED record
```

The orchestration preserves original claim/article identifiers, gives child claims a
deterministic suffix, and emits an event trace.  It must not label a pre-query
admission outcome as `HOLD`: `HOLD` remains reserved for an attempted official
KOSIS stage as required by `CLAFACT_AUTO_EXECUTION_CONTRACT.md`.

## Safety and failure handling

- Context is limited to the existing title plus target-sentence neighbourhood.
- A missing context, failed reparse, unsplittable multi-claim, or exhausted retry
  remains an `ADMISSION_ROUTED` result with its admission reason; it does not enter
  the official engine.
- Each source candidate has bounded processing: one context reparse and one split
  generation.  This prevents recursive loops.
- Non-KOSIS/private candidates are recorded as `EXTERNAL_SOURCE_REVIEW_REQUIRED`;
  no second source-verification engine is introduced in this scope.

## Validation

Tests first prove all six routes, bounded retry behavior, child re-admission, and
that only eligible claims call the injected official resolver.  Integration tests
prove the shared article/batch entrypoint emits the same result contract.  Final
acceptance runs the 1,542-candidate population through the router and runs actual
official KOSIS requests only for admitted claims, preserving API traces and reason
codes.
