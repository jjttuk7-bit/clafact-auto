from pathlib import Path

import pytest

from tools.run_multi_claim_group import main


def test_cli_refuses_more_than_twenty_cases_before_loading_files(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        main(
            [
                "--goldset",
                str(tmp_path / "missing-gold.csv"),
                "--registry",
                str(tmp_path / "missing-registry.jsonl"),
                "--source-registry",
                str(tmp_path / "missing-source.jsonl"),
                "--output",
                str(tmp_path / "result.csv"),
                "--limit",
                "21",
            ]
        )

    assert caught.value.code == 2
