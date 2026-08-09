# CLAFACT-AUTO PHASE 0–2 Implementation Plan

> **For Codex:** Execute this plan task-by-task with test-first development.

**Goal:** Establish the Python foundation, strict Pydantic data contracts, and read-only loaders for semantic-standard and KOSIS catalog assets.

**Architecture:** Raw source files under `news_data/` remain untouched. Adapter functions load JSON seed data and catalog metadata from the application-owned `data/` directories, normalize fields into Pydantic contracts, and expose deterministic lookup APIs. Tests use isolated temporary fixture files.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, standard-library logging and JSON.

---

### Task 1: PHASE 0 project foundation

**Files:**
- Create: `pyproject.toml`, `.env.example`, `config/settings.py`, `config/__init__.py`, `tests/conftest.py`
- Test: `tests/unit/test_settings.py`

1. Write failing tests for environment-backed settings defaults and required version fields.
2. Run `pytest tests/unit/test_settings.py -v` and observe the import failure.
3. Implement the smallest settings module and pytest configuration.
4. Run the focused test, then `pytest`.

### Task 2: PHASE 1 schemas

**Files:**
- Create: `schemas/__init__.py`, `schemas/claim.py`, `schemas/concept.py`, `schemas/candidate.py`, `schemas/evidence.py`, `schemas/verdict.py`
- Test: `tests/unit/test_schemas.py`

1. Write failing tests for validation of every pipeline contract and version-bearing verdicts.
2. Run `pytest tests/unit/test_schemas.py -v` and observe the import failure.
3. Implement immutable-style Pydantic v2 contracts with constrained literal status values.
4. Run focused and full tests.

### Task 3: PHASE 2 data assets and loaders

**Files:**
- Create: `data/semantic_standard/seed_concepts.json`, `data/kosis_catalog/catalog.json`, `core/__init__.py`, `core/data_loader.py`
- Test: `tests/unit/test_data_loader.py`

1. Write failing tests for deterministic loading, normalization of delimited/list metadata fields, and malformed input rejection.
2. Run `pytest tests/unit/test_data_loader.py -v` and observe the import failure.
3. Implement read-only loaders and catalog normalizer; do not modify `news_data/`.
4. Run focused and full tests.

### Task 4: Verification

1. Run `pytest tests/unit -v`.
2. Run `pytest -v`.
3. Confirm `news_data/` remains unchanged with a file hash comparison from before/after the loader test.

