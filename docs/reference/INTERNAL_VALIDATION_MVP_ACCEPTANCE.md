# Internal Validation MVP Acceptance

## Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Execution contract | Conditional | Declared 1,532; available structured 1,531; one source record remains externally missing. |
| Full structured batch | Passed | 1,531 results, deterministic `concepts.json`, and an error-isolation rerun in `artifacts/internal_validation_mvp_full_20260811/`. |
| Profile safety | Passed | Only immutable KOSIS snapshot-backed Profiles may be selected; unresolved scope stays `HOLD`. |
| Per-record isolation | Passed | Unexpected processing errors produce `BATCH_RECORD_ERROR` and do not stop the batch. |
| Operator review | Passed | The Streamlit panel reads persisted report/results/queue, filters Profile reasons, and offers CSV/XLSX downloads. |
| Automated checks | Passed | Goldset, full pytest, and browser smoke are recorded in the runbook. |

## Release decision

The MVP is suitable for internal operation on the 1,531 supplied structured Claims. It is not eligible to claim a complete 1,532-Claim acceptance until the externally missing source record is supplied, loaded, and included in a new reconciled run.

The birth-count snapshot was reviewed but intentionally not registered as a production Profile: its stored `LST_CHN_DE` values are after the affected article dates, so it cannot prove article-time availability.

