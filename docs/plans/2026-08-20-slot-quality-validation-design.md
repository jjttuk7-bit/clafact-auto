# Slot Quality Validation Design

## Goal

Validate the paused 12-slot parsing changes before expanding them to a registry-wide run, then measure their effect through a bounded official KOSIS execution.

## Decision

Use a validation-first sequence: preserve the existing uncommitted implementation, run its focused regression tests, repair only demonstrated defects, then run the full suite.  Once the local gate is green, execute a 25-record read-only official batch using the existing engine and compare routing reasons against the prior baseline.

## Data flow

`source_sentence` -> comparison/dimension enrichment -> ClaimSchema contract -> existing official evidence engine -> KOSIS catalog/metadata/value/publication calls -> deterministic calculation and verdict.

No registry source rows are modified. The batch writes only a new, timestamped artifact directory. An unavailable external API must remain an explicit operational HOLD reason; it must not be recast as missing evidence.

## Acceptance criteria

- Focused parser, deterministic enrichment, and metadata-repository tests pass.
- Full pytest suite passes without introducing unrelated edits.
- A bounded 25-record batch attempts the official path and retains per-stage traces.
- The run report compares AUTO/HOLD reasons with the August 14 baseline and identifies whether parsing uncertainty decreased.
