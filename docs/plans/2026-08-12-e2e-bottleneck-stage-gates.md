# E2E Bottleneck Stage-Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete CLAFACT-AUTO by removing one measurable pipeline bottleneck at a time, without repeated full-batch reprocessing or unsafe AUTO promotion.

**Architecture:** The gold Registry is a regression corpus, not an AUTO-rate target. Each gate consumes only records that passed the prior gate, writes immutable inputs/outputs, and cannot advance until its acceptance checks pass. New articles and gold claims continue to share the same dynamic engine; only their Claim source differs.

**Tech Stack:** Python 3.12, Pydantic v2, KOSIS API adapter, OpenAI Structured Output, pytest, Streamlit.

---

## Current evidence baseline

- Canonical gold Registry: 1,542 claims, 12 slots preserved, no load errors.
- Input eligibility: 693 are HOLD/HUMAN_REVIEW in the gold source.
- Of those 693 after approved reparse: 622 remain structurally non-verifiable from the available sentence (429 explicit ambiguity/forecast/range/compound reasons, 187 missing required slots, 6 unresolved); 71 reached a downstream gate but none AUTO.
- Of the original 849 AUTO_OK claims: 417 stop at candidate selection/Hard Guard, 327 stop at evidence coordinate, 104 stop later, and 1 reaches AUTO in the rerun.
- A live-search rerun changed five earlier AUTO results into `AMBIGUOUS_MARGIN`, so deterministic Catalog/metadata snapshots are a release blocker.

## Operating rules

1. Never rerun all 1,542 records to diagnose one class.
2. Freeze each gate's input IDs, candidate responses, metadata, versions, and metrics before changing code.
3. Do not change `AUTO_OK` merely to improve coverage; only a parser result with all required evidence conditions may advance.
4. A Claim that cannot be verified from supplied text is a successful, specific HOLD—not backlog for KOSIS tuning.
5. Advance only when a gate's regression tests and acceptance metric pass; otherwise stop and repair that same gate.

### Gate 0: Reproducible KOSIS discovery (release blocker)

**Problem:** Live Catalog discovery/metadata changes candidate ranking across otherwise identical runs.

**Scope:** Only the 849 original `AUTO_OK` Claims plus the 71 reparsed Claims that reached semantic/KOSIS stages. No OpenAI calls.

**Implementation:**
- Persist raw Catalog Search and table-metadata responses keyed by normalized query and KOSIS API version/date.
- Make `KosisLiveCatalogSearch`, metadata refresh, and dynamic batch accept a read-only snapshot first; network fills cache only in an explicit refresh command.
- Record snapshot hashes in every result and trace.

**Acceptance gate:** Run the same frozen input twice with network disabled. Claim ID, candidate ordering, terminal route, reason, evidence coordinates, official values, and calculation must be byte-for-byte identical.

**Do not move to Gate 1 until this passes.**

### Gate 1: Claim admissibility, not blind reparsing

**Problem:** 622 of 693 initially held Claims lack a machine-verifiable statement from available sentence context.

**Scope:** Exactly the original 693 `HOLD`/`HUMAN_REVIEW` claims.

**Implementation:**
- Create an immutable `claim_admissibility.jsonl` with three routes: `VERIFIABLE`, `STRUCTURAL_HOLD`, `CONTEXT_REQUIRED`.
- Normalize model reasons into controlled codes: `MULTI_CLAIM`, `RANGE_VALUE`, `FORECAST_OR_CONDITIONAL`, `RELATIVE_TIME_UNRESOLVED`, `MISSING_REQUIRED_SLOT`, `INDICATOR_UNRESOLVED`.
- Send only `CONTEXT_REQUIRED` records to a future article-context recovery process; do not call OpenAI again for `STRUCTURAL_HOLD` records unless the source text changes.

**Acceptance gate:** Every one of 693 records has exactly one admissibility route, a controlled reason code, and source provenance. Only `VERIFIABLE` records enter KOSIS.

### Gate 2: Candidate selection and Hard Guard

**Problem:** 417 of original AUTO_OK Claims stop before evidence: 217 ambiguous candidates and 200 no Hard Guard candidate.

**Scope:** The frozen candidate snapshot and Claim set that survived Gate 1.

**Implementation:**
- Cluster by normalized `indicator + calculation + unit + frequency + region/dimension requirement`.
- Work one highest-volume cluster at a time; add only verified Concept aliases and explicit hard constraints.
- Build a compact operator decision table for unresolved semantic intents; decisions create a versioned semantic-standard patch, never a hidden profile bypass.

**Acceptance gate per cluster:** Candidate result is either one deterministic structural match with all mandatory constraints or a controlled HOLD code. Re-run that cluster against the frozen snapshot before accepting the next cluster.

### Gate 3: Evidence coordinate resolution

**Problem:** 327 original AUTO_OK Claims have a plausible table but no unique `(table, item, dimension members, period)` coordinate.

**Scope:** Only Claims that passed Gate 2.

**Implementation:**
- Group by `org_id/tbl_id` and cache its item and dimension metadata.
- Resolve required members from Claim slots; reject an unresolved member rather than selecting a default.
- Add table-specific resolver rules only when KOSIS metadata proves the mapping, with tests using cached metadata fixtures.

**Acceptance gate per table:** Every resolved coordinate has a canonical key, item ID, all required dimension codes, period, unit, and metadata snapshot hash. Others remain `NO_EVIDENCE_COORDINATE_CANDIDATE`.

### Gate 4: Official value, calculation, and as-of correctness

**Problem:** Even resolved cells may have no value, comparison base, or publication-time validity.

**Scope:** Only confirmed Evidence Cells.

**Implementation:**
- Fetch values from cached official responses, then run Python deterministic calculation.
- Keep `NO_DATA`, `AS_OF_UNAVAILABLE`, and `MISSING_COMPARISON_FOR_GROWTH_RATE` as distinct terminal HOLDs.
- Add a snapshot regression fixture for every new AUTO route.

**Acceptance gate:** AUTO has official cell coordinates, source link, API/snapshot value, as-of evidence, calculation inputs/output, tolerance decision, and versions. No LLM-supplied numeric value enters the verdict.

### Gate 5: Release acceptance—gold regression and new-article parity

**Scope:** The complete frozen gold run plus a small new-article fixture suite.

**Acceptance gate:**
- Gold run is repeatable from versioned Registry, semantic standard, KOSIS snapshot, and code commit.
- Every Claim ends `AUTO` or a controlled, stage-specific `HOLD`.
- The same dynamic verifier processes an uploaded new article after Claim Split/12-slot parsing.
- Streamlit shows trace, official evidence, calculation, and actionable HOLD reason.

## Execution order

Start with Gate 0 only. Its deliverable is deterministic candidate/metadata snapshots and a two-run equality test—not a new 1,542-Claim execution. After Gate 0 passes, execute Gate 1 and report its stable admissibility partition before any candidate or Evidence work begins.
