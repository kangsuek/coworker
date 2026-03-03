"""LLM Provider Base Interface."""

import abc
from collections.abc import Callable


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    async def stream_generate(
        self,
        system_prompt: str,
        user_message: str,
        on_line: Callable[[str], None] | None = None,
        model: str = "",
        **kwargs,
    ) -> str:
        """Stream output from LLM model."""
        pass
