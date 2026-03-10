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
from pathlib import Path

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.presets import coder, planner, researcher, reviewer, writer
from app.agents.sub_agent import SubAgent
from app.config import settings
from app.services import settings_service
from app.models import db as models
from app.models.schemas import AgentPlan, ClassificationResult
from app.services.classification import classify_message
from app.services.cli_service import LineBufferFlusher, _cancelled_runs, cancel_current
from app.services.llm import get_provider
from app.services.session_service import (
    add_custom_role,
    create_agent_message,
    create_memory,
    create_user_message,
    get_all_memories,
    get_custom_roles,
    get_recent_messages,
    update_agent_message_content,
    update_agent_message_status,
    update_run_status,
)

logger = logging.getLogger(__name__)

CONTEXT_CHAR_LIMIT = int(os.getenv("CONTEXT_CHAR_LIMIT", "3000"))
_HISTORY_MSG_LIMIT = 20  # 최근 20개 메시지 (약 10턴)


_BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"
})

_TEXT_INJECT_LIMIT = 20000  # 파일당 최대 삽입 글자 수


def _split_files(file_paths: list[str]) -> tuple[list[str], list[str]]:
    """파일 경로 목록을 네이티브(이미지/PDF) vs 텍스트(프롬프트 인젝션)으로 분리.

    Returns:
        (native_paths, text_paths)
    """
    native: list[str] = []
    text_files: list[str] = []
    for p in file_paths:
        ext = Path(p).suffix.lower()
        if ext in _BINARY_EXTENSIONS:
            native.append(p)
        else:
            text_files.append(p)
    return native, text_files


def _inject_text_files(user_message: str, text_file_paths: list[str]) -> str:
    """텍스트/코드 파일 내용을 user_message 뒤에 삽입.

    존재하지 않는 파일은 건너뜀.
    _TEXT_INJECT_LIMIT 초과 파일 내용은 잘라서 삽입.
    """
    if not text_file_paths:
        return user_message

    parts = [user_message, "\n\n[첨부 파일]"]
    for path in text_file_paths:
        p = Path(path)
        if not p.exists():
            logger.warning("첨부 파일 없음, 건너뜀: %s", path)
            continue
        try:
            content = p.read_text(errors="replace")
        except OSError:
            logger.warning("첨부 파일 읽기 실패, 건너뜀: %s", path)
            continue
        if len(content) > _TEXT_INJECT_LIMIT:
            content = content[:_TEXT_INJECT_LIMIT] + "\n...(이하 생략)"
        parts.append(f"\n--- {p.name} ---\n{content}")

    return "\n".join(parts)


def _today_context() -> str:
    """오늘 날짜를 에이전트 프롬프트 상단에 삽입할 컨텍스트 문자열로 반환."""
    today = datetime.now(UTC).strftime("%Y년 %m월 %d일")
    return f"[오늘 날짜: {today}]\n\n"


def _memory_context(memories: list) -> str:
    """전역 메모리 목록을 프롬프트 컨텍스트 문자열로 변환.

    메모리가 없을 때도 빈 섹션을 명시하여 이전 대화 이력에 남은
    삭제된 메모리 내용을 LLM이 재참조하지 않도록 방지한다.
    """
    if not memories:
        return (
            "[전역 메모리 — 현재 저장된 메모리가 없습니다. "
            "이전 대화에서 메모리 내용이 언급됐더라도 이미 삭제된 것이므로 절대 참조하지 마세요.]\n\n"
        )
    items = "\n".join(f"- {m.content}" for m in memories)
    return (
        f"[전역 메모리 — 아래 목록만 유효합니다. 목록에 없는 내용은 삭제된 메모리이므로 참조하지 마세요.]\n"
        f"{items}\n\n"
    )


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

def _get_agent_common_instruction() -> str:
    return "\n\n" + (settings_service.get("prompt_agent_common") or settings.prompt_agent_common)


def _get_preset_map() -> dict[str, str]:
    common = _get_agent_common_instruction()
    return {
        "Researcher": (settings_service.get("prompt_researcher") or researcher.SYSTEM_PROMPT) + common,
        "Coder": (settings_service.get("prompt_coder") or coder.SYSTEM_PROMPT) + common,
        "Reviewer": (settings_service.get("prompt_reviewer") or reviewer.SYSTEM_PROMPT) + common,
        "Writer": (settings_service.get("prompt_writer") or writer.SYSTEM_PROMPT) + common,
        "Planner": (settings_service.get("prompt_planner") or planner.SYSTEM_PROMPT) + common,
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
        self, session_id: str, user_message: str, run_id: str,
        file_paths: list[str] | None = None,
    ) -> None:
        """메시지 처리: 분류 → Solo/Team 실행."""
        file_paths = file_paths or []
        try:
            # 현재 run의 user_message_id를 찾아 대화 이력에서 제외
            run = await self.db.get(models.Run, run_id)
            current_msg_id = run.user_message_id if run else None

            session = await self.db.get(models.Session, session_id)
            provider_name = session.llm_provider if session and session.llm_provider else "gemini-cli"
            self.llm_provider = get_provider(provider_name)
            self.provider_name = provider_name
            self.session_model = session.llm_model if session else None

            # 전역 메모리 저장 트리거 감지
            _MEMORY_TRIGGER = settings_service.get("memory_trigger") or settings.memory_trigger
            _team_header = (settings_service.get("team_trigger_header") or settings.team_trigger_header).strip()
            # BUG-07: 팀모드 메시지에 (기억)이 포함돼도 메모리 트리거로 오인식하지 않도록 예외 처리
            _is_team_trigger = bool(_team_header and user_message.startswith(_team_header))
            if not _is_team_trigger and _MEMORY_TRIGGER in user_message:
                # BUG-02: thinking 상태를 메모리 처리 전에 먼저 업데이트 (queued→done 직접 점프 방지)
                async with self.db_lock:
                    await update_run_status(
                        self.db, run_id, "thinking", thinking_started_at=datetime.now(UTC)
                    )
                # BUG-03: 직접 저장은 "(기억) " (공백 필수) 형식만 허용
                _is_direct = (
                    user_message.startswith(_MEMORY_TRIGGER)
                    and len(user_message) > len(_MEMORY_TRIGGER)
                    and user_message[len(_MEMORY_TRIGGER)] in (' ', '\t', '\n')
                )
                if _is_direct:
                    # 직접 저장: "(기억) 기억할 내용"
                    content = user_message[len(_MEMORY_TRIGGER):].strip()
                    if not content:
                        reply = f"⚠️ 기억할 내용을 입력해주세요.\n\n형식: `{_MEMORY_TRIGGER} 기억할 내용`"
                        async with self.db_lock:
                            await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                            await update_run_status(
                                self.db, run_id, "done",
                                response=reply, mode="solo", finished_at=datetime.now(UTC),
                            )
                        return
                else:
                    # LLM 생성 후 저장: "대화를 요약해서 (기억)에 저장해줘" 등 자연어 요청
                    history = await get_recent_messages(
                        self.db, session_id, limit=_HISTORY_MSG_LIMIT, exclude_id=current_msg_id
                    )
                    model_to_use = self.session_model or self.session_model or ""
                    _MEMORY_GEN_PROMPT = (
                        "사용자의 요청을 처리하여 전역 메모리에 저장할 내용을 생성하세요. "
                        "저장할 내용만 간결하게 출력하세요. 설명, 인사, 확인 문구는 절대 포함하지 마세요."
                    )
                    prompt = (
                        _today_context()
                        + _build_conversation_prompt(user_message, history)
                    )
                    content = await self.llm_provider.stream_generate(
                        _MEMORY_GEN_PROMPT, prompt, model=model_to_use, run_id=run_id
                    )
                    content = content.strip()
                    # BUG-04: LLM이 빈 응답 반환 시 빈 메모리 저장 차단
                    if not content:
                        reply = "⚠️ 메모리 생성에 실패했습니다. (LLM이 빈 응답 반환)"
                        async with self.db_lock:
                            await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                            await update_run_status(
                                self.db, run_id, "done",
                                response=reply, mode="solo", finished_at=datetime.now(UTC),
                            )
                        return

                # BUG-06: create_memory를 db_lock 블록 안에서 실행 (코드 일관성)
                async with self.db_lock:
                    mem = await create_memory(self.db, content)
                    reply = f"✅ 기억했습니다.\n\n> {mem.content}"
                    await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                    await update_run_status(
                        self.db, run_id, "done",
                        response=reply, mode="solo", finished_at=datetime.now(UTC),
                    )
                return

            # 커스텀 역할 정의 지시문 감지: "(역할추가) 역할명: 프롬프트"
            trigger = (settings_service.get("role_add_trigger") or settings.role_add_trigger).strip()
            if trigger and user_message.startswith(trigger):
                rest = user_message[len(trigger):].strip()
                if ":" in rest:
                    role_name, prompt = rest.split(":", 1)
                    role_name = role_name.strip()
                    prompt = prompt.strip()
                    if role_name and prompt:
                        # SEC-05: 커스텀 역할 입력 길이 검증
                        if len(role_name) > 50:
                            reply = f"⚠️ 역할명은 50자 이내로 입력해주세요. (현재: {len(role_name)}자)"
                            async with self.db_lock:
                                await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                                await update_run_status(self.db, run_id, "done", response=reply, mode="solo", finished_at=datetime.now(UTC))
                            return
                        if len(prompt) > 2000:
                            reply = f"⚠️ 역할 프롬프트는 2000자 이내로 입력해주세요. (현재: {len(prompt)}자)"
                            async with self.db_lock:
                                await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                                await update_run_status(self.db, run_id, "done", response=reply, mode="solo", finished_at=datetime.now(UTC))
                            return
                        await add_custom_role(self.db, session_id, role_name, prompt)
                        reply = f"✅ 역할 **{role_name}** 이(가) 이 세션에 등록되었습니다.\n\n> {prompt}"
                        async with self.db_lock:
                            await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                            await update_run_status(
                                self.db, run_id, "done",
                                response=reply, mode="solo", finished_at=datetime.now(UTC),
                            )
                        return
                # 형식 오류 안내
                reply = f"⚠️ 역할 추가 형식이 올바르지 않습니다.\n\n형식: `{trigger} 역할명: 시스템 프롬프트`\n\n예시: `{trigger} Friend: 당신은 친근한 친구입니다.`"
                async with self.db_lock:
                    await create_user_message(self.db, session_id, "reader", reply, mode="solo")
                    await update_run_status(
                        self.db, run_id, "done",
                        response=reply, mode="solo", finished_at=datetime.now(UTC),
                    )
                return

            # 전역 메모리 로드 (모든 프롬프트에 자동 주입)
            self.memories = await get_all_memories(self.db)

            # 세션 커스텀 역할 로드 (팀모드 분류 시 활용)
            self.custom_roles = await get_custom_roles(self.db, session_id)

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
                text = await self._solo_respond(user_message, history, run_id=run_id, file_paths=file_paths)
                
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
                await self._team_execute(result, user_message, session_id, run_id, file_paths=file_paths)
        except Exception as e:
            logger.exception("process_message 실패: run_id=%s", run_id)

            async with self.db_lock:
                # TypeError 등으로 SQLAlchemy 세션이 롤백 상태일 수 있으므로 먼저 롤백
                try:
                    await self.db.rollback()
                except Exception:
                    pass

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
        finally:
            # BUG-C01: 백그라운드 태스크 종료 시점에 _cancelled_runs 정리
            # (update_run_status에서 "cancelled" 시 정리하지 않으므로 여기서 수행)
            _cancelled_runs.discard(run_id)

    @property
    def _CLASSIFY_MODEL(self) -> dict[str, str]:
        return {
            "claude-cli": self.session_model or "",
            "gemini-cli": self.session_model or "",
        }

    async def _classify(self, user_message: str) -> ClassificationResult:
        """Solo/Team 분류.

        규칙 기반으로 1차 판정 후, Team 모드일 경우 경량 LLM(Haiku/Flash)으로
        역할(Role) 및 의존성(depends_on)을 정교화한다.
        사용자가 선택한 프로바이더를 그대로 사용하여 불필요한 cold start를 방지한다.
        """
        classify_model = self._CLASSIFY_MODEL.get(
            self.provider_name, self.session_model or ""
        )
        result = await classify_message(
            user_message,
            llm_provider=self.llm_provider,
            classify_model=classify_model,
            custom_roles=getattr(self, "custom_roles", None),
        )
        logger.info(
            "_classify: mode=%s agents=%s provider=%s model=%s",
            result.mode, result.agents, self.provider_name, classify_model,
        )
        return result

    async def _solo_respond(
        self, user_message: str, history: list | None = None, run_id: str | None = None,
        file_paths: list[str] | None = None,
    ) -> str:
        """Solo 모드 응답 생성. history가 있으면 대화 이력을 프롬프트에 포함.

        file_paths가 있으면:
          - 텍스트/코드 파일은 프롬프트에 내용 삽입
          - 이미지/PDF는 file_paths kwarg로 CLI에 전달 (Phase 3에서 --file 플래그로 연결)

        run_id가 있으면 LineBufferFlusher로 0.5초마다 SSE solo_content 이벤트를 broadcast하여
        프론트엔드 채팅창에 실시간 스트리밍 표시한다.
        """
        file_paths = file_paths or []
        native_files, text_files = _split_files(file_paths)

        memories = getattr(self, "memories", [])
        enriched_message = _inject_text_files(user_message, text_files)
        prompt = _today_context() + _memory_context(memories) + _build_conversation_prompt(enriched_message, history or [])
        model_to_use = self.session_model or self.session_model or ""

        if not run_id:
            return await self.llm_provider.stream_generate(
                self.SOLO_SYSTEM_PROMPT,
                prompt,
                model=model_to_use,
                run_id=run_id,
                file_paths=native_files,
            )

        # SSE 실시간 스트리밍용 콜백
        accumulated: list[str] = []

        async def solo_flush_callback(chunks: list[str]) -> None:
            if not chunks:
                return
            accumulated.extend(chunks)
            content = "".join(accumulated)
            try:
                from app.services.stream_service import stream_manager
                await stream_manager.broadcast(run_id, {
                    "type": "solo_content",
                    "run_id": run_id,
                    "content": content,
                })
            except Exception:
                pass

        flusher = LineBufferFlusher(solo_flush_callback, flush_interval=0.5)
        flusher.start()

        def on_line(chunk: str) -> None:
            flusher.append(chunk)

        try:
            result = await self.llm_provider.stream_generate(
                self.SOLO_SYSTEM_PROMPT,
                prompt,
                on_line=on_line,
                model=model_to_use,
                run_id=run_id,
                file_paths=native_files,
            )
        finally:
            await flusher.stop()

        return result

    async def _team_execute(
        self,
        classification: ClassificationResult,
        user_message: str,
        session_id: str,
        run_id: str,
        file_paths: list[str] | None = None,
    ) -> None:
        """Team 모드 전체 흐름 (병렬 실행 지원)."""
        file_paths = file_paths or []
        native_files, text_files = _split_files(file_paths)
        enriched_message = _inject_text_files(user_message, text_files)
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
        started_count = 0   # 시작된 에이전트 수 (progress 표시용)
        completed_count = 0
        total_count = len(classification.agents)
        progress_lock = asyncio.Lock()  # started_count / completed_count 보호

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

                # progress 업데이트 (락으로 started_count 원자적 증가)
                nonlocal started_count, completed_count
                async with progress_lock:
                    started_count += 1
                    progress_str = f"{started_count}/{total_count}"
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
                    f"{_today_context()}"
                    f"{_memory_context(getattr(self, 'memories', []))}"
                    f"[전체 프로젝트 요청]\n{enriched_message}\n\n"
                    f"[당신의 담당 태스크]\n{agent_plan.task}"
                )

                try:
                    model_to_use = self.session_model or self.session_model or ""
                    result = await agent.execute(full_task, full_context, on_line, model=model_to_use, run_id=run_id, file_paths=native_files)
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
                async with progress_lock:
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

        # BUG-H02: 모든 에이전트 완료 후 통합 전 취소 여부 재확인
        if run_id in _cancelled_runs:
            logger.info("에이전트 완료 후 취소 감지, 통합 생략: run_id=%s", run_id)
            return
        run_mid = await self.db.get(models.Run, run_id)
        if run_mid is None or run_mid.status == "cancelled":
            logger.info("에이전트 완료 후 DB 취소 감지, 통합 생략: run_id=%s", run_id)
            return

        async with self.db_lock:
            await update_run_status(self.db, run_id, "integrating")

        final = await self._integrate_results(
            enriched_message, agent_results, run_id=run_id,
        )
        
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
        """AgentPlan → SubAgent 생성.

        Gemini CLI는 Google Search가 기본 활성화되어 있으므로
        Researcher에 웹 검색 활용 지침을 적용한다.
        """
        preset_map = _get_preset_map()
        common = _get_agent_common_instruction()
        custom_roles = getattr(self, "custom_roles", {}) or {}
        if agent_plan.role in custom_roles:
            system_prompt = custom_roles[agent_plan.role] + common
        elif agent_plan.role == "Researcher" and self.provider_name == "gemini-cli":
            researcher_web = settings_service.get("prompt_researcher_web_search") or researcher.SYSTEM_PROMPT_WEB_SEARCH
            system_prompt = researcher_web + common
        else:
            system_prompt = preset_map.get(agent_plan.role, preset_map["Researcher"])
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
        prompt = f"{_today_context()}사용자 요청: {user_message}\n\n{combined}"
        model_to_use = self.session_model or self.session_model or ""
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
        model_to_use = self.session_model or self.session_model or ""
        return await self.llm_provider.stream_generate(
            _SUMMARIZE_SYSTEM_PROMPT,
            f"다음은 {agent_name}의 작업 결과입니다. 요약해주세요:\n\n{content}",
            on_line=None,
            model=model_to_use,
            run_id=run_id,
        )

    async def _summarize_history(self, history_text: str, run_id: str | None = None) -> str:
        """긴 대화 이력을 요약하여 핵심 맥락만 추출."""
        model_to_use = self.session_model or self.session_model or ""
        return await self.llm_provider.stream_generate(
            _SUMMARIZE_HISTORY_SYSTEM_PROMPT,
            f"다음 대화 이력을 요약해주세요:\n\n{history_text}",
            on_line=None,
            model=model_to_use,
            run_id=run_id,
        )
