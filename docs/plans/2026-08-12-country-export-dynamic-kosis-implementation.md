# Country Export Dynamic KOSIS Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Parse raw country dimensions and resolve a country-export Claim to an auditable KOSIS coordinate without unsafe Top-1 selection.

**Architecture:** Add one pure Claim-dimension normalizer shared by Hard Guard, catalog query construction, and Evidence Resolver. Preserve official item/member codes and use deterministic currency scaling before the existing verdict engine.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, KOSIS OpenAPI snapshots

---

### Task 1: Normalize imported raw dimensions

**Files:**
- Create: `core/claim_dimensions.py`
- Modify: `core/hard_guard.py`, `core/evidence_resolver.py`, `core/catalog_discovery.py`
- Test: `tests/unit/test_claim_dimensions.py`, `tests/unit/test_catalog_search_and_hard_guard.py`, `tests/unit/test_evidence_resolver.py`

1. Write failing tests for `{"raw":"{\"교역상대국\":[\"미국\"]}"}`.
2. Verify Hard Guard currently rejects the official `미국` member.
3. Implement strict JSON-object/list extraction with plain-string fallback.
4. Use the shared values at all three pipeline boundaries.
5. Run focused tests.

### Task 2: Add deterministic dollar scaling

**Files:**
- Modify: `core/unit_normalizer.py`
- Test: `tests/unit/test_unit_normalizer.py`

1. Write failing tests for 천달러/천불 to 달러.
2. Add aliases and scale factors.
3. Verify incompatible currencies remain rejected.

### Task 3: Add official country-export search vocabulary

**Files:**
- Modify: `data/semantic_standard/concept_seed_v1.json`
- Test: `tests/unit/test_concept_seed_v1.py`

1. Require `국가별 수출액 수입액` in export search terms.
2. Verify existing total-export search remains first.

### Task 4: Freeze official metadata and run the real Claim

**Files:**
- Create: `data/kosis_snapshots/export_by_country_2024_v1.json`
- Create: `artifacts/export_by_country_20260812/e2e_result.json`

1. Store official table, item, country member, period metadata, value, and last-change date.
2. Run `A00312_4` through the unchanged dynamic batch entry point.
3. Require coordinate `DT_1R11006_FRM101 / 13103103829T1 / 13102103829E.US / 2024`.
4. Require `AS_OF_UNAVAILABLE` when the final row postdates the article.
5. Run unit, integration, goldset, and diff checks.