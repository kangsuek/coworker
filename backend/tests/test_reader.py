"""Reader Agent 테스트 — Task 3-1.

call_claude_streaming을 완전히 mock해 CLI 호출 없이 테스트.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.reader import ReaderAgent, _build_conversation_prompt
from app.models.db import Run
from app.services.session_service import create_run, create_session, create_user_message


@pytest.mark.asyncio
async def test_process_message_logs_error_on_exception(db):
    """CLI 에러 발생 시 logger.exception 호출 확인."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "오류 테스트")
    run = await create_run(db, sess.id, msg.id)

    with (
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
        patch("app.agents.reader.logger") as mock_logger,
    ):
        mock_cli.side_effect = RuntimeError("CLI 오류")
        await ReaderAgent(db).process_message(sess.id, "오류 테스트", run.id)

    mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_classify_returns_solo(db):
    """단순 메시지 → solo 분류 (haiku CLI mock)."""
    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = '{"mode":"solo","reason":"간단한 질문","agents":[]}'
        result = await ReaderAgent(db)._classify("안녕하세요")
    assert result.mode == "solo"


@pytest.mark.asyncio
async def test_classify_returns_team(db):
    """헤더 + 번호 목록 → 규칙 기반으로 즉시 team 반환 (CLI 호출 없음)."""
    result = await ReaderAgent(db)._classify(
        "(팀모드) 1. 시장 조사, 2. 기술 설계, 3. 마케팅 전략을 작성해줘."
    )
    assert result.mode == "team"
    assert len(result.agents) == 3


@pytest.mark.asyncio
async def test_solo_respond_returns_text(db):
    """call_claude_streaming mock → 응답 텍스트 반환."""
    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = "응답 텍스트"
        agent = ReaderAgent(db)
        result = await agent._solo_respond("질문입니다")
    assert result == "응답 텍스트"


@pytest.mark.asyncio
async def test_process_message_solo_flow(db):
    """Solo 흐름: run status 'done', response 저장, mode='solo' 확인."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "안녕")
    run = await create_run(db, sess.id, msg.id)

    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        # solo 응답 1회 (분류는 규칙 기반이므로 CLI 호출 없음)
        mock_cli.return_value = "안녕하세요!"
        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "안녕", run.id)

    updated_run = await db.get(Run, run.id)
    assert updated_run.status == "done"
    assert updated_run.response == "안녕하세요!"
    assert updated_run.mode == "solo"


@pytest.mark.asyncio
async def test_process_message_error_handling(db):
    """CLI 오류 → run status='error'."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "오류 테스트")
    run = await create_run(db, sess.id, msg.id)

    with patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli:
        mock_cli.side_effect = RuntimeError("CLI 오류")
        agent = ReaderAgent(db)
        await agent.process_message(sess.id, "오류 테스트", run.id)

    updated_run = await db.get(Run, run.id)
    assert updated_run.status == "error"


# ── 대화 이력 프롬프트 조립 테스트 ──────────────────────────────────────────


def test_build_conversation_prompt_no_history():
    """이력 없으면 user_message 그대로 반환."""
    result = _build_conversation_prompt("안녕하세요", [])
    assert result == "안녕하세요"


def test_build_conversation_prompt_with_history():
    """이전 대화 이력이 있으면 [이전 대화] 섹션이 포함된다."""

    class FakeMsg:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    history = [
        FakeMsg("user", "파이썬이 뭐야?"),
        FakeMsg("reader", "파이썬은 프로그래밍 언어입니다."),
    ]
    result = _build_conversation_prompt("더 자세히 설명해줘", history)

    assert "[이전 대화]" in result
    assert "사용자: 파이썬이 뭐야?" in result
    assert "어시스턴트: 파이썬은 프로그래밍 언어입니다." in result
    assert "[현재 질문]" in result
    assert "더 자세히 설명해줘" in result


@pytest.mark.asyncio
async def test_conversation_history_passed_to_cli(db):
    """2턴 대화 후 3번째 메시지 전송 시 CLI에 이전 대화 이력이 포함된다."""
    sess = await create_session(db)

    # 1번째 대화 (user + reader 메시지 저장)
    await create_user_message(db, sess.id, "user", "파이썬이 뭐야?")
    await create_user_message(db, sess.id, "reader", "파이썬은 프로그래밍 언어입니다.", mode="solo")

    # 2번째 메시지 전송
    msg2 = await create_user_message(db, sess.id, "user", "더 자세히 설명해줘")
    run = await create_run(db, sess.id, msg2.id)

    captured_prompt: list[str] = []

    async def fake_streaming(system_prompt, prompt, **kwargs):
        captured_prompt.append(prompt)
        return "자세한 설명입니다."

    with patch("app.agents.reader.call_claude_streaming", side_effect=fake_streaming):
        await ReaderAgent(db).process_message(sess.id, "더 자세히 설명해줘", run.id)

    assert len(captured_prompt) == 1
    prompt = captured_prompt[0]
    assert "파이썬이 뭐야?" in prompt, "이전 user 메시지가 프롬프트에 포함되어야 함"
    assert "파이썬은 프로그래밍 언어입니다." in prompt, \
        "이전 reader 메시지가 프롬프트에 포함되어야 함"
    assert "더 자세히 설명해줘" in prompt, "현재 질문이 프롬프트에 포함되어야 함"
    # 현재 메시지는 이력 섹션이 아닌 [현재 질문] 섹션에 있어야 함
    assert "[현재 질문]" in prompt
