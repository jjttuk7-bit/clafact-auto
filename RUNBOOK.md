# CLAFACT-AUTO Runbook

## Prerequisites

- Python 3.12 or later
- KOSIS and HCX keys supplied only through environment variables or `.env`

```ini
KOSIS_API_KEY=...
HCX_API_KEY=...
CLAFACT_LOG_LEVEL=INFO
```

Never commit `.env` or print either key in logs.

## Install and verify

```powershell
python -m pip install -e ".[dev,app]"
python -m pytest -q
```

## Run MVP

```powershell
streamlit run app/streamlit_app.py
```

Enter a news sentence and its article date (`YYYY-MM-DD`). The app displays the parsed Claim, candidates, evidence coordinate, official value status, deterministic verdict, and review-console payload.

## Route policy

- `AUTO`: candidate, evidence coordinate, article-time official value, and deterministic calculation all succeed.
- `HOLD`: missing article date, ambiguous candidate/coordinate, unavailable official value, post-article revision, or API failure.
- `HUMAN_REVIEW`: use when a provider/parser marks the Claim as needing human interpretation.

## Snapshot operations

Snapshots are immutable JSON evidence under `data/kosis_snapshots/`; each saved API response records request parameters, retrieval time, and a SHA-256 response hash. Do not edit a snapshot in place; add a new versioned snapshot.
