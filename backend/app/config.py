from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Claude CLI
    claude_cli_path: str = "claude"
    claude_cli_timeout: int = 120

    # 모델 설정 (빈 문자열 = CLI 기본값 사용)
    solo_model: str = ""   # 분류 + Solo 응답용 (예: claude-haiku-4-5-20251001)
    team_model: str = ""   # Team 에이전트 + 통합용 (예: claude-sonnet-4-6)

    # Agent
    max_sub_agents: int = 5

    # Session
    session_ttl_seconds: int = 3600
    db_path: str = "./data/coworker.db"

    # Server
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        db = Path(self.db_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db}"


settings = Settings()
