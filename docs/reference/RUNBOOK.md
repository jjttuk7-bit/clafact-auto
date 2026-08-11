# CLAFACT-AUTO Runbook

## Prerequisites

- Python 3.12 or later
- KOSIS and HCX keys supplied only through environment variables or `.env`

```ini
KOSIS_API_KEY=...
HCX_API_KEY=...
CLAFACT_LOG_LEVEL=INFO
```

Never commit `.env` or print either key in logs.

## Install and verify

```powershell
python -m pip install -e ".[dev,app]"
python -m pytest -q
```

## Run MVP

```powershell
streamlit run app/streamlit_app.py
```

Enter a news sentence and its article date (`YYYY-MM-DD`). The app displays the parsed Claim, candidates, evidence coordinate, official value status, deterministic verdict, and review-console payload.

## Route policy

- `AUTO`: candidate, evidence coordinate, article-time official value, and deterministic calculation all succeed.
- `HOLD`: missing article date, ambiguous candidate/coordinate, unavailable official value, post-article revision, or API failure.
- `HUMAN_REVIEW`: use when a provider/parser marks the Claim as needing human interpretation.

## Snapshot operations

Snapshots are immutable JSON evidence under `data/kosis_snapshots/`; each saved API response records request parameters, retrieval time, and a SHA-256 response hash. Do not edit a snapshot in place; add a new versioned snapshot.

## Internal validation MVP run

The owner-approved internal-MVP target is the 1,531 available structured Claims. The historical declaration of 1,532 remains recorded: the missing declared record has no Claim ID in the supplied registries and must never be synthesized. The 1,600 raw candidates and 69 source exclusions remain recorded in `artifacts/internal_validation_mvp_full_20260811/reconciliation_report.json`; the approval boundary is in `acceptance_scope.json`.

Run the structured registry only with registered Profiles and immutable snapshots. Preserve results outside Git when they contain operational source data.

```powershell
python -m pytest tests/goldset -q
python -m pytest -q
python -m tools.merge_enriched_registry --source-registry <registry.jsonl> --enriched-registry <enriched_claims.jsonl> --output-dir <run_dir>
python -m tools.materialize_semantic_concepts <run_dir>/derived_registry.jsonl data/semantic_standard/concept_seed_v1.json <run_dir>/concepts.json
python -m tools.run_e2e_batch <run_dir>/derived_registry.jsonl <profiles.json> <run_dir>/concepts.json <run_dir> --profile <additional-profile.json> --snapshot <official-snapshot.json>
```

The merge command creates a derived Registry and never alters the source Registry. The next command materializes the deterministic Claim-to-Concept input required by the batch rerun; it does not invoke an LLM. Expected acceptance baseline: 24 Goldset tests and 450 total tests pass. The current acceptance decision and the historical 1,532nd-record boundary are documented in `docs/reference/INTERNAL_VALIDATION_MVP_ACCEPTANCE.md`.

## Review queues and Profile changes

- Read `profile_review_priority_queue.json` before any Profile work. Each row is grouped by indicator, calculation, frequency, and unit; use the typed `review_queues/` artifacts for parse and other HOLD reasons.
- Add a Profile only after recording its KOSIS table, item, every dimension code, unit, publication policy, and immutable official response hash in `data/verification_profiles/profile_evidence_v1.json`.
- Re-run only the affected Claim family first. Inspect every resulting `AUTO` row; an AUTO result without an official value is a release blocker.
- Keep unresolved country, product, age, region, or frequency scope as `HOLD`; never convert a catalog Top-1 candidate into a Profile without coordinate proof.

## Transport failure and rollback

- KOSIS API timeouts, network errors, and retryable HTTP-style error codes belong in the retry review queue. They are not evidence of a zero value or a mismatch.
- If a new Profile changes an existing AUTO result unexpectedly, remove that new Profile document, keep its evidence artifact for audit, and restore the previous run manifest before re-running.
- The operator console reads persisted artifacts only. It does not mutate Claims, Profiles, KOSIS snapshots, or verdicts.

