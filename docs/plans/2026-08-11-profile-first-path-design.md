# Profile-First Path Design

## Decision

Use exact `StandardConceptSchema.standard_key == VerificationProfileSchema.claim_key`
matching as the only Profile-First selection rule. A matched profile is a
deterministic routing choice, not an official value or a verdict.

## Flow

1. Consider profiles only after semantic normalization returns `MATCHED`.
2. Select one profile with the same key.
3. Return `NOT_FOUND` when no profile matches so the ordinary KOSIS catalog
   search can continue.
4. Return `HOLD` when more than one profile matches, the claim explicitly
   requests a different calculation, or a profile is missing a required KOSIS
   coordinate.
5. Leave Hard Guard, official-value retrieval, calculation, and verdicting in
   the existing pipeline. Evidence-cell resolution and snapshots are the next
   milestone, so this change never creates KOSIS values.

## Error Handling

`HOLD` results carry stable reason codes: `PROFILE_KEY_CONFLICT`,
`PROFILE_CALCULATION_CONFLICT`, and `PROFILE_COORDINATE_INCOMPLETE`.

## Tests

Cover exact selection, no-match fallback, explicit-calculation conflict, and
incomplete-coordinate HOLD with pure unit tests.
