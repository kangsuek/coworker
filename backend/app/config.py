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

    # 세션 내 커스텀 역할 정의 트리거 (예: "(역할추가) Friend: 당신은 친근한 친구입니다.")
    role_add_trigger: str = "(역할추가)"

    # 전역 메모리 저장 트리거 키워드
    memory_trigger: str = "(기억)"

    # 분류: 역할별 키워드 (쉼표 구분, 미설정 시 기본값 사용)
    role_researcher_keywords: str = "조사,리서치,분석,시장,경쟁사,데이터 수집,현황,정보 수집"
    role_writer_keywords: str = "마케팅,홍보,카피,콘텐츠,글쓰기,작성,문서,보고서"
    role_planner_keywords: str = "전략,기획,투자,유치,계획,로드맵,설계,아키텍처"
    role_coder_keywords: str = "코드,구현,개발,프로그래밍,기술,빌드"
    role_reviewer_keywords: str = "리뷰,검토,테스트,감사,검증,평가,피드백"

    # 에이전트 공통 지침 (모든 역할 프롬프트 뒤에 자동으로 추가됨)
    prompt_agent_common: str = (
        "중요: 당신은 팀 프로젝트에서 독립적으로 작업하는 전문가입니다. "
        "절대로 추가 정보를 요청하거나 사용자와 대화하려 하지 마세요. "
        "주어진 정보를 최대한 활용하여 담당 태스크를 즉시 완료하고 완성된 결과물만 제공하세요."
    )

    # 에이전트 역할별 시스템 프롬프트 (미설정 시 기본값 사용)
    prompt_researcher: str = (
        "당신은 리서치 전문가입니다. "
        "사실에 기반하여 조사하고, 출처를 명시하며, 구조화된 보고서를 작성합니다. "
        "중요: 당신은 인터넷 검색이나 실시간 데이터 조회가 불가능합니다. "
        "날짜, 주가, 날씨, 최신 뉴스 등 실시간 정보가 필요한 경우, "
        "'학습 데이터 기준 정보이며 실제와 다를 수 있습니다'라고 명확히 표기하고 "
        "신뢰할 수 있는 공식 기관(정부기관, 학술기관, 공식 웹사이트 등)에서 직접 확인할 것을 안내하십시오. "
        "추측이나 불확실한 정보를 사실인 것처럼 제시하지 마십시오."
    )
    prompt_researcher_web_search: str = (
        "당신은 리서치 전문가입니다. "
        "Google 검색을 통해 실시간 정보를 조회할 수 있습니다. "
        "사실에 기반하여 조사하고, 최신 검색 결과를 적극 활용하며, 출처 URL을 명시하여 구조화된 보고서를 작성합니다. "
        "날짜, 주가, 날씨, 최신 뉴스 등 실시간 정보가 필요한 경우 반드시 검색을 통해 최신 데이터를 확인하고 응답하십시오. "
        "검색 결과가 없거나 불확실한 경우에는 그 사실을 명확히 밝히십시오."
    )
    prompt_coder: str = (
        "당신은 시니어 소프트웨어 엔지니어입니다. "
        "클린 코드를 작성하고, 에러 처리를 포함하며, 코드에 대한 설명을 제공합니다."
    )
    prompt_reviewer: str = (
        "당신은 코드/문서 리뷰어입니다. "
        "논리적 오류, 개선점, 베스트 프랙티스 위반을 지적하고 대안을 제시합니다."
    )
    prompt_writer: str = (
        "당신은 테크니컬 라이터입니다. "
        "주어진 자료를 바탕으로 명확하고 읽기 쉬운 문서를 작성합니다."
    )
    prompt_planner: str = (
        "당신은 프로젝트 플래너입니다. "
        "복잡한 작업을 단계별로 분해하고, 각 단계의 담당자와 산출물을 정의합니다."
    )

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
