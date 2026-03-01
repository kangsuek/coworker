"""3-6. Solo 모드 End-to-End 통합 테스트.

httpx AsyncClient로 전체 흐름 검증:
POST /api/chat → BackgroundTask 완료 → GET /api/runs/{run_id} → done
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_session_cm(db):
    """async_session()이 반환하는 컨텍스트 매니저 mock."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


@pytest.mark.asyncio
async def test_solo_e2e_full_flow(client, db):
    """POST → BackgroundTask 완료 → GET → done + response 확인."""
    with (
        patch("app.routers.chat.async_session", return_value=_make_session_cm(db)),
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
    ):
        mock_cli.side_effect = [
            '{"mode":"solo","reason":"단순 질문","agents":[]}',
            "Solo 응답 텍스트",
        ]
        post_resp = await client.post("/api/chat", json={"message": "안녕하세요"})

    assert post_resp.status_code == 200
    run_id = post_resp.json()["run_id"]

    get_resp = await client.get(f"/api/runs/{run_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["status"] == "done"
    assert data["response"] == "Solo 응답 텍스트"
    assert data["mode"] == "solo"


@pytest.mark.asyncio
async def test_solo_e2e_session_history(client, db):
    """Solo 응답 완료 후 세션 히스토리에 user + reader 메시지 저장 확인."""
    with (
        patch("app.routers.chat.async_session", return_value=_make_session_cm(db)),
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
    ):
        mock_cli.side_effect = [
            '{"mode":"solo","reason":"단순","agents":[]}',
            "히스토리 응답",
        ]
        post_resp = await client.post("/api/chat", json={"message": "히스토리 테스트"})

    session_id = post_resp.json()["session_id"]
    detail_resp = await client.get(f"/api/sessions/{session_id}")
    assert detail_resp.status_code == 200
    messages = detail_resp.json()["messages"]
    roles = [m["role"] for m in messages]
    assert "user" in roles
    assert "reader" in roles


@pytest.mark.asyncio
async def test_solo_e2e_json_fallback(client, db):
    """분류 CLI 비정상 출력 → Solo 폴백 → 응답 성공."""
    with (
        patch("app.routers.chat.async_session", return_value=_make_session_cm(db)),
        patch("app.agents.reader.call_claude_streaming", new_callable=AsyncMock) as mock_cli,
    ):
        # 비정상 JSON → parse_classification이 Solo 폴백 반환
        mock_cli.side_effect = [
            "I cannot classify this request",
            "폴백 응답",
        ]
        post_resp = await client.post("/api/chat", json={"message": "분류 불가 요청"})

    assert post_resp.status_code == 200
    run_id = post_resp.json()["run_id"]

    get_resp = await client.get(f"/api/runs/{run_id}")
    data = get_resp.json()
    assert data["status"] == "done"
    assert data["response"] == "폴백 응답"
