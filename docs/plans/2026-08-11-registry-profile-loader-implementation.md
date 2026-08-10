# Registry Profile Loader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Load Claim Registry JSONL and verification-profile JSON with strict validation and auditable input errors.

**Architecture:** Define a versioned VerificationProfile schema with exact official coordinate fields and supported calculation types. The Registry loader validates each JSONL row independently and returns valid records plus row-level errors; the Profile loader rejects duplicate IDs, missing version metadata, and invalid coordinates before execution begins.

**Tech Stack:** Python 3.12+, Pydantic v2, stdlib JSON, pytest.

---

### Task 1: Define the versioned verification-profile contract

**Files:**
- Create: `schemas/verification_profile.py`
- Create: `tests/unit/test_verification_profile_loader.py`

**Step 1: Write failing schema tests**

Cover a valid direct-value profile, unsupported calculation type, and missing version fields.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py -q`
Expected: FAIL because schema and loader do not exist.

**Step 3: Implement the minimal schema**

Require profile ID, claim key, calculation type, official coordinate values, and all project version fields.

**Step 4: Verify focused tests pass**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py -q`
Expected: PASS.

### Task 2: Add strict Profile JSON loading

**Files:**
- Create: `core/verification_profile_loader.py`
- Modify: `tests/unit/test_verification_profile_loader.py`

**Step 1: Write failing loader tests**

Cover a valid `profiles` document, duplicate profile IDs, and malformed entries.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py -q`
Expected: FAIL before loader implementation.

**Step 3: Implement strict loading**

Validate the document version, reject duplicate IDs, and return only typed profiles.

**Step 4: Verify focused tests pass**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py -q`
Expected: PASS.

### Task 3: Add Registry JSONL loading with row-level errors

**Files:**
- Create: `core/claim_registry_loader.py`
- Create: `tests/unit/test_claim_registry_loader.py`

**Step 1: Write failing tests**

Cover valid Registry rows, duplicate `(article_id, sentence_id)` keys, malformed JSON, and invalid Claim fields.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_claim_registry_loader.py -q`
Expected: FAIL because loader does not exist.

**Step 3: Implement the minimal loader**

Return typed valid records and typed row-level errors; never silently drop input.

**Step 4: Verify and commit**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py tests/unit/test_claim_registry_loader.py -q`

Run: `python -m pytest -q`

```powershell
git add schemas/verification_profile.py core/verification_profile_loader.py core/claim_registry_loader.py tests/unit/test_verification_profile_loader.py tests/unit/test_claim_registry_loader.py docs/plans/2026-08-11-registry-profile-loader-implementation.md
git commit -m "feat: add registry and profile loaders"
```
