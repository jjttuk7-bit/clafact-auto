from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CONTRACT = ROOT / "CLAFACT_AUTO_EXECUTION_CONTRACT.md"


def test_agents_requires_execution_contract_before_project_rules() -> None:
    agents = AGENTS.read_text(encoding="utf-8")

    contract_reference = agents.index("CLAFACT_AUTO_EXECUTION_CONTRACT.md")
    project_purpose = agents.index("## 프로젝트 목적")

    assert contract_reference < project_purpose


def test_execution_contract_requires_direct_official_api_pipeline() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    required_rules = (
        "KOSIS Catalog API Search",
        "KOSIS Official Metadata API",
        "KOSIS Official Value API",
        "Official Publication Information Lookup",
        "공식 조회를 실제로 시도했다",
        "Python 결정론적 함수",
    )

    assert all(rule in contract for rule in required_rules)


def test_execution_contract_forbids_verdict_without_official_lookup() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    assert "공식 조회를 수행하지 않은 상태" in contract
    assert "조회를 수행하지 않고 등록 여부만으로" in contract

