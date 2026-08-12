# Export Rank Contract Design

## Goal

Prevent malformed export RANK Claims from entering KOSIS selection unless the ranked target and comparison population are explicit.

## Decision

Keep the existing pipeline and extend the deterministic Claim slot-quality boundary. A RANK Claim must use unit `위`, a positive integer claim value, exactly one ranked product target, and condition fields `rank_value`, `order`, and `population_scope`. `order` is limited to `DESC` or `ASC`; `rank_value` must equal the Claim value.

The OpenAI Structured Output prompt receives the same contract. Existing shorthand such as `condition.rank`, percentage values misclassified as rank, multiple ranked targets, and missing comparison populations route to `CLAIM_PARSE_UNCERTAIN` before KOSIS search.

## Safety boundary

This step validates the Claim contract only. Actual RANK AUTO verification additionally requires resolving the population into multiple official Evidence Cells; no Claim is promoted to AUTO until that downstream capability exists.