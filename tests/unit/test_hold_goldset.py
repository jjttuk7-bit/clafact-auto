from __future__ import annotations

import json

from core.hold_goldset import review_hold_record, select_hold_sample, write_ai_provisional_reviews, write_hold_goldset


def _record(claim_id: str, reason: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "route_status": "HOLD",
        "reason_code": reason,
        "source_sentence": f"sentence {claim_id}",
        "execution_trace": {"events": []},
    }


def test_select_hold_sample_is_deterministic_and_stratified() -> None:
    records = [
        _record("A_1", "PARSER"), _record("A_2", "PARSER"), _record("A_3", "PARSER"),
        _record("B_1", "COORD"), _record("B_2", "COORD"),
        {"claim_id": "auto", "route_status": "AUTO"},
    ]
    quotas = {"PARSER": 2, "COORD": 1}

    holds, first = select_hold_sample(records, quotas, seed="fixed")
    _, second = select_hold_sample(records, quotas, seed="fixed")

    assert len(holds) == 5
    assert [row["claim_id"] for row in first] == [row["claim_id"] for row in second]
    assert [row["reason_code"] for row in first].count("PARSER") == 2
    assert [row["reason_code"] for row in first].count("COORD") == 1


def test_write_hold_goldset_creates_pending_review_artifacts(tmp_path) -> None:
    input_path = tmp_path / "results.jsonl"
    records = [_record("A_1", "PARSER"), _record("B_1", "COORD")]
    input_path.write_text("\n".join(json.dumps(row) for row in records) + "\n", encoding="utf-8")

    output_dir = tmp_path / "goldset"
    report = write_hold_goldset(input_path, output_dir, quotas={"PARSER": 1, "COORD": 1})

    assert report["hold_population_count"] == 2
    assert report["sample_count"] == 2
    sample = [json.loads(line) for line in (output_dir / "review_sample.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sample[0]["review"]["review_status"] == "PENDING"
    assert (output_dir / "LABELING_GUIDE.md").exists()
    assert (output_dir / "review_sample.csv").exists()


def test_review_marks_foreign_statistic_as_not_kosis_verifiable() -> None:
    review = review_hold_record({
        "claim_id": "foreign_1",
        "reason_code": "AMBIGUOUS_MARGIN",
        "concept": {"canonical_name": "소비자물가"},
        "source_sentence": "미 노동부가 지난달 소비자물가지수(CPI)가 2.3% 상승했다고 밝혔다.",
    })

    assert review["automation_feasibility"] == "NOT_AUTO_VERIFIABLE"
    assert review["primary_root_cause"] == "KOSIS_OUT_OF_SCOPE"
    assert review["review_status"] == "AI_PROVISIONAL_REVIEWED"


def test_write_ai_provisional_reviews_preserves_source_and_labels_rows(tmp_path) -> None:
    source = tmp_path / "sample.jsonl"
    source.write_text(json.dumps(_record("foreign_1", "AMBIGUOUS_MARGIN")) + "\n", encoding="utf-8")

    output_dir = tmp_path / "reviewed"
    report = write_ai_provisional_reviews(source, output_dir)

    assert report["reviewed_count"] == 1
    reviewed = json.loads((output_dir / "review_sample_ai_provisional.jsonl").read_text(encoding="utf-8"))
    assert reviewed["review"]["review_status"] == "AI_PROVISIONAL_REVIEWED"
    assert source.exists()
