from core.progress_csv import ProgressCsvRecorder, ProgressRecord


def test_progress_csv_uses_excel_compatible_utf8_and_korean_headers(tmp_path) -> None:
    path = tmp_path / "00_progress.csv"
    recorder = ProgressCsvRecorder(path)

    recorder.append(
        ProgressRecord(
            work_number="작업 1",
            work_name="단계별 결과 저장",
            status="완료",
            processed_count=1542,
            passed_count=1542,
            stopped_count=0,
            test_result="3개 통과",
            remaining_issue="없음",
            next_work="작업 2",
            recorded_at="2026-08-22T10:30:00+09:00",
        )
    )

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("작업번호,작업명,상태")
    assert "작업 1,단계별 결과 저장,완료,1542,1542,0" in text

