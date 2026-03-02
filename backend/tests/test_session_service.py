"""세션 CRUD 서비스 테스트 — Task 2-4.

테스트 대상:
- create_session, get_session, list_sessions
- get_session_with_messages
- create_user_message, create_run, update_run_status
"""

import pytest
from sqlalchemy import select

from app.models.db import AgentMessage, Run, UserMessage
from app.services.session_service import (
    create_agent_message,
    create_run,
    create_session,
    create_user_message,
    delete_session,
    get_agent_messages,
    get_session,
    get_session_with_messages,
    list_sessions,
    update_agent_message_content,
    update_agent_message_status,
    update_run_status,
)


@pytest.mark.asyncio
async def test_create_session(db):
    """세션 생성 -> id, created_at 존재."""
    sess = await create_session(db)
    assert sess.id is not None
    assert sess.created_at is not None


@pytest.mark.asyncio
async def test_list_sessions(db):
    """복수 생성 -> 최신순 목록 반환."""
    s1 = await create_session(db)
    s2 = await create_session(db)
    sessions = await list_sessions(db)
    assert len(sessions) >= 2
    assert sessions[0].id == s2.id
    assert sessions[1].id == s1.id


@pytest.mark.asyncio
async def test_get_session(db):
    """존재하는 세션 조회 성공."""
    created = await create_session(db)
    fetched = await get_session(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.asyncio
async def test_get_session_not_found(db):
    """없는 세션 -> None 반환."""
    result = await get_session(db, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_session_with_messages(db):
    """메시지 포함 상세 조회."""
    sess = await create_session(db)
    await create_user_message(db, sess.id, "user", "hello")
    await create_user_message(db, sess.id, "reader", "hi there")

    detail = await get_session_with_messages(db, sess.id)
    assert detail is not None
    assert len(detail.user_messages) == 2


@pytest.mark.asyncio
async def test_create_user_message(db):
    """메시지 저장 -> 세션에 연결."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "test message", mode="solo")
    assert msg.id is not None
    assert msg.session_id == sess.id
    assert msg.role == "user"
    assert msg.content == "test message"
    assert msg.mode == "solo"


@pytest.mark.asyncio
async def test_create_run(db):
    """Run 생성 -> status='queued'."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "run test")
    run = await create_run(db, sess.id, msg.id)
    assert run.id is not None
    assert run.session_id == sess.id
    assert run.user_message_id == msg.id
    assert run.status == "queued"


@pytest.mark.asyncio
async def test_update_run_status(db):
    """상태 업데이트 확인."""
    sess = await create_session(db)
    msg = await create_user_message(db, sess.id, "user", "update test")
    run = await create_run(db, sess.id, msg.id)

    updated = await update_run_status(db, run.id, "done", response="result text", mode="solo")
    assert updated is not None
    assert updated.status == "done"
    assert updated.response == "result text"
    assert updated.mode == "solo"


# --- Task 3-4-a: 세션 제목 자동 생성 ---


@pytest.mark.asyncio
async def test_auto_title_generation(db):
    """30자 이하 메시지 → session.title == message."""
    sess = await create_session(db)
    short_msg = "짧은 메시지"
    await create_user_message(db, sess.id, "user", short_msg)
    updated = await get_session(db, sess.id)
    assert updated.title == short_msg


@pytest.mark.asyncio
async def test_auto_title_truncation(db):
    """31자 메시지 → title == message[:30] + '…'."""
    sess = await create_session(db)
    long_msg = "가" * 31
    await create_user_message(db, sess.id, "user", long_msg)
    updated = await get_session(db, sess.id)
    assert updated.title == "가" * 30 + "…"


@pytest.mark.asyncio
async def test_auto_title_no_overwrite(db):
    """title이 이미 있는 세션 → 덮어쓰지 않음."""
    sess = await create_session(db)
    sess.title = "기존 제목"
    await db.commit()
    await db.refresh(sess)

    await create_user_message(db, sess.id, "user", "새 메시지")
    updated = await get_session(db, sess.id)
    assert updated.title == "기존 제목"


# --- Task 5-5: Agent Channel DB 기록 ---


@pytest.mark.asyncio
async def test_create_agent_message(db):
    """AgentMessage 레코드 생성 확인."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)

    msg = await create_agent_message(db, sess.id, run.id, "Researcher-A", "Researcher")
    assert msg.id is not None
    assert msg.session_id == sess.id
    assert msg.run_id == run.id
    assert msg.sender == "Researcher-A"
    assert msg.role_preset == "Researcher"
    assert msg.status == "working"


@pytest.mark.asyncio
async def test_update_agent_message_content(db):
    """중간 출력 누적 업데이트."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)
    msg = await create_agent_message(db, sess.id, run.id, "Coder-A", "Coder")

    updated = await update_agent_message_content(db, msg.id, "첫 번째 줄\n두 번째 줄\n")
    assert updated is not None
    assert "첫 번째 줄" in updated.content
    assert "두 번째 줄" in updated.content


@pytest.mark.asyncio
async def test_update_agent_message_status(db):
    """상태 변경 확인."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)
    msg = await create_agent_message(db, sess.id, run.id, "Writer-A", "Writer")

    updated = await update_agent_message_status(db, msg.id, "done")
    assert updated is not None
    assert updated.status == "done"


@pytest.mark.asyncio
async def test_get_agent_messages(db):
    """run_id로 agent_messages 목록 조회."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "작업")
    run = await create_run(db, sess.id, user_msg.id)

    await create_agent_message(db, sess.id, run.id, "Researcher-A", "Researcher")
    await create_agent_message(db, sess.id, run.id, "Coder-A", "Coder")

    messages = await get_agent_messages(db, run.id)
    assert len(messages) == 2


# --- Bug Fix: 세션 삭제 시 자식 레코드 완전 삭제 검증 ---


@pytest.mark.asyncio
async def test_delete_session_removes_all_children(db):
    """세션 삭제 시 runs, agent_messages, user_messages 모두 삭제됨 (Bug 1 + Bug 4 수정 검증)."""
    sess = await create_session(db)
    user_msg = await create_user_message(db, sess.id, "user", "테스트")
    run = await create_run(db, sess.id, user_msg.id)
    await create_agent_message(db, sess.id, run.id, "Coder-1", "Coder")

    result = await delete_session(db, sess.id)
    assert result is True

    remaining_runs = (await db.execute(select(Run).where(Run.session_id == sess.id))).scalars().all()
    remaining_msgs = (await db.execute(select(UserMessage).where(UserMessage.session_id == sess.id))).scalars().all()
    remaining_agent = (await db.execute(select(AgentMessage).where(AgentMessage.session_id == sess.id))).scalars().all()

    assert remaining_runs == [], "runs가 삭제되지 않음"
    assert remaining_msgs == [], "user_messages가 삭제되지 않음"
    assert remaining_agent == [], "agent_messages가 삭제되지 않음"


@pytest.mark.asyncio
async def test_delete_session_returns_false_for_nonexistent(db):
    """없는 세션 삭제 → False 반환."""
    result = await delete_session(db, "nonexistent-id")
    assert result is False
