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

    # Agent
    max_sub_agents: int = 5

    # Session
    session_ttl_seconds: int = 3600
    db_path: str = "./data/coworker.db"

    # Server
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def database_url(self) -> str:
        db = Path(self.db_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db}"


settings = Settings()
