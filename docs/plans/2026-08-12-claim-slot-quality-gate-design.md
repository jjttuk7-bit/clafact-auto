# Claim Slot Quality Gate Design

## Purpose

Preserve the imported `gold_standard_v1` 12-slot records while preventing a flattened or contradictory `indicator` from selecting an unrelated KOSIS table.

## Observed failure

The monthly inflation cluster contains source sentences such as “가공식품 물가”, “외식 물가”, and “근원물가”, but their structured `indicator` is uniformly `물가상승률`. KOSIS discovery can find broad CPI tables, yet the evidence resolver cannot safely select a specific item or dimension. A forced choice would violate the hard-guard rule.

## Selected approach

Add a deterministic, pre-KOSIS slot-quality gate. It compares normalized indicator wording with the source sentence and flags only known over-broad indicators when a more specific statistical modifier is present in that sentence. The original record remains immutable. The gate emits a `CLAIM_PARSE_UNCERTAIN` HOLD and an explicit reparse-queue entry.

## Alternatives considered

1. Map all `물가상승률` claims directly to a CPI table. Rejected: it would incorrectly handle producer prices, processed food, dining out, and core inflation.
2. Add broad semantic aliases to evidence-item matching. Rejected: aliases at this scope would bypass source-specific distinction and can create false AUTO verdicts.
3. Deterministic quality gate plus targeted reparse queue. Selected: preserves safety, keeps the failure reason observable, and sends only defective records to the OpenAI 12-slot parser.

## Data flow

`Claim Registry → Slot Quality Gate → valid Claim: existing dynamic pipeline / flagged Claim: CLAIM_PARSE_UNCERTAIN + reparse queue`.

The gate does not call OpenAI or KOSIS, does not mutate Gold input, and does not declare an AUTO result.

## Acceptance criteria

- A generic inflation indicator with a source-specific modifier is held before semantic mapping.
- A generic national inflation sentence without a specific modifier remains eligible.
- The hold reason and detected modifier are available to the review/reparse queue.
- Existing frozen-snapshot and dynamic-batch tests continue passing.
