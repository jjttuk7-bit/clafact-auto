# KOSIS Direct Gateway Design

## Goal

Keep the existing Claim pipeline and execute the official KOSIS Catalog,
metadata, value, and publication calls from a Gateway runtime instead of the
Streamlit Cloud runtime.

## Chosen approach

The Gateway exposes one authenticated `POST /verify` endpoint. It receives a
structured Claim and article date, builds the existing `OfficialEvidenceService`,
and returns its Verdict plus safe Catalog diagnostics. The KOSIS key remains
only in the Gateway environment. Streamlit uses `CLAFACT_OFFICIAL_GATEWAY_URL`
when configured; otherwise it retains the local Core Engine path.

## Rejected approaches

- Static Claim/Profile result: violates direct KOSIS verification.
- Browser-side KOSIS calls: exposes credentials and is not auditable.
- Altering Hard Guard to accept missing metadata: creates unsupported AUTO.

## Failure contract

The Gateway never returns API keys or raw KOSIS payloads. Transport failure is
returned as a stable stage/reason code, allowing Streamlit to display an
explicit HOLD rather than `NO_HARD_GUARD_CANDIDATE`.
