import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Text, event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def run_pragmas(conn: AsyncConnection) -> None:
    """WAL 모드 + busy_timeout 활성화 (PRD ADR-002)."""
    await conn.execute(text("PRAGMA journal_mode=WAL;"))
    await conn.execute(text("PRAGMA busy_timeout=5000;"))


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


async def get_db():
    async with async_session() as session:
        yield session


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str | None] = mapped_column(Text, default=None)
    llm_provider: Mapped[str] = mapped_column(Text, default="claude-cli", server_default="claude-cli")
    llm_model: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user_messages: Mapped[list["UserMessage"]] = relationship(back_populates="session")
    agent_messages: Mapped[list["AgentMessage"]] = relationship(back_populates="session")
    runs: Mapped[list["Run"]] = relationship(back_populates="session")


class UserMessage(Base):
    __tablename__ = "user_messages"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(Text)  # user | reader
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(Text, default=None)  # solo | team
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    session: Mapped["Session"] = relationship(back_populates="user_messages")


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    sender: Mapped[str] = mapped_column(Text)
    role_preset: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="working")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    session: Mapped["Session"] = relationship(back_populates="agent_messages")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_message_id: Mapped[str] = mapped_column(ForeignKey("user_messages.id"))
    mode: Mapped[str | None] = mapped_column(Text, default=None)  # solo | team
    status: Mapped[str] = mapped_column(Text, default="queued")
    response: Mapped[str | None] = mapped_column(Text, default=None)
    agent_count: Mapped[int | None] = mapped_column(default=None)
    thinking_started_at: Mapped[datetime | None] = mapped_column(default=None)
    cli_started_at: Mapped[datetime | None] = mapped_column(default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    session: Mapped["Session"] = relationship(back_populates="runs")
