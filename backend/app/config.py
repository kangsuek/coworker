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

    # 분류: Team 모드 트리거 헤더 (메시지가 이 값으로 시작하면 team 모드)
    # 빈 값이면 헤더 트리거 비활성 (예: (팀프로젝트))
    team_trigger_header: str = ""

    # 분류: 역할별 키워드 (쉼표 구분, 미설정 시 기본값 사용)
    role_researcher_keywords: str = "조사,리서치,분석,시장,경쟁사,데이터 수집,현황,정보 수집"
    role_writer_keywords: str = "마케팅,홍보,카피,콘텐츠,글쓰기,작성,문서,보고서"
    role_planner_keywords: str = "전략,기획,투자,유치,계획,로드맵,설계,아키텍처"
    role_coder_keywords: str = "코드,구현,개발,프로그래밍,기술,빌드"
    role_reviewer_keywords: str = "리뷰,검토,테스트,감사,검증,평가,피드백"

    @property
    def role_map(self) -> list[tuple[str, list[str]]]:
        # 순서가 우선순위 — Writer를 Planner보다 먼저 배치 (예: "마케팅 계획"은 Writer로 분류)
        ordered = [
            ("Researcher", self.role_researcher_keywords),
            ("Writer",     self.role_writer_keywords),
            ("Planner",    self.role_planner_keywords),
            ("Coder",      self.role_coder_keywords),
            ("Reviewer",   self.role_reviewer_keywords),
        ]
        return [
            (role, [kw.strip() for kw in kws.split(",") if kw.strip()])
            for role, kws in ordered
        ]

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
