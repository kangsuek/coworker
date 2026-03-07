"""Researcher 프리셋 시스템 프롬프트."""

from app.config import settings

# 웹 검색 불가 환경 (Claude CLI — MCP 미설정 시)
SYSTEM_PROMPT = settings.prompt_researcher

# 웹 검색 가능 환경 (Gemini CLI — Google Search 기본 활성화)
SYSTEM_PROMPT_WEB_SEARCH = settings.prompt_researcher_web_search
