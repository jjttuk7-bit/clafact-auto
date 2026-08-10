# Claim Result Download Design

## Goal

Allow a user to download the complete result of one on-screen claim verification as both a machine-readable JSON artifact and a review-ready XLSX workbook.

## Scope

Two download controls appear immediately after the single-claim verdict and review-console payload. They are rendered only after a verdict exists.

- **JSON:** the canonical `VerdictSchema` data, including the Claim, evidence cells and values, deterministic calculated value, decision, version fields, and execution trace.
- **XLSX:** three sheets: `Summary`, `Evidence Cells`, and `Execution Trace`. It contains the same decision-relevant information in reviewer-friendly columns.

The button payloads are generated in memory for the current Streamlit rerun. Nothing is written to the app server, source registry, KOSIS snapshots, or user data directories. Credentials and raw API responses are never represented in either artifact.

## Architecture

Add a small pure exporter module that converts an existing `VerdictSchema` to JSON bytes and XLSX bytes. Reuse the project’s existing `openpyxl` dependency and the same trace/evidence schemas already shown in the UI. `app/streamlit_app.py` only calls the exporters and renders two `st.download_button` controls; it does not contain workbook formatting logic.

## Error handling and tests

The exporter accepts only validated verdict contracts. Empty evidence or trace fields generate valid sheets with headers and no rows. Unit tests validate JSON round-trip data, workbook sheet names, and evidence/trace rows. A focused Streamlit source test asserts both download control labels and filenames are wired to the single-claim result area.
