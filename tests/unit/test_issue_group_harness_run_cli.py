from __future__ import annotations

import csv
from datetime import date
import json

import tools.run_issue_group_harness as cli
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="parsed",
            source_sentence=source_sentence,
            indicator="취업자 수",
            value=100000,
            unit="명",
            time="2025-01",
            frequency="M",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


def test_run_group_cli_executes_only_requested_context_slice(tmp_path, monkeypatch) -> None:
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(
        "\n".join(json.dumps(_baseline(claim_id)) for claim_id in ("C-001", "C-002")) + "\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text(
        "\n".join(
            record.model_dump_json()
            for record in (_record("C-001", "1"), _record("C-002", "2"))
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "create_claim_extractor", lambda settings: _Extractor())
    output = tmp_path / "output"

    exit_code = cli.main(
        [
            "run-group",
            str(baseline),
            str(registry_path),
            str(output),
            "--group",
            "CONTEXT",
            "--limit",
            "1",
            "--run-id",
            "context-test-001",
        ]
    )

    assert exit_code == 0
    with (output / "runs" / "context-test-001.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    assert rows[0]["Claim번호"] == "C-001"
    assert rows[0]["개선판정"] == "IMPROVED"
    detail = [
        json.loads(line)
        for line in (output / "runs" / "context-test-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert detail[0]["official_lookup_attempted"] is False


def _record(claim_id: str, sentence_id: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A-001",
        sentence_id=sentence_id,
        article_published_at=date(2025, 2, 1),
        source_ref="test",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=f"취업자는 {sentence_id}0만 명이다.",
            value=int(sentence_id) * 100000,
            unit="명",
            parse_status="HOLD",
            parse_reason="CONTEXT_REQUIRED",
        ),
    )


def _baseline(claim_id: str) -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": claim_id[-1],
        "parent_claim_id": claim_id,
        "claim_id": claim_id,
        "source_sentence": "취업자는 증가했다.",
        "terminal_status": "HUMAN_REVIEW",
        "reason_code": "CONTEXT_REQUIRED",
        "claim": {"claim_id": claim_id},
        "slot_audit": {"entries": []},
        "stage_results": [],
        "official_resolution": None,
    }
