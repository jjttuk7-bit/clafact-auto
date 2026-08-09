# OpenAI Function Calling Claim Extractor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an OpenAI Responses API Strict Function Calling Claim extractor selected by environment configuration, with HCX fallback only for technical failures.

**Architecture:** Keep `ClaimSchema` as the provider-neutral internal contract. Add an OpenAI-only strict tool payload that represents dynamic map slots as validated key/value arrays, convert it to `ClaimOutputPayload`, and select it through the existing extractor factory. The rest of the KOSIS/Python verification pipeline remains unchanged.

**Tech Stack:** Python 3.12+, Pydantic v2, `urllib.request`, pytest, Streamlit 1.57+.

---

### Task 1: OpenAI Strict Claim Tool Contract

**Files:**
- Create: `core/openai_claim_contract.py`
- Create: `tests/unit/test_openai_claim_contract.py`

**Step 1: Write the failing contract tests**

Add tests proving that:

```python
def test_openai_tool_is_strict_and_exposes_only_emit_claim():
    tool = openai_emit_claim_tool_definition()
    assert tool["type"] == "function"
    assert tool["name"] == "emit_claim"
    assert tool["strict"] is True
    assert tool["parameters"]["additionalProperties"] is False
    assert set(tool["parameters"]["required"]) == set(CLAIM_OUTPUT_FIELD_NAMES)


def test_openai_payload_converts_entry_arrays_to_internal_maps():
    payload = OpenAIClaimToolPayload.model_validate(valid_payload(
        dimension=[{"key": "sex", "value": "여성"}],
        comparison=[{"key": "type", "value": "YEAR_OVER_YEAR"}],
    ))
    claim = payload.to_claim()
    assert claim.dimension == {"sex": "여성"}
    assert claim.comparison == {"type": "YEAR_OVER_YEAR"}


def test_openai_payload_rejects_duplicate_map_keys():
    with pytest.raises(ValueError, match="DUPLICATE_SLOT_KEY"):
        OpenAIClaimToolPayload.model_validate(valid_payload(
            dimension=[{"key": "sex", "value": "여성"}, {"key": "sex", "value": "남성"}],
        )).to_claim()
```

Also cover empty arrays converting to `None`, nullable scalar fields, forbidden extra keys, and all nested entry objects using `additionalProperties: false`.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_openai_claim_contract.py -q`

Expected: FAIL because `core.openai_claim_contract` does not exist.

**Step 3: Implement the minimal strict contract**

Create:

```python
class SlotEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str
    value: str


class OpenAIClaimToolPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    # Same scalar fields as ClaimOutputPayload.
    dimension: list[SlotEntry] | None
    comparison: list[SlotEntry] | None
    condition: list[SlotEntry] | None

    def to_claim(self) -> ClaimSchema:
        # Reject duplicate keys, convert empty arrays to None, then validate
        # through ClaimOutputPayload before producing ClaimSchema.
```

Build a provider-specific tool definition in Responses API format:

```python
{
    "type": "function",
    "name": "emit_claim",
    "description": "Submit one parsed numerical news claim only.",
    "strict": True,
    "parameters": strict_schema,
}
```

Every object in the schema must set `additionalProperties: false`; every property must appear in `required`.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_openai_claim_contract.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/openai_claim_contract.py tests/unit/test_openai_claim_contract.py
git commit -m "feat: add strict OpenAI claim contract"
```

### Task 2: OpenAI Responses API Adapter

**Files:**
- Create: `core/openai_function_claim_extractor.py`
- Create: `tests/unit/test_openai_function_claim_extractor.py`

**Step 1: Write failing request and response tests**

Test the public pure functions first:

```python
def test_build_request_forces_one_emit_claim_call():
    request = build_openai_claim_request("2025년 고용률은 70%였다.", "gpt-5.6-luna")
    assert request["model"] == "gpt-5.6-luna"
    assert request["tool_choice"] == {"type": "function", "name": "emit_claim"}
    assert request["parallel_tool_calls"] is False
    assert request["tools"] == [openai_emit_claim_tool_definition()]


def test_parse_one_function_call():
    claim = parse_openai_emit_claim_response(valid_response())
    assert claim.indicator == "고용률"
    assert claim.parse_status == "AUTO_OK"


@pytest.mark.parametrize("payload", [missing_call(), two_calls(), wrong_function()])
def test_parse_rejects_invalid_function_envelope(payload):
    with pytest.raises(OpenAIContractError):
        parse_openai_emit_claim_response(payload)
```

Add tests for arguments supplied as a JSON string, malformed JSON, and a valid `HOLD` response.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_openai_function_claim_extractor.py -q`

Expected: FAIL because the adapter module does not exist.

**Step 3: Implement request, parser, and typed failures**

Use `POST https://api.openai.com/v1/responses` through `urllib.request`. Send only the sentence, system instructions, and the single strict tool. Parse exactly one output item where `type == "function_call"` and `name == "emit_claim"`.

Define errors:

```python
class OpenAIClaimExtractorError(RuntimeError): ...
class OpenAIConfigurationError(OpenAIClaimExtractorError): ...
class OpenAIAuthenticationError(OpenAIClaimExtractorError): ...
class OpenAITransientError(OpenAIClaimExtractorError): ...
class OpenAIContractError(OpenAIClaimExtractorError): ...
```

Map missing key to configuration error, HTTP 401/403 to authentication error, HTTP 429/5xx and timeout to transient error, and invalid Function envelopes to contract error. Do not include API keys or full provider payloads in exception messages.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_openai_function_claim_extractor.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/openai_function_claim_extractor.py tests/unit/test_openai_function_claim_extractor.py
git commit -m "feat: add OpenAI function claim extractor"
```

### Task 3: Settings, Provider Factory, and Technical Fallback

**Files:**
- Modify: `config/settings.py`
- Modify: `core/claim_extractor_factory.py`
- Create: `core/fallback_claim_extractor.py`
- Modify: `tests/unit/test_settings.py`
- Modify: `tests/unit/test_claim_extractor_factory.py`
- Create: `tests/unit/test_fallback_claim_extractor.py`

**Step 1: Write failing settings tests**

```python
def test_settings_load_openai_provider(monkeypatch):
    monkeypatch.setenv("CLAFACT_CLAIM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("CLAFACT_OPENAI_MODEL", "gpt-5.6-luna")
    settings = Settings()
    assert settings.claim_provider == "openai"
    assert settings.openai_api_key == "test-openai-key"
    assert settings.openai_model == "gpt-5.6-luna"
```

Run: `python -m pytest tests/unit/test_settings.py::test_settings_load_openai_provider -q`

Expected: FAIL because fields are missing.

**Step 2: Add the Settings fields and environment loading**

Add `claim_provider`, `openai_api_key`, and `openai_model` without changing existing HCX defaults for deployments that do not opt in.

Run: `python -m pytest tests/unit/test_settings.py -q`

Expected: PASS.

**Step 3: Write failing factory and fallback tests**

Prove:

- `openai` selects `OpenAIFunctionClaimExtractor`.
- `hcx` preserves the current structured/function modes.
- unsupported providers raise a stable configuration error.
- transient and contract failures call HCX exactly once.
- configuration/authentication failures do not fallback.
- a valid OpenAI `HOLD` Claim does not fallback.

Run: `python -m pytest tests/unit/test_claim_extractor_factory.py tests/unit/test_fallback_claim_extractor.py -q`

Expected: FAIL before implementation.

**Step 4: Implement minimal provider selection and fallback wrapper**

`FallbackClaimExtractor.extract()` should catch only `(OpenAITransientError, OpenAIContractError)`. It records `last_provider` as `openai`, `hcx`, or `unavailable` without modifying `ClaimSchema`.

**Step 5: Run focused and parser regression tests**

Run: `python -m pytest tests/unit/test_claim_extractor_factory.py tests/unit/test_fallback_claim_extractor.py tests/unit/test_claim_parser.py -q`

Expected: PASS.

**Step 6: Commit**

```bash
git add config/settings.py core/claim_extractor_factory.py core/fallback_claim_extractor.py tests/unit/test_settings.py tests/unit/test_claim_extractor_factory.py tests/unit/test_fallback_claim_extractor.py
git commit -m "feat: select OpenAI claim provider with safe fallback"
```

### Task 4: Streamlit Status and Deployment Configuration

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `.env.example`
- Modify: `tests/test_streamlit_app.py`
- Modify: `tests/test_deployment_config.py`

**Step 1: Run Streamlit reference discovery**

Run:

```powershell
python C:\Users\USER\.agents\skills\developing-with-streamlit\scripts\discover.py --project-dir D:\projects\services\archived\clafact-auto
```

Read the returned bundled `SKILL.md` and only the references it routes to for metrics/status display.

**Step 2: Write failing UI source tests**

Assert that the app displays:

- `OpenAI Function Calling` when `claim_provider == "openai"`.
- OpenAI configured/missing status based only on key presence.
- `HCX fallback` separately.
- actual provider after a single Claim extraction using the extractor's `last_provider`.

Run: `python -m pytest tests/test_streamlit_app.py tests/test_deployment_config.py -q`

Expected: FAIL because OpenAI UI/config support is absent.

**Step 3: Implement minimal status display**

Create the extractor once per single verification request, pass it into `parse_claim`, and display only the non-secret provider label. Keep error rendering generic and never print provider response bodies.

Update `.env.example`:

```ini
KOSIS_API_KEY=
HCX_API_KEY=
OPENAI_API_KEY=
CLAFACT_CLAIM_PROVIDER=hcx
CLAFACT_OPENAI_MODEL=gpt-5.6-luna
CLAFACT_HCX_EXTRACTION_MODE=structured_output
CLAFACT_LOG_LEVEL=INFO
```

**Step 4: Run UI and deployment tests**

Run: `python -m pytest tests/test_streamlit_app.py tests/test_deployment_config.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add app/streamlit_app.py .env.example tests/test_streamlit_app.py tests/test_deployment_config.py
git commit -m "feat: expose OpenAI claim provider status"
```

### Task 5: Full Regression and Safe Live Smoke Test

**Files:**
- Modify only if a failing regression demonstrates a defect in the new code.

**Step 1: Run the complete offline test suite**

Run: `python -m pytest -q`

Expected: all tests PASS without external network access.

**Step 2: Verify secrets are not tracked or printed**

Run: `git status --short` and `git diff --check`.

Expected: `.env` is not listed; no whitespace errors.

**Step 3: Run an opt-in live OpenAI smoke test**

Using the configured local environment only, submit:

```text
2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.
```

Validate only the returned Claim contract and Provider label. Do not print the key or raw response. If local `OPENAI_API_KEY` is unavailable, record the live smoke test as skipped rather than weakening offline tests.

**Step 4: Run the existing deterministic pipeline regression**

Run:

```powershell
python -m pytest tests/goldset/test_cpi_growth_e2e.py tests/unit/test_batch_verifier.py -q
```

Expected: PASS with KOSIS official values still coming only from Snapshot/API and calculations still performed by Python.

**Step 5: Final commit if verification required fixes**

```bash
git add <only-files-changed-for-verified-fixes>
git commit -m "fix: complete OpenAI claim provider integration"
```
