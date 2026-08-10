# KOSIS Evidence Coordinate and Snapshot Service Design

## Decision

Implement one deterministic service that converts an approved verification
profile and a confirmed claim period into an auditable `EvidenceCellSchema`.
It returns a structured `HOLD` instead of calling KOSIS whenever a required
coordinate, period, or unit is unavailable or inconsistent.

## Data Contract

`VerificationProfileSchema` will add the stable retrieval fields `prd_se` and
`unit`. They are profile-owned KOSIS metadata, not values inferred by an LLM.
The claim supplies its parsed period; a profile's period frequency and unit
must agree with the claim when those claim fields are present.

The new resolution result will contain one of `CONFIRMED` or `HOLD`, an
optional `EvidenceCellSchema`, and a stable reason code. A confirmed cell has
only official profile coordinates and a canonical key derived from them.

## Flow

1. Receive an exact-match profile, an `AUTO_OK` claim, and an explicit KOSIS
   period value.
2. Reject incomplete profile coordinate, missing period, frequency mismatch,
   or unit mismatch with `HOLD`.
3. Build the Evidence Cell from profile `org_id`, `tbl_id`, `itm_id`,
   dimensions, frequency, unit, and period.
4. Keep the existing `OfficialValueFetcher` as the sole official-value reader;
   it already enforces article-date as-of filtering.
5. Save any KOSIS response with the complete requested coordinate, article
   date when known, retrieval time, and SHA-256 response hash.

## Boundaries

This increment does not invoke a live API, generate an official number,
calculate a verdict, or replace existing snapshot readers. It supplies a
safe, reproducible coordinate handoff and enriches snapshot audit metadata.

## Tests

Use unit tests for successful coordinate construction, missing period HOLD,
unit/frequency mismatch HOLD, and snapshot request metadata plus response
hash preservation. Existing fetcher tests remain the proof of as-of value
selection.
