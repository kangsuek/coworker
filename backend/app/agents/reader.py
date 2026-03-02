"""Reader Agent (Orchestrator).

분류, Solo 모드, Team 모드 오케스트레이션.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.presets import coder, planner, researcher, reviewer, writer
from app.agents.sub_agent import SubAgent
from app.config import settings
from app.models.schemas import AgentPlan, ClassificationResult
from app.services.classification import classify_message, parse_classification
from app.services.cli_service import LineBufferFlusher, call_claude_streaming, execute_with_lock
from app.services.session_service import (
    create_agent_message,
    create_user_message,
    update_agent_message_content,
    update_agent_message_status,
    update_run_status,
)

logger = logging.getLogger(__name__)

CONTEXT_CHAR_LIMIT = int(os.getenv("CONTEXT_CHAR_LIMIT", "3000"))

_AGENT_COMMON_INSTRUCTION = (
    "\n\n중요: 당신은 팀 프로젝트에서 독립적으로 작업하는 전문가입니다. "
    "절대로 추가 정보를 요청하거나 사용자와 대화하려 하지 마세요. "
    "주어진 정보를 최대한 활용하여 담당 태스크를 즉시 완료하고 완성된 결과물만 제공하세요."
)

_PRESET_MAP = {
    "Researcher": researcher.SYSTEM_PROMPT + _AGENT_COMMON_INSTRUCTION,
    "Coder": coder.SYSTEM_PROMPT + _AGENT_COMMON_INSTRUCTION,
    "Reviewer": reviewer.SYSTEM_PROMPT + _AGENT_COMMON_INSTRUCTION,
    "Writer": writer.SYSTEM_PROMPT + _AGENT_COMMON_INSTRUCTION,
    "Planner": planner.SYSTEM_PROMPT + _AGENT_COMMON_INSTRUCTION,
}

_INTEGRATE_SYSTEM_PROMPT = (
    "당신은 여러 전문가의 작업 결과를 통합하는 조율자입니다. "
    "각 전문가의 결과를 종합하여 사용자 요청에 대한 최종 답변을 작성하세요. "
    "중복을 제거하고 논리적으로 구성된 완성된 응답을 제공하세요."
)

_SUMMARIZE_SYSTEM_PROMPT = (
    "이전 Agent의 작업 결과를 다음 Agent가 참고할 수 있도록 핵심 내용만 간결하게 요약하세요. "
    "코드가 포함된 경우 핵심 로직과 주요 함수 시그니처를 보존하세요."
)


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
                await self._team_execute(result, user_message, session_id, run_id)
        except Exception as e:
            logger.exception("process_message 실패: run_id=%s", run_id)

            # 취소된 run은 에러 상태로 덮어쓰지 않음 (cancel_run 엔드포인트와의 race condition 방어)
            status_row = await self.db.execute(
                sql_text("SELECT status FROM runs WHERE id = :run_id"), {"run_id": run_id}
            )
            row = status_row.fetchone()
            if row and row[0] == "cancelled":
                logger.info("process_message 예외 발생했으나 이미 취소됨: run_id=%s", run_id)
                return

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
        """Solo/Team 분류: 규칙 기반 1차 판정 → 모호하면 haiku CLI 호출."""
        # 1차: 규칙 기반 (명확한 경우 CLI 호출 생략)
        rule_result = classify_message(user_message)
        if rule_result.mode == "team":
            logger.info("_classify (rule-based): mode=team agents=%s", rule_result.agents)
            return rule_result

        # 2차: haiku CLI 호출로 최종 판정 (solo 또는 모호한 경우)
        raw = await execute_with_lock(
            call_claude_streaming(
                self.CLASSIFY_SYSTEM_PROMPT,
                user_message,
                output_json=True,
                model=settings.solo_model,
            )
        )
        result = parse_classification(raw)
        logger.info("_classify (haiku): mode=%s reason=%s agents=%s", result.mode, result.reason, result.agents)
        return result

    async def _solo_respond(self, user_message: str) -> str:
        """Solo 모드 응답 생성."""
        return await execute_with_lock(
            call_claude_streaming(
                self.SOLO_SYSTEM_PROMPT,
                user_message,
                model=settings.solo_model,
            )
        )

    async def _team_execute(
        self,
        classification: ClassificationResult,
        user_message: str,
        session_id: str,
        run_id: str,
    ) -> None:
        """Team 모드 전체 흐름."""
        await update_run_status(self.db, run_id, "delegating", mode="team")

        results: dict[str, str] = {}

        for i, agent_plan in enumerate(classification.agents):
            progress = f"{i + 1}/{len(classification.agents)}"
            await update_run_status(self.db, run_id, "working", progress=progress)

            agent = self._create_agent(agent_plan, i)
            context = await self._assemble_context(results)

            # Agent Channel DB 기록 생성
            agent_msg = await create_agent_message(
                self.db, session_id, run_id, agent.name, agent.role_preset
            )

            # LineBufferFlusher로 배치 DB 쓰기
            accumulated: list[str] = []

            def flush_callback(lines: list[str]) -> None:
                if not lines:
                    return
                accumulated.extend(lines)
                content = "".join(accumulated)
                # 동기 sqlite3로 DB 업데이트 (aiosqlite와 별도 connection)
                try:
                    conn = sqlite3.connect(settings.db_path, timeout=5)
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout=5000;")
                    conn.execute(
                        "UPDATE agent_messages SET content = ? WHERE id = ?",
                        (content, agent_msg.id),
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    logger.warning(
                        "LineBufferFlusher DB 쓰기 실패: msg_id=%s", agent_msg.id, exc_info=True
                    )

            flusher = LineBufferFlusher(flush_callback, flush_interval=0.5)
            flusher.start()

            def on_line(line: str) -> None:
                flusher.append(line)

            # 원본 사용자 요청을 포함하여 Sub-Agent가 전체 맥락을 파악하도록 함
            full_task = (
                f"[전체 프로젝트 요청]\n{user_message}\n\n"
                f"[당신의 담당 태스크]\n{agent_plan.task}"
            )

            try:
                result = await execute_with_lock(
                    agent.execute(full_task, context, on_line, model=settings.team_model)
                )
            except Exception:
                flusher.stop()
                await update_agent_message_status(self.db, agent_msg.id, "error")
                raise
            flusher.stop()

            # aiosqlite 세션으로 최종 content 동기화
            await update_agent_message_content(self.db, agent_msg.id, result)
            await update_agent_message_status(self.db, agent_msg.id, "done")
            results[agent.name] = result

        await update_run_status(self.db, run_id, "integrating")
        final = await self._integrate_results(user_message, results)
        await create_user_message(self.db, session_id, "reader", final, mode="team")
        await update_run_status(self.db, run_id, "done", response=final, mode="team")

    def _create_agent(self, agent_plan: AgentPlan, index: int) -> SubAgent:
        """AgentPlan → SubAgent 생성."""
        system_prompt = _PRESET_MAP.get(agent_plan.role, _PRESET_MAP["Researcher"])
        return SubAgent(
            name=f"{agent_plan.role}-{index + 1}",
            role_preset=agent_plan.role,
            system_prompt=system_prompt,
        )

    async def _integrate_results(self, user_message: str, results: dict[str, str]) -> str:
        """모든 Agent 결과를 통합하는 CLI 호출."""
        parts = [f"[{name} 결과]:\n{result}" for name, result in results.items()]
        combined = "\n\n".join(parts)
        prompt = f"사용자 요청: {user_message}\n\n{combined}"
        return await execute_with_lock(
            call_claude_streaming(
                _INTEGRATE_SYSTEM_PROMPT,
                prompt,
                model=settings.team_model,
            )
        )

    async def _assemble_context(self, results: dict[str, str]) -> str | None:
        """이전 Agent 결과를 다음 Agent 컨텍스트로 조립."""
        if not results:
            return None

        parts = []
        for agent_name, result in results.items():
            if len(result) > CONTEXT_CHAR_LIMIT:
                result = await self._summarize_for_context(agent_name, result)
            parts.append(f"[{agent_name} 결과]:\n{result}")

        return "\n\n".join(parts)

    async def _summarize_for_context(self, agent_name: str, content: str) -> str:
        """긴 결과물을 다음 Agent에 전달할 수 있도록 CLI 호출로 요약."""
        return await execute_with_lock(
            call_claude_streaming(
                _SUMMARIZE_SYSTEM_PROMPT,
                f"다음은 {agent_name}의 작업 결과입니다. 요약해주세요:\n\n{content}",
                on_line=None,
                model=settings.team_model,
            )
        )
