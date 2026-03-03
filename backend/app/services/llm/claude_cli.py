"""Claude CLI Provider implementation."""

from collections.abc import Callable

from app.services.cli_service import call_claude_streaming, execute_with_lock

from .base import LLMProvider


class ClaudeCliProvider(LLMProvider):
    async def stream_generate(
        self,
        system_prompt: str,
        user_message: str,
        on_line: Callable[[str], None] | None = None,
        model: str = "",
        **kwargs,
    ) -> str:
        """Claude CLI를 통해 모델을 호출합니다."""
        return await execute_with_lock(
            call_claude_streaming(
                system_prompt=system_prompt,
                user_message=user_message,
                on_line=on_line,
                model=model,
                **kwargs
            )
        )
