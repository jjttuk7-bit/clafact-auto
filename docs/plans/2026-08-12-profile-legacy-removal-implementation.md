# Profile Legacy Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the standard CLAFACT-AUTO service exclusively 12-slot dynamic KOSIS based.

**Architecture:** Remove unreferenced Profile-only modules and pilot tooling. Rename the Streamlit operator queue to generic review terminology. Keep the standard batch runner unchanged except for replacement of stale tests.

**Tech Stack:** Python, Streamlit, pytest.

---

### Task 1: Prove standard execution is Profile-free
- Test: `tests/unit/test_run_e2e_batch.py`
- Replace the legacy registered-profile test with a dynamic KOSIS invocation contract.

### Task 2: Remove dead Profile-only code
- Delete Profile pilot commands, Profile loaders, Profile-first resolver, evidence service, schemas, and their tests only after `rg` confirms no imports.

### Task 3: Rename UI review queue
- Modify `app/streamlit_app.py`
- Replace profile-specific queue label/download naming with generic review queue.

### Task 4: Verify
- Run `rg` for Profile imports in standard app/core/tools paths.
- Run unit tests and report unrelated failures separately.
