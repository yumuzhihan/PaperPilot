import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from src.models import ChatHistory
from src.tools import tool_register


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

    async def _execute_tool(self, func_name: str, arguments: str) -> str:
        """执行工具并返回结果"""
        try:
            args_dict = json.loads(arguments)
            return await tool_register.dispatch(func_name, args_dict)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments: {arguments}"
        except Exception as e:
            return f"Error executing tool {func_name}: {str(e)}"
