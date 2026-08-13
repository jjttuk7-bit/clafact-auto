"""Safe natural-language rendering for deterministic CLAFACT verdicts."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from core.openai_function_claim_extractor import OPENAI_RESPONSES_URL, OPENAI_TIMEOUT_SECONDS
from schemas.verdict import VerdictSchema
from schemas.verdict_explanation import VerdictExplanationSchema


_KOREAN_CONCLUSIONS = {
    "MATCH": "일치",
    "MISMATCH": "불일치",
    "UNDETERMINED": "판정 불가",
}


def build_template_explanation(verdict: VerdictSchema) -> VerdictExplanationSchema:
    """Return a deterministic Korean explanation from the immutable verdict."""
    conclusion = _KOREAN_CONCLUSIONS[verdict.verdict]
    if verdict.verdict == "MATCH":
        summary = "기사 주장과 KOSIS 공식값 계산 결과가 허용 오차 안에서 일치합니다."
        detail = "기사값과 KOSIS 공식 근거로 Python이 계산한 값의 차이가 허용 오차 이내입니다."
        next_action = None
    elif verdict.verdict == "MISMATCH":
        summary = "기사 주장과 KOSIS 공식값 계산 결과가 허용 오차를 벗어나 불일치합니다."
        detail = "기사값과 KOSIS 공식 근거로 Python이 계산한 값의 차이가 허용 오차를 초과했습니다."
        next_action = "기사의 수치, 기준시점, 비교 기준을 다시 확인하세요."
    else:
        summary = "공식 근거 또는 필수 검증 조건이 충분하지 않아 판정할 수 없습니다."
        if verdict.reason_code == "PUBLICATION_FETCH_FAILED":
            detail = "KOSIS 공식 공표정보 조회가 외부 연결 오류로 완료되지 않았습니다."
            next_action = "공표정보 API 연결을 확인한 뒤 다시 시도하세요."
        else:
            detail = f"판정 불가 사유 코드: {verdict.reason_code}."
            next_action = "KOSIS 표·항목·기준시점 또는 기사 표현을 확인한 뒤 재검토하세요."
    return VerdictExplanationSchema(
        source="TEMPLATE",
        conclusion=conclusion,
        summary=summary,
        detail=detail,
        next_action=next_action,
    )


def explain_verdict_with_openai(
    verdict: VerdictSchema,
    *,
    api_key: str | None,
    model: str,
) -> VerdictExplanationSchema:
    """Ask OpenAI only to paraphrase a fixed verdict; fall back at the caller on failure."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY_NOT_CONFIGURED")
    template = build_template_explanation(verdict)
    tool = {
        "type": "function",
        "name": "emit_verdict_explanation",
        "description": "Return Korean explanatory prose only. Never recalculate, change, or add facts.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "detail": {"type": "string"},
                "next_action": {"type": ["string", "null"]},
            },
            "required": ["summary", "detail", "next_action"],
            "additionalProperties": False,
        },
    }
    fixed_context = {
        "conclusion": template.conclusion,
        "summary": template.summary,
        "detail": template.detail,
        "next_action": template.next_action,
    }
    request_body = {
        "model": model,
        "instructions": (
            "Explain only the supplied deterministic Korean verification result. "
            "Do not produce numbers, dates, table IDs, new evidence, or a different conclusion. "
            "Call emit_verdict_explanation exactly once."
        ),
        "input": json.dumps(fixed_context, ensure_ascii=False),
        "tools": [tool],
        "tool_choice": {"type": "function", "name": "emit_verdict_explanation"},
        "parallel_tool_calls": False,
    }
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(request_body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=OPENAI_TIMEOUT_SECONDS) as response:
        payload: Any = json.loads(response.read())
    calls = [item for item in payload.get("output", []) if item.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != "emit_verdict_explanation":
        raise ValueError("ONE_VERDICT_EXPLANATION_CALL_REQUIRED")
    arguments = json.loads(calls[0]["arguments"])
    if not isinstance(arguments, dict):
        raise ValueError("INVALID_VERDICT_EXPLANATION")
    if any(character.isdigit() for value in arguments.values() if isinstance(value, str) for character in value):
        raise ValueError("NUMERIC_LLM_EXPLANATION_REJECTED")
    return VerdictExplanationSchema(
        source="LLM",
        conclusion=template.conclusion,
        summary=arguments["summary"],
        detail=arguments["detail"],
        next_action=arguments["next_action"],
    )


def explain_verdict(verdict: VerdictSchema, *, api_key: str | None, model: str) -> VerdictExplanationSchema:
    """Use optional AI phrasing without ever changing the deterministic outcome."""
    try:
        return explain_verdict_with_openai(verdict, api_key=api_key, model=model)
    except Exception:
        return build_template_explanation(verdict)
