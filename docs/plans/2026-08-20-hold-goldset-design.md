# HOLD Gold Set Candidate Design

**Goal:** Generate a reproducible, human-review-ready sample from the 1,507 HOLD results without changing the official pipeline outcome.

## Decision

Use deterministic stratified sampling of 250 records. Every HOLD reason is represented; large failure groups receive proportionally more records. The output is explicitly a candidate set until a human verifies official KOSIS evidence.

## Outputs

- Full immutable HOLD inventory
- 250-record JSONL and CSV review sample
- Reviewer labeling guide and sampling report

## Safety

The generator never queries or fabricates official values, never modifies the source E2E results, and refuses to overwrite an existing artifact directory.
