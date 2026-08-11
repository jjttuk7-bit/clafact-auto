# Registry 12-Slot Completion Design

## Goal

Reprocess the 772 existing `AUTO_OK` registry records with OpenAI Structured Output, normalize comparison and calculation semantics deterministically, map concepts, and run only unambiguous registered-profile claims through KOSIS verification.

## Data boundaries

The 1,531-record Guard registry remains immutable. The 1,532 target mismatch stays in a reconciliation report until its missing source identity is supplied. OpenAI output is schema-constrained; it never provides KOSIS official values, evidence coordinates, or a verdict. Derived JSONL, mappings, reports, and E2E results are written to a new execution directory.

## Normalization

Normalize all equivalent comparison keys (`period`, `reference_period`, and `basis`) to `basis`. Only the exact normalized basis `전년 동월 대비` may infer `GROWTH_RATE` when calculation is empty. Other ambiguous or unsupported comparisons remain HOLD. Concept mapping is deterministic against `concept_seed_v1.json`; no approximate tie is selected.

## Verification

The pipeline emits both a Claim/Concept sidecar and profile-first E2E artifacts. Existing registered profiles can produce AUTO only when semantic keys and KOSIS evidence resolve exactly. All other records retain explicit HOLD reasons. Unit tests cover comparison-key normalization and end-to-end growth planning before the OpenAI batch is run.
