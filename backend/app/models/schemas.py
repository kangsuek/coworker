from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _ensure_utc(dt: datetime) -> datetime:
    """SQLite에서 읽은 naive datetime을 UTC로 간주해 타임존을 붙인다.

    JSON 직렬화 시 Z 포함 → 프론트에서 로컬 시각으로 정확히 변환.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


UTCDatetime = Annotated[datetime, BeforeValidator(_ensure_utc)]

# --- 요청 모델 ---


class ChatRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    session_id: str | None = None
    message: str
    llm_provider: str | None = None
    llm_model: str | None = None


# --- 응답 모델 ---


class ChatResponse(BaseModel):
    run_id: str
    session_id: str


class AgentInfo(BaseModel):
    name: str
    role_preset: str
    status: str


class TimingInfo(BaseModel):
    queued_at: UTCDatetime | None = None
    thinking_started_at: UTCDatetime | None = None
    cli_started_at: UTCDatetime | None = None
    finished_at: UTCDatetime | None = None


class RunStatus(BaseModel):
    status: Literal[
        "queued",
        "thinking",
        "solo",
        "delegating",
        "working",
        "integrating",
        "done",
        "error",
        "cancelled",
    ]
    progress: str | None = None
    response: str | None = None
    mode: Literal["solo", "team"] | None = None
    model: str | None = None
    agents: list[AgentInfo] | None = None
    timing: TimingInfo | None = None


class AgentMessageOut(BaseModel):
    id: str
    sender: str
    role_preset: str
    content: str
    status: Literal["working", "done", "error", "cancelled"]
    created_at: UTCDatetime


class AgentMessagesResponse(BaseModel):
    messages: list[AgentMessageOut]
    has_more: bool = False


# --- 세션 모델 ---


class SessionOut(BaseModel):
    id: str
    title: str | None
    llm_provider: str
    llm_model: str | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class UserMessageOut(BaseModel):
    id: str
    role: str
    content: str
    mode: str | None
    run_id: str | None = None
    model: str | None = None
    timing: TimingInfo | None = None
    created_at: UTCDatetime


class SessionDetail(BaseModel):
    id: str
    title: str | None
    llm_provider: str
    llm_model: str | None
    created_at: UTCDatetime
    updated_at: UTCDatetime
    messages: list[UserMessageOut]
    last_team_run_id: str | None = None


# --- CLI 분류 결과 (F-001) ---


class AgentPlan(BaseModel):
    role: Literal["Researcher", "Coder", "Reviewer", "Writer", "Planner"]
    task: str
    depends_on: list[int] = []


class ClassificationResult(BaseModel):
    model_config = ConfigDict(strict=True)
    mode: Literal["solo", "team"]
    reason: str
    agents: list[AgentPlan] = []
    user_status_message: str | None = None


class LLMClassificationResponse(BaseModel):
    """LLM이 각 태스크의 역할과 의존성을 분석한 결과."""
    agents: list[AgentPlan]
