"""Reader Agent (Orchestrator).

분류, Solo 모드, Team 모드 오케스트레이션.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from datetime import UTC, datetime

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.presets import coder, planner, researcher, reviewer, writer
from app.agents.sub_agent import SubAgent
from app.config import settings
from app.models import db as models
from app.models.schemas import AgentPlan, ClassificationResult
from app.services.classification import classify_message
from app.services.cli_service import LineBufferFlusher
from app.services.llm import get_provider
from app.services.session_service import (
    create_agent_message,
    create_user_message,
    get_recent_messages,
    update_agent_message_content,
    update_agent_message_status,
    update_run_status,
)

logger = logging.getLogger(__name__)

CONTEXT_CHAR_LIMIT = int(os.getenv("CONTEXT_CHAR_LIMIT", "3000"))
_HISTORY_MSG_LIMIT = 20  # 최근 20개 메시지 (약 10턴)


def _build_conversation_prompt(user_message: str, history: list) -> str:
    """이전 대화 이력을 포함한 프롬프트 생성.

    history가 비어 있으면 user_message를 그대로 반환.
    role='user' → '사용자', role='reader' → '어시스턴트'로 표기.
    """
    if not history:
        return user_message

    lines = ["[이전 대화]"]
    for msg in history:
        role_label = "사용자" if msg.role == "user" else "어시스턴트"
        lines.append(f"{role_label}: {msg.content}")
    lines.append("")
    lines.append(f"[현재 질문]\n{user_message}")
    return "\n".join(lines)

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

_SUMMARIZE_HISTORY_SYSTEM_PROMPT = (
    "사용자와 AI 어시스턴트 간의 이전 대화 이력을 요약하세요. "
    "현재 질문을 이해하는 데 필요한 핵심 맥락, 설정값, 이미 내려진 결정 사항 위주로 요약하세요. "
    "다음 Agent가 이 요약을 보고 대화의 흐름을 완벽히 파악할 수 있어야 합니다."
)


class ReaderAgent:
    SOLO_SYSTEM_PROMPT = (
        "당신은 친절하고 유능한 AI 어시스턴트입니다. "
        "사용자의 질문에 명확하고 도움이 되는 답변을 제공합니다."
    )

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.db_lock = asyncio.Lock()

    async def process_message(
        self, session_id: str, user_message: str, run_id: str
    ) -> None:
        """메시지 처리: 분류 → Solo/Team 실행."""
        try:
            # 현재 run의 user_message_id를 찾아 대화 이력에서 제외
            run = await self.db.get(models.Run, run_id)
            current_msg_id = run.user_message_id if run else None

            session = await self.db.get(models.Session, session_id)
            provider_name = session.llm_provider if session and session.llm_provider else "claude-cli"
            self.llm_provider = get_provider(provider_name)
            self.session_model = session.llm_model if session else None

            async with self.db_lock:
                await update_run_status(
                    self.db, run_id, "thinking", thinking_started_at=datetime.now(UTC)
                )
            result = await self._classify(user_message)

            if result.mode == "solo":
                async with self.db_lock:
                    await update_run_status(
                        self.db, run_id, "solo", cli_started_at=datetime.now(UTC)
                    )
                history = await get_recent_messages(
                    self.db, session_id,
                    limit=_HISTORY_MSG_LIMIT,
                    exclude_id=current_msg_id,
                )
                text = await self._solo_respond(user_message, history, run_id=run_id)
                
                async with self.db_lock:
                    # CLI 실행 도중 세션이 삭제됐을 수 있으므로 run 존재 여부 재확인
                    if await self.db.get(models.Run, run_id) is None:
                        logger.info("solo 완료 후 run이 삭제됨, DB 쓰기 건너뜀: run_id=%s", run_id)
                        return
                    await create_user_message(self.db, session_id, "reader", text, mode="solo")
                    await update_run_status(
                        self.db, run_id, "done",
                        response=text, mode="solo", finished_at=datetime.now(UTC),
                    )
            else:
                await self._team_execute(result, user_message, session_id, run_id)
        except Exception as e:
            logger.exception("process_message 실패: run_id=%s", run_id)

            async with self.db_lock:
                # run이 삭제됐으면 (세션 삭제 등) 고아 레코드 생성을 막기 위해 즉시 반환
                status_row = await self.db.execute(
                    sql_text("SELECT status FROM runs WHERE id = :run_id"), {"run_id": run_id}
                )
                row = status_row.fetchone()
                if row is None:
                    logger.info("process_message 예외 발생했으나 run이 삭제됨: run_id=%s", run_id)
                    return
                # 취소된 run은 에러 상태로 덮어쓰지 않음 (cancel_run 엔드포인트와의 race condition 방어)
                if row[0] == "cancelled":
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
                await update_run_status(
                    self.db, run_id, "error", response=error_msg, finished_at=datetime.now(UTC)
                )

    async def _classify(self, user_message: str) -> ClassificationResult:
        """Solo/Team 분류: 규칙 기반 판정만 사용 (CLI 호출 없음).

        2차 CLI 판정을 제거해 분류 지연(3~15초)과 _cli_lock 선점 문제를 해소한다.
        Team 트리거는 TEAM_TRIGGER_KEYWORDS 환경변수로 코드 수정 없이 확장 가능.
        """
        result = classify_message(user_message)
        logger.info("_classify (rule-based): mode=%s agents=%s", result.mode, result.agents)
        return result

    async def _solo_respond(
        self, user_message: str, history: list | None = None, run_id: str | None = None
    ) -> str:
        """Solo 모드 응답 생성. history가 있으면 대화 이력을 프롬프트에 포함."""
        prompt = _build_conversation_prompt(user_message, history or [])
        model_to_use = self.session_model or settings.solo_model
        return await self.llm_provider.stream_generate(
            self.SOLO_SYSTEM_PROMPT,
            prompt,
            model=model_to_use,
            run_id=run_id,
        )

    async def _team_execute(
        self,
        classification: ClassificationResult,
        user_message: str,
        session_id: str,
        run_id: str,
    ) -> None:
        """Team 모드 전체 흐름 (병렬 실행 지원)."""
        async with self.db_lock:
            await update_run_status(self.db, run_id, "delegating", mode="team")

        # 현재 run의 user_message_id를 찾아 대화 이력에서 제외
        run = await self.db.get(models.Run, run_id)
        current_msg_id = run.user_message_id if run else None

        # 최근 대화 이력 가져오기 (Solo 모드와 동일한 로직)
        history_msgs = await get_recent_messages(
            self.db, session_id,
            limit=_HISTORY_MSG_LIMIT,
            exclude_id=current_msg_id,
        )
        # 히스토리를 텍스트로 변환 (사용자 질문 제외하고 이전 내용만)
        history_context = ""
        if history_msgs:
            history_context = _build_conversation_prompt("", history_msgs).strip()
            # 히스토리가 너무 길면 요약
            if len(history_context) > CONTEXT_CHAR_LIMIT:
                logger.info(
                    "히스토리가 길어 요약 수행: session_id=%s, len=%d",
                    session_id, len(history_context)
                )
                history_context = await self._summarize_history(history_context, run_id=run_id)
                history_context = f"[이전 대화 요약]\n{history_context}"

        # 병렬 실행 관리
        semaphore = asyncio.Semaphore(3)  # 동시 CLI 실행 제한 (Rate limit 대응)
        agent_results: dict[str, str] = {}  # 에이전트 이름 -> 결과물
        agent_tasks: dict[int, asyncio.Task] = {}  # index -> Task
        completed_count = 0
        total_count = len(classification.agents)

        async def run_one_agent(index: int, agent_plan: AgentPlan) -> str:
            # 1. 의존성 대기 (depends_on에 있는 이전 에이전트 태스크 완료 대기)
            for dep_idx in agent_plan.depends_on:
                if dep_idx in agent_tasks:
                    await agent_tasks[dep_idx]
            
            # 2. 실행 (세마포어 획득하여 동시 CLI 실행 개수 제한)
            async with semaphore:
                agent = self._create_agent(agent_plan, index)
                
                # 현재까지 완료된 다른 에이전트들의 결과 조립
                # (의존성이 없는 에이전트들은 빈 컨텍스트를 가질 수 있음)
                # 이 딕셔너리는 쓰기 시 락이 없어도 괜찮음 (각 태스크가 고유한 이름을 쓰거나 완료 시점에만 씀)
                agent_results_context = await self._assemble_context(agent_results, run_id=run_id)

                # 전체 맥락: 이전 대화 히스토리 + 이전 에이전트 결과물
                full_context_parts = []
                if history_context:
                    full_context_parts.append(history_context)
                if agent_results_context:
                    full_context_parts.append(agent_results_context)
                
                full_context = "\n\n".join(full_context_parts) if full_context_parts else None

                # Agent Channel DB 기록 생성
                async with self.db_lock:
                    agent_msg = await create_agent_message(
                        self.db, session_id, run_id, agent.name, agent.role_preset
                    )

                # progress 업데이트
                nonlocal completed_count
                progress_str = f"{completed_count + 1}/{total_count}"
                async with self.db_lock:
                    await update_run_status(self.db, run_id, "working", progress=progress_str)

                # LineBufferFlusher로 배치 DB 쓰기
                accumulated: list[str] = []

                async def flush_callback(lines: list[str]) -> None:
                    if not lines:
                        return
                    accumulated.extend(lines)
                    content = "".join(accumulated)
                    
                    # 모든 DB 쓰기를 하나의 락으로 통합
                    async with self.db_lock:
                        try:
                            # 비동기 세션을 사용하여 안전하게 업데이트
                            await update_agent_message_content(self.db, agent_msg.id, content)
                        except Exception:
                            logger.warning(
                                "LineBufferFlusher DB 쓰기 실패: msg_id=%s", agent_msg.id, exc_info=True
                            )

                flusher = LineBufferFlusher(flush_callback, flush_interval=0.5)
                flusher.start()

                def on_line(line: str) -> None:
                    flusher.append(line)

                full_task = (
                    f"[전체 프로젝트 요청]\n{user_message}\n\n"
                    f"[당신의 담당 태스크]\n{agent_plan.task}"
                )

                try:
                    model_to_use = self.session_model or settings.team_model
                    result = await agent.execute(full_task, full_context, on_line, model=model_to_use, run_id=run_id)
                except Exception:
                    await flusher.stop()
                    async with self.db_lock:
                        await update_agent_message_status(self.db, agent_msg.id, "error")
                    raise
                await flusher.stop()

                # 완료 처리
                async with self.db_lock:
                    await update_agent_message_content(self.db, agent_msg.id, result)
                    await update_agent_message_status(self.db, agent_msg.id, "done")
                
                agent_results[agent.name] = result
                completed_count += 1
                return result

        # 3. 모든 에이전트 태스크 생성 및 실행
        for i, plan in enumerate(classification.agents):
            agent_tasks[i] = asyncio.create_task(run_one_agent(i, plan))
        
        try:
            # 4. 모든 태스크 완료 대기 (하나라도 실패하면 중단하도록 기존 로직 유지하되, 클린업 보장)
            # gather(return_exceptions=False) 시 예외가 즉시 발생하므로 try-except로 잡아야 함
            await asyncio.gather(*agent_tasks.values())
        except Exception as e:
            # 예외 발생 시(취소 포함) 실행 중인 모든 태스크 취소 및 프로세스 강제 종료
            logger.info("팀 모드 실행 중 예외 발생(%s), 하위 태스크 취소 시작: run_id=%s", type(e).__name__, run_id)
            await cancel_current(run_id=run_id)  # 프로세스 즉시 살해
            
            for task in agent_tasks.values():
                if not task.done():
                    task.cancel()
            
            # 모든 태스크가 취소/종료될 때까지 확실히 대기 (고아 태스크 방지)
            await asyncio.gather(*agent_tasks.values(), return_exceptions=True)
            raise

        async with self.db_lock:
            await update_run_status(self.db, run_id, "integrating")
        
        final = await self._integrate_results(user_message, agent_results, run_id=run_id)
        
        async with self.db_lock:
            # 통합 CLI 실행 도중 세션이 삭제됐을 수 있으므로 run 존재 여부 재확인
            if await self.db.get(models.Run, run_id) is None:
                logger.info("team 통합 완료 후 run이 삭제됨, DB 쓰기 건너뜀: run_id=%s", run_id)
                return
            await create_user_message(self.db, session_id, "reader", final, mode="team")
            await update_run_status(
                self.db, run_id, "done", response=final, mode="team", finished_at=datetime.now(UTC)
            )

    def _create_agent(self, agent_plan: AgentPlan, index: int) -> SubAgent:
        """AgentPlan → SubAgent 생성."""
        system_prompt = _PRESET_MAP.get(agent_plan.role, _PRESET_MAP["Researcher"])
        return SubAgent(
            name=f"{agent_plan.role}-{index + 1}",
            role_preset=agent_plan.role,
            system_prompt=system_prompt,
            llm_provider=self.llm_provider,
        )

    async def _integrate_results(self, user_message: str, results: dict[str, str], run_id: str | None = None) -> str:
        """모든 Agent 결과를 통합하는 CLI 호출."""
        parts = [f"[{name} 결과]:\n{result}" for name, result in results.items()]
        combined = "\n\n".join(parts)
        prompt = f"사용자 요청: {user_message}\n\n{combined}"
        model_to_use = self.session_model or settings.team_model
        return await self.llm_provider.stream_generate(
            _INTEGRATE_SYSTEM_PROMPT,
            prompt,
            model=model_to_use,
            run_id=run_id,
        )

    async def _assemble_context(self, results: dict[str, str], run_id: str | None = None) -> str | None:
        """이전 Agent 결과를 다음 Agent 컨텍스트로 조립."""
        if not results:
            return None

        parts = []
        for agent_name, result in results.items():
            if len(result) > CONTEXT_CHAR_LIMIT:
                result = await self._summarize_for_context(agent_name, result, run_id=run_id)
            parts.append(f"[{agent_name} 결과]:\n{result}")

        return "\n\n".join(parts)

    async def _summarize_for_context(self, agent_name: str, content: str, run_id: str | None = None) -> str:
        """긴 결과물을 다음 Agent에 전달할 수 있도록 CLI 호출로 요약."""
        model_to_use = self.session_model or settings.team_model
        return await self.llm_provider.stream_generate(
            _SUMMARIZE_SYSTEM_PROMPT,
            f"다음은 {agent_name}의 작업 결과입니다. 요약해주세요:\n\n{content}",
            on_line=None,
            model=model_to_use,
            run_id=run_id,
        )

    async def _summarize_history(self, history_text: str, run_id: str | None = None) -> str:
        """긴 대화 이력을 요약하여 핵심 맥락만 추출."""
        model_to_use = self.session_model or settings.team_model
        return await self.llm_provider.stream_generate(
            _SUMMARIZE_HISTORY_SYSTEM_PROMPT,
            f"다음 대화 이력을 요약해주세요:\n\n{history_text}",
            on_line=None,
            model=model_to_use,
            run_id=run_id,
        )
