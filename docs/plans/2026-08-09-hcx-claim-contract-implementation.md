# HCX Claim Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce all 12 nullable semantic slots in HCX Structured Outputs and add a single, non-dispatching `emit_claim` Function Calling alternative while retaining Python control of KOSIS retrieval and verdicts.

**Architecture:** A new provider-neutral contract module owns one canonical Claim JSON Schema and the `emit_claim` tool definition. Structured Output and Function Calling request builders reuse that schema, while both response paths end in strict `ClaimSchema` validation. The tool-call parser only decodes a Claim envelope and cannot execute KOSIS, calculation, or verdict functions.

**Tech Stack:** Python 3.12+, Pydantic v2, urllib, pytest

---

### Task 1: Canonical 12-slot JSON Schema

**Files:**
- Create: `core/claim_output_contract.py`
- Create: `tests/unit/test_claim_output_contract.py`

**Step 1: Write failing contract tests**

Test that all 12 semantic slot names occur in `properties` and `required`, all optional fields explicitly include `null`, mapping slots use object-or-null with string `additionalProperties`, and extra properties are forbidden.

**Step 2: Run test to verify RED**

Run: `python -m pytest tests/unit/test_claim_output_contract.py -q`
Expected: FAIL because `core.claim_output_contract` does not exist.

**Step 3: Implement the minimal canonical schema**

Add `SEMANTIC_SLOT_NAMES`, `CLAIM_OUTPUT_FIELD_NAMES`, and `claim_output_json_schema()`. Return a deep copy so callers cannot mutate the shared contract.

**Step 4: Run test to verify GREEN**

Run: `python -m pytest tests/unit/test_claim_output_contract.py -q`
Expected: PASS.

**Step 5: Commit**

Commit tests and the contract module together.

### Task 2: Apply shared schema to HCX Structured Output

**Files:**
- Modify: `core/hcx_claim_extractor.py`
- Modify: `tests/unit/test_hcx_prompt.py`

**Step 1: Write failing request contract tests**

Add a test for `build_structured_claim_request()` proving it contains the shared schema, contains all required Claim keys, and contains neither `tools` nor `toolChoice`.

**Step 2: Run test to verify RED**

Run: `python -m pytest tests/unit/test_hcx_prompt.py -q`
Expected: FAIL because the request builder and full schema are absent.

**Step 3: Implement the request builder**

Replace the inline partial schema with `claim_output_json_schema()`. Preserve `temperature=0`, the HCX-007 endpoint, and Pydantic response validation.

**Step 4: Run test to verify GREEN**

Run: `python -m pytest tests/unit/test_hcx_prompt.py tests/unit/test_claim_parser.py -q`
Expected: PASS.

**Step 5: Commit**

Commit the Structured Output integration.

### Task 3: Add the constrained emit_claim Function Calling path

**Files:**
- Create: `core/hcx_function_claim_extractor.py`
- Modify: `core/claim_output_contract.py`
- Modify: `tests/unit/test_claim_output_contract.py`
- Create: `tests/unit/test_hcx_function_claim_extractor.py`

**Step 1: Write failing tool contract and parser tests**

Cover the exact tool name, shared parameters schema, forced `toolChoice`, absence of `responseFormat` and `thinking`, valid response parsing, and rejection of missing/multiple calls, wrong names/types, non-object arguments, missing fields, extra fields, and bad field types.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_claim_output_contract.py tests/unit/test_hcx_function_claim_extractor.py -q`
Expected: FAIL because the tool definition and extractor do not exist.

**Step 3: Implement minimal Function Calling support**

Add `emit_claim_tool_definition()`, `build_function_claim_request()`, `parse_emit_claim_tool_call()`, and `HcxFunctionClaimExtractor`. The parser validates only `emit_claim.arguments` through `ClaimSchema`; it never dynamically dispatches a Python callable.

**Step 4: Run tests to verify GREEN**

Run the two targeted test modules and confirm all pass.

**Step 5: Commit**

Commit the Function Calling boundary.

### Task 4: Authority-boundary audit and documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/CLAFACT_AUTO_구현결과_상세정리.txt`
- Test: `tests/unit/test_hcx_function_claim_extractor.py`

**Step 1: Add an authority-boundary test**

Assert that the HCX request exposes exactly one function name, `emit_claim`, and no function names for KOSIS, calculation, matching, or verdict operations.

**Step 2: Run the test and verify expected RED if not already enforced**

Run the single authority test.

**Step 3: Document the two mutually exclusive HCX modes**

State that Structured Outputs are the default, Function Calling is an optional Claim envelope, and all downstream verification remains Python-controlled.

**Step 4: Run focused and full verification**

Run:

`python -m pytest tests/unit/test_claim_output_contract.py tests/unit/test_hcx_prompt.py tests/unit/test_hcx_function_claim_extractor.py -q`

`python -m pytest -q`

`git diff --check`

Expected: all tests pass, no whitespace errors, and repository search finds no downstream HCX tools.

**Step 5: Commit**

Commit documentation and the final authority test.

