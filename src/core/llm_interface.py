import json
import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional, TypeVar

from src.config import settings
from src.models import ChatHistory
from src.tools import tool_register

T = TypeVar("T")


class LLMInterface(ABC):
    """LLM 基类"""

    def __init__(self):
        super().__init__()

    @abstractmethod
    async def response_stream(
        self,
        messages: ChatHistory,
        tools: Optional[list] = None,
    ) -> AsyncGenerator[str | dict, None]:
        """以流式输出调用大模型

        Args:
            messages (ChatHistory): 历史记录
            tools (list): 工具调用

        Returns:
            AsyncGenerator[str, None]: 大模型的输出

        Yields:
            Iterator[AsyncGenerator[str | dict, None]]: 一个 chunk 的内容或者处理后的字典
        """
        yield ""
        raise NotImplementedError("子类必须实现 response_stream 方法")

    @staticmethod
    def resolve_tools(tools: Optional[list]) -> Optional[list]:
        if tools is None:
            return tool_register.get_func_call_list()
        return tools

    @staticmethod
    def normalize_tool_call(tool_call: Any, index: int = 0) -> dict[str, Any]:
        if isinstance(tool_call, dict):
            function = tool_call.get("function", {})
            arguments = function.get("arguments", "")
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments, ensure_ascii=False)
            return {
                "id": tool_call.get("id") or f"tool_call_{index}",
                "type": tool_call.get("type", "function"),
                "function": {
                    "name": function.get("name", ""),
                    "arguments": arguments or "",
                },
            }

        function = getattr(tool_call, "function", None)
        arguments = getattr(function, "arguments", "") if function else ""
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        elif arguments is None:
            arguments = ""

        return {
            "id": getattr(tool_call, "id", None) or f"tool_call_{index}",
            "type": getattr(tool_call, "type", None) or "function",
            "function": {
                "name": getattr(function, "name", "") if function else "",
                "arguments": arguments,
            },
        }

    @staticmethod
    def parse_tool_arguments(arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if not isinstance(arguments, str):
            raise ValueError("工具参数不是合法 JSON 字符串")
        stripped = arguments.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"工具参数 JSON 解析失败: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("工具参数必须解析为 JSON object")
        return parsed

    @staticmethod
    def is_rate_limit_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return True

        response = getattr(exc, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            return True

        return "429" in str(exc) or "rate limit" in str(exc).lower()

    async def call_with_backoff(
        self,
        operation: Callable[[], Awaitable[T]],
        provider_name: str,
    ) -> T:
        delay = settings.LLM_RETRY_BASE_DELAY
        last_exc: Exception | None = None

        for attempt in range(1, settings.LLM_RETRY_MAX_ATTEMPTS + 1):
            try:
                return await operation()
            except Exception as exc:
                last_exc = exc
                if not self.is_rate_limit_error(exc):
                    raise RuntimeError(
                        f"Error calling {provider_name} API: {str(exc)}"
                    ) from exc
                if attempt >= settings.LLM_RETRY_MAX_ATTEMPTS:
                    break
                await asyncio.sleep(min(delay, settings.LLM_RETRY_MAX_DELAY))
                delay = min(delay * 2, settings.LLM_RETRY_MAX_DELAY)

        raise RuntimeError(
            f"Error calling {provider_name} API after rate-limit retries: {str(last_exc)}"
        ) from last_exc

    async def _execute_tool(self, func_name: str, arguments: str) -> str:
        """执行工具并返回结果"""
        try:
            args_dict = self.parse_tool_arguments(arguments)
            return await tool_register.dispatch(func_name, args_dict)
        except ValueError as exc:
            return f"Error: {exc}"
        except Exception as e:
            return f"Error executing tool {func_name}: {str(e)}"
