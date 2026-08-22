"""Human-readable CSV progress ledger for the final completion run."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProgressRecord:
    work_number: str
    work_name: str
    status: str
    processed_count: int
    passed_count: int
    stopped_count: int
    test_result: str
    remaining_issue: str
    next_work: str
    recorded_at: str


_HEADERS = {
    "work_number": "작업번호",
    "work_name": "작업명",
    "status": "상태",
    "processed_count": "처리수",
    "passed_count": "통과수",
    "stopped_count": "중단수",
    "test_result": "시험결과",
    "remaining_issue": "남은문제",
    "next_work": "다음작업",
    "recorded_at": "기록시각",
}


class ProgressCsvRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: ProgressRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(_HEADERS.values()))
            if write_header:
                writer.writeheader()
            writer.writerow(
                {_HEADERS[key]: value for key, value in asdict(record).items()}
            )

