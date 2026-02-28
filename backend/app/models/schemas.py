from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# --- 요청 모델 ---

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


# --- 응답 모델 ---

class ChatResponse(BaseModel):
    run_id: str
    session_id: str


class AgentInfo(BaseModel):
    name: str
    role_preset: str
    status: str


class RunStatus(BaseModel):
    status: Literal[
        "queued", "thinking", "solo", "delegating",
        "working", "integrating", "done", "error", "cancelled",
    ]
    progress: str | None = None
    response: str | None = None
    mode: Literal["solo", "team"] | None = None
    agents: list[AgentInfo] | None = None


class AgentMessageOut(BaseModel):
    id: str
    sender: str
    role_preset: str
    content: str
    status: Literal["working", "done", "error", "cancelled"]
    created_at: datetime


class AgentMessagesResponse(BaseModel):
    messages: list[AgentMessageOut]
    has_more: bool = False


# --- 세션 모델 ---

class SessionOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class UserMessageOut(BaseModel):
    id: str
    role: str
    content: str
    mode: str | None
    created_at: datetime


class SessionDetail(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[UserMessageOut]


# --- CLI 분류 결과 (F-001) ---

class AgentPlan(BaseModel):
    role: Literal["Researcher", "Coder", "Reviewer", "Writer", "Planner"]
    task: str


class ClassificationResult(BaseModel):
    mode: Literal["solo", "team"]
    reason: str
    agents: list[AgentPlan] = []
    user_status_message: str | None = None
