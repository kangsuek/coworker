"""LLM Provider Factory."""

from .base import LLMProvider
from .claude_cli import ClaudeCliProvider

_providers: dict[str, LLMProvider] = {
    "claude-cli": ClaudeCliProvider(),
    # 새로운 모델 연동 시 여기에 추가 (예: "openai": OpenAIProvider())
}


def get_allowed_provider_names() -> list[str]:
    """허용된 LLM provider 이름 목록을 반환합니다 (입력 검증용)."""
    return list(_providers.keys())


def get_provider(name: str) -> LLMProvider:
    """이름에 해당하는 LLM Provider를 반환합니다. 기본값은 claude-cli입니다."""
    return _providers.get(name, _providers["claude-cli"])


__all__ = ["get_provider", "get_allowed_provider_names", "LLMProvider"]
