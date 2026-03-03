"""Sub-Agent 기반 클래스."""

from __future__ import annotations

from collections.abc import Callable

from app.services.llm.base import LLMProvider


class SubAgent:
    """단일 역할을 수행하는 Sub-Agent."""

    def __init__(self, name: str, role_preset: str, system_prompt: str, llm_provider: LLMProvider) -> None:
        self.name = name
        self.role_preset = role_preset
        self.system_prompt = system_prompt
        self.llm_provider = llm_provider

    async def execute(
        self,
        task: str,
        context: str | None,
        on_line: Callable[[str], None] | None,
        model: str = "",
    ) -> str:
        """설정된 LLM Provider를 통해 태스크 수행. context는 이전 Agent 결과."""
        prompt = self._build_prompt(task, context)
        return await self.llm_provider.stream_generate(
            system_prompt=self.system_prompt,
            user_message=prompt,
            on_line=on_line,
            model=model,
        )

    def _build_prompt(self, task: str, context: str | None) -> str:
        if context:
            return f"[이전 작업 결과]\n{context}\n[/이전 작업 결과]\n\n{task}"
        return task
