# Internal Validation MVP Acceptance

## Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Execution contract | Accepted | Owner-approved operational scope is the 1,531 supplied structured Claims. The historical declaration of 1,532 remains reconciled without creating a synthetic Claim. |
| Full structured batch | Passed | 1,531 results, deterministic `concepts.json`, an error-isolation rerun, and a CPI Profile rerun (AUTO 5 / HOLD 1,526) in `artifacts/internal_validation_mvp_full_20260811/`. |
| Profile safety | Passed | Employment and monthly total CPI Profiles cite immutable KOSIS snapshots; unproven percentages and unresolved scope stay `HOLD`. |
| Per-record isolation | Passed | Unexpected processing errors produce `BATCH_RECORD_ERROR` and do not stop the batch. |
| Operator review | Passed | The Streamlit panel reads persisted report/results/queue, filters Profile reasons, and offers CSV/XLSX downloads. |
| Automated checks | Passed | Goldset, full pytest, and browser smoke are recorded in the runbook. |

## Release decision

The MVP is suitable for internal operation on the 1,531 supplied structured Claims. The owner approved excluding the one externally missing record from this MVP acceptance scope; if it is later supplied, it must be loaded and reconciled in a new run rather than synthesized.

The birth-count snapshot was reviewed but intentionally not registered as a production Profile: its stored `LST_CHN_DE` values are after the affected article dates, so it cannot prove article-time availability.
