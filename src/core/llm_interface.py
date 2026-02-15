from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from src.models import ChatHistory


class LLMInterface(ABC):
    """LLM 基类"""

    def __init__(self):
        super().__init__()

    @abstractmethod
    async def response_stream(
        self,
        messages: ChatHistory,
        tools: Optional[list] = None,
    ) -> AsyncGenerator[str, None]:
        """以流式输出调用大模型

        Args:
            messages (ChatHistory): 历史记录
            tools (list): 工具调用

        Returns:
            AsyncGenerator[str, None]: 大模型的输出

        Yields:
            Iterator[AsyncGenerator[str, None]]: 一个 chunk 的内容
        """
        yield ""
        raise NotImplementedError("子类必须实现 response_stream 方法")
