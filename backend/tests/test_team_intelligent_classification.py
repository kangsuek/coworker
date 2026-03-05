import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.classification import classify_message

@pytest.mark.asyncio
async def test_intelligent_classification_e2e():
    """실제 LLM 호출을 포함한 지능형 분류 E2E 테스트."""
    user_message = "(팀모드) 1. 시장 조사 2. 기술 분석 3. 두 내용을 종합하여 보고서 작성"
    
    # 실제 gemini-cli 호출을 Mocking하여 지능형 응답을 반환하도록 설정
    mock_llm_response = json.dumps({
        "agents": [
            {"role": "Researcher", "task": "시장 조사", "depends_on": []},
            {"role": "Researcher", "task": "기술 분석", "depends_on": []},
            {"role": "Writer", "task": "두 내용을 종합하여 보고서 작성", "depends_on": [0, 1]}
        ]
    })

    # GeminiCliProvider.stream_generate를 패치
    with patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_llm_response
        
        result = await classify_message(user_message)
        
        # 기본 검증
        assert result.mode == "team"
        assert len(result.agents) == 3
        
        # 의존성 검증
        # 2번 태스크(보고서 작성)가 0번(시장 조사)과 1번(기술 분석)에 의존하는지 확인
        assert 0 in result.agents[2].depends_on
        assert 1 in result.agents[2].depends_on
        
        # 시스템 프롬프트가 최적화되었는지 확인 (일부 키워드 포함 여부)
        called_args, called_kwargs = mock_gen.call_args
        system_prompt = called_kwargs.get('system_prompt', '')
        assert "Planner" in system_prompt
        assert "depends_on" in system_prompt
        # 최적화된 짧은 문구 확인
        assert "다른 설명 없이 JSON만 반환하십시오" in system_prompt

@pytest.mark.asyncio
async def test_vague_role_assignment_e2e():
    """모호한 요청에 대한 지능형 역할 할당 E2E 테스트."""
    user_message = "(팀모드) 1. 현재 주식 시장 트렌드를 알려줘 2. 이를 바탕으로 내일 투자 전략을 세워줘"
    
    mock_llm_response = json.dumps({
        "agents": [
            {"role": "Researcher", "task": "현재 주식 시장 트렌드를 알려줘", "depends_on": []},
            {"role": "Planner", "task": "이를 바탕으로 내일 투자 전략을 세워줘", "depends_on": [0]}
        ]
    })

    with patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_llm_response
        
        result = await classify_message(user_message)
        
        assert result.mode == "team"
        assert result.agents[0].role == "Researcher"
        assert result.agents[1].role == "Planner"
        assert result.agents[1].depends_on == [0]
