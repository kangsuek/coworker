import json
import pytest
from unittest.mock import AsyncMock, patch
from app.services.classification import classify_message
from app.models.schemas import ClassificationResult

@pytest.mark.asyncio
async def test_llm_classification_complex_dependency():
    """복합 의존성 시나리오: A, B 작업 후 C 수행."""
    user_message = "(팀모드) 1. 시장 조사 2. 기술 분석 3. 두 내용을 종합하여 보고서 작성"
    
    # LLM이 반환할 가상의 응답 (JSON 형태)
    mock_llm_response = json.dumps({
        "agents": [
            {"role": "Researcher", "task": "시장 조사", "depends_on": []},
            {"role": "Researcher", "task": "기술 분석", "depends_on": []},
            {"role": "Writer", "task": "두 내용을 종합하여 보고서 작성", "depends_on": [0, 1]}
        ]
    })

    # GeminiCliProvider.stream_generate를 패치하여 가짜 응답 반환
    with patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_llm_response
        
        result = await classify_message(user_message)
        
        assert result.mode == "team"
        assert len(result.agents) == 3
        
        # 0: 시장 조사 (Researcher)
        # 1: 기술 분석 (Researcher)
        # 2: 보고서 작성 (Writer, depends_on=[0, 1])
        assert result.agents[0].role == "Researcher"
        assert result.agents[1].role == "Researcher"
        assert result.agents[2].role == "Writer"
        
        # 핵심 검증: 복합 의존성 (0번과 1번이 끝난 후 2번 실행)
        assert 0 in result.agents[2].depends_on
        assert 1 in result.agents[2].depends_on
        mock_gen.assert_called_once()

@pytest.mark.asyncio
async def test_llm_classification_vague_role():
    """모호한 역할 할당: 키워드가 없어도 문맥으로 역할 판단."""
    user_message = "(팀모드) 1. 현재 트렌드를 파악해줘 2. 이걸 바탕으로 다음 행보를 제안해줘"
    
    mock_llm_response = json.dumps({
        "agents": [
            {"role": "Researcher", "task": "현재 트렌드를 파악해줘", "depends_on": []},
            {"role": "Planner", "task": "이걸 바탕으로 다음 행보를 제안해줘", "depends_on": [0]}
        ]
    })

    with patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_llm_response
        
        result = await classify_message(user_message)
        
        assert result.mode == "team"
        assert len(result.agents) == 2
        
        assert result.agents[0].role == "Researcher"
        assert result.agents[1].role == "Planner"
        assert result.agents[1].depends_on == [0]

@pytest.mark.asyncio
async def test_llm_classification_fallback_on_failure():
    """LLM 실패 시 기존 규칙 기반(Regex/Keyword) 방식으로 폴백."""
    user_message = "(팀모드) 1. 조사 2. 작성"
    
    # _classify_with_llm 내부에서 발생하는 예외를 모방
    with patch("app.services.llm.gemini_cli.GeminiCliProvider.stream_generate", side_effect=Exception("LLM Timeout")):
        result = await classify_message(user_message)
        
        # 폴백 시에도 기본적으로 team 모드는 유지되어야 함
        assert result.mode == "team"
        assert len(result.agents) == 2
        assert result.agents[0].role == "Researcher"
        assert result.agents[1].role == "Writer"
        
        # 규칙 기반 폴백 시에는 순차적 의존성 ([i-1])이 생성됨
        assert result.agents[0].depends_on == []
        assert result.agents[1].depends_on == [0]
