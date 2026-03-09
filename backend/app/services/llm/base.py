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
        file_paths: list[str] | None = None,
        **kwargs,
    ) -> str:
        """Stream output from LLM model.

        Args:
            file_paths: 이미지/PDF 파일 경로 목록. CLI 네이티브 플래그로 전달됨.
                        텍스트/코드 파일은 reader.py에서 프롬프트에 삽입된 후 이 목록에 포함되지 않음.
        """
        pass
