# KOSIS Direct Gateway Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Provide an HTTP Gateway that runs the existing direct KOSIS official-evidence engine outside Streamlit Cloud.

**Architecture:** A small FastAPI app receives a structured Claim and article date, invokes the existing `OfficialEvidenceService`, and returns the Verdict, candidates, and safe diagnostics. Streamlit selects the Gateway only when its URL is configured; direct local execution remains the fallback.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, existing KOSIS Core Engine, Streamlit.

---

### Task 1: Gateway request and response contract

**Files:**
- Create: `schemas/official_gateway.py`
- Test: `tests/unit/test_official_gateway.py`

1. Write a failing test for Claim/date validation and safe response serialization.
2. Implement Pydantic request/response schemas without credential fields.
3. Run the unit test.

### Task 2: Gateway application

**Files:**
- Create: `gateway/official_gateway_app.py`
- Test: `tests/integration/test_official_gateway.py`

1. Write a failing test with an injected official-evidence service.
2. Implement `POST /verify`, including stable operational error conversion.
3. Run the integration test.

### Task 3: Streamlit Gateway client selection

**Files:**
- Create: `core/official_gateway_client.py`
- Modify: `config/settings.py`
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_official_gateway_client.py`

1. Write failing tests for URL-configured Gateway selection and safe transport HOLD.
2. Implement an adapter matching the Core service result contract.
3. Run Streamlit and client tests.

### Task 4: Deployment contract and verification

**Files:**
- Modify: `README.md`
- Create: `gateway/README.md`
- Test: `tests/integration/test_official_gateway.py`

1. Document Gateway-only KOSIS key configuration and local launch.
2. Execute a local direct KOSIS employment Claim through the Gateway.
3. Run focused regression tests and commit the feature branch.
