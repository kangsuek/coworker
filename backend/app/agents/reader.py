"""Reader Agent (Orchestrator).

분류, Solo 모드, Team 모드 오케스트레이션.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ClassificationResult
from app.services.classification import parse_classification
from app.services.cli_service import call_claude_streaming, execute_with_lock
from app.services.session_service import create_user_message, update_run_status

logger = logging.getLogger(__name__)


class ReaderAgent:
    CLASSIFY_SYSTEM_PROMPT = (
        "당신은 요청 라우터입니다. "
        "사용자 메시지를 분석하고 아래 JSON 형식으로만 응답하세요.\n\n"
        "solo: 단순 질문/답변, 단일 태스크, 창작, 번역, 요약 등\n"
        "team: 복잡한 프로젝트, 다단계 작업, 여러 전문 분야 필요\n\n"
        '{"mode": "solo"|"team", "reason": "이유", "agents": [], "user_status_message": null}\n\n'
        "team일 때 agents 예시:\n"
        '{"role": "Researcher"|"Coder"|"Reviewer"|"Writer"|"Planner", "task": "구체적 태스크"}\n\n'
        "JSON만 출력. 다른 텍스트 금지."
    )
    SOLO_SYSTEM_PROMPT = (
        "당신은 친절하고 유능한 AI 어시스턴트입니다. "
        "사용자의 질문에 명확하고 도움이 되는 답변을 제공합니다."
    )

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def process_message(
        self, session_id: str, user_message: str, run_id: str
    ) -> None:
        """메시지 처리: 분류 → Solo/Team 실행."""
        try:
            await update_run_status(self.db, run_id, "thinking")
            result = await self._classify(user_message)

            if result.mode == "solo":
                await update_run_status(self.db, run_id, "solo")
                text = await self._solo_respond(user_message)
                await create_user_message(self.db, session_id, "reader", text, mode="solo")
                await update_run_status(self.db, run_id, "done", response=text, mode="solo")
            else:
                # Sprint 5에서 Team 모드 구현
                await update_run_status(self.db, run_id, "delegating", mode="team")
        except Exception as e:
            logger.exception("process_message 실패: run_id=%s", run_id)
            error_msg = str(e)

            if "Claude CLI error" in error_msg:
                try:
                    parts = error_msg.split("): ", 1)
                    if len(parts) == 2:
                        raw_output = parts[1].strip()
                        if raw_output.startswith("{"):
                            parsed = json.loads(raw_output)
                            if "result" in parsed:
                                error_msg = parsed["result"]
                            elif "error" in parsed:
                                error_msg = str(parsed["error"])
                            else:
                                error_msg = raw_output
                        else:
                            error_msg = raw_output
                except Exception:
                    pass

            await create_user_message(
                self.db, session_id, "reader", f"⚠️ 오류 발생: {error_msg}", mode="solo"
            )
            await update_run_status(self.db, run_id, "error", response=error_msg)

    async def _classify(self, user_message: str) -> ClassificationResult:
        """CLI로 Solo/Team 분류."""
        raw = await execute_with_lock(
            call_claude_streaming(
                self.CLASSIFY_SYSTEM_PROMPT, user_message, output_json=True
            )
        )
        return parse_classification(raw)

    async def _solo_respond(self, user_message: str) -> str:
        """Solo 모드 응답 생성."""
        return await execute_with_lock(
            call_claude_streaming(self.SOLO_SYSTEM_PROMPT, user_message)
        )
