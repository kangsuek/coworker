"""JSON 파싱 + 4단계 폴백 체인 (F-001a ~ F-001c).

0단계: CLI --output-format json 래퍼 처리 (result 필드 추출)
1단계: json.loads() -> Pydantic 검증
2단계: 중괄호 카운팅으로 JSON 블록 추출 -> 재파싱 (다중 중첩 지원)
3단계: Solo 폴백
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.models.schemas import ClassificationResult


def _extract_json_objects(text: str) -> list[str]:
    """중괄호 카운팅으로 JSON 객체 후보 문자열 추출.

    정규식과 달리 임의 깊이의 중첩 JSON을 정확히 추출한다.
    """
    results: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                results.append(text[start : i + 1])
                start = -1
    return results


def parse_classification(raw_output: str) -> ClassificationResult:
    """CLI 출력을 ClassificationResult로 변환. 4단계 폴백."""
    # 0단계: CLI --output-format json 래퍼 처리
    # {"type":"result","subtype":"success","result":"<escaped json 또는 dict>"}
    try:
        wrapper = json.loads(raw_output)
        if isinstance(wrapper, dict) and "result" in wrapper:
            result_val = wrapper["result"]
            if isinstance(result_val, str):
                # result 필드가 escape된 JSON 문자열이면 raw_output을 교체
                raw_output = result_val
            elif isinstance(result_val, dict):
                try:
                    return ClassificationResult(**result_val)
                except ValidationError:
                    pass
    except json.JSONDecodeError:
        pass

    # 1단계 (F-001a): 직접 JSON 파싱 + Pydantic 검증
    try:
        data = json.loads(raw_output)
        return ClassificationResult(**data)
    except (json.JSONDecodeError, ValidationError):
        pass

    # 2단계 (F-001b): 중괄호 카운팅으로 JSON 블록들 추출, 각각 파싱 시도
    for candidate in _extract_json_objects(raw_output):
        try:
            data = json.loads(candidate)
            return ClassificationResult(**data)
        except (json.JSONDecodeError, ValidationError):
            continue

    # 3단계 (F-001c): Solo 폴백
    return ClassificationResult(
        mode="solo",
        reason="파싱 실패: CLI 출력을 분류 결과로 변환할 수 없음",
        agents=[],
        user_status_message=None,
    )
