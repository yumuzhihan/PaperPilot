import json
from typing import AsyncGenerator, Optional, List, Dict, Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from src.config.settings import settings
from src.core import LLMInterface
from src.tools import tool_register
from src.models import ChatHistory, Message as ChatMessage


class ZhipuLLM(LLMInterface):
    """
    智谱 AI (BigModel) 适配实现
    基于 OpenAI 兼容协议，针对智谱的 Thinking 参数和 Base URL 进行了特定适配
    """

    def __init__(self):
        super().__init__()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL or "https://open.bigmodel.cn/api/paas/v4/"
        self.api_key = settings.LLM_API_KEY
        self.temperature = settings.LLM_TEMP

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _convert_messages(
        self, messages: ChatHistory
    ) -> List[ChatCompletionMessageParam]:
        """将内部 ChatHistory 转换为 OpenAI/智谱 兼容的消息列表"""
        openai_messages = []
        for msg in messages.messages:
            if msg.role == "tool":
                openai_messages.append(
                    {
                        "role": "tool",
                        "content": msg.content,
                        "tool_call_id": getattr(msg, "tool_call_id", None)
                        or getattr(msg, "tool_name", None),
                    }
                )
            elif hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_data = []
                for tc in msg.tool_calls:
                    if isinstance(tc, dict):
                        tool_calls_data.append(tc)
                    else:
                        tool_calls_data.append(
                            {
                                "id": getattr(tc, "id", None),
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": (
                                        tc.function.arguments
                                        if isinstance(tc.function.arguments, str)
                                        else json.dumps(tc.function.arguments)
                                    ),
                                },
                            }
                        )

                openai_messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": tool_calls_data,
                    }
                )
            else:
                openai_messages.append({"role": msg.role, "content": msg.content})
        return openai_messages

    async def response_stream(
        self,
        messages: ChatHistory,
        tools: Optional[list] = None,
    ) -> AsyncGenerator[str, None]:
        current_tools = tools if tools else tool_register.get_func_call_list()
        api_messages = self._convert_messages(messages)

        request_params = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,
            "temperature": self.temperature,
        }

        if current_tools:
            request_params["tools"] = current_tools
            request_params["tool_choice"] = "auto"

        extra_body = {}

        if settings.LLM_THINK:
            extra_body["thinking"] = {"type": "enabled"}

        if extra_body:
            request_params["extra_body"] = extra_body

        try:
            stream = await self.client.chat.completions.create(**request_params)
        except Exception as e:
            yield f"Error calling Zhipu API: {str(e)}"
            return

        full_content = ""
        full_thinking = ""

        tool_calls_buffer: Dict[int, Dict[str, Any]] = {}

        has_started_thinking = False
        has_started_content = False

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                if not has_started_thinking:
                    yield "> **Thinking Process:**\n\n"
                    has_started_thinking = True

                full_thinking += delta.reasoning_content
                yield delta.reasoning_content

            if delta.content:
                if has_started_thinking and not has_started_content:
                    yield "\n\n---\n\n"
                    has_started_content = True

                full_content += delta.content
                yield delta.content

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    index = tc.index

                    if index not in tool_calls_buffer:
                        tool_calls_buffer[index] = {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name or "",
                                "arguments": tc.function.arguments or "",
                            },
                        }
                        if tc.function.name:
                            yield f"\n\n> 🛠️ **Calling Tool:** `{tc.function.name}`\n"
                    else:
                        if tc.function.arguments:
                            tool_calls_buffer[index]["function"][
                                "arguments"
                            ] += tc.function.arguments

        if tool_calls_buffer:
            final_tool_calls = list(tool_calls_buffer.values())

            assistant_msg = ChatMessage(
                role="assistant", content=full_content, tool_calls=final_tool_calls
            )
            if full_thinking:
                assistant_msg.thinking = full_thinking

            messages.messages.append(assistant_msg)

            for tool_call in final_tool_calls:
                func_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                call_id = tool_call["id"]

                tool_result = await self._execute_tool(func_name, arguments)

                yield tool_result

                messages.messages.append(
                    ChatMessage(
                        role="tool",
                        content=str(tool_result),
                        tool_name=func_name,
                        tool_call_id=call_id,
                    )
                )

            async for chunk in self.response_stream(messages, tools=current_tools):
                yield chunk

        else:
            final_msg = ChatMessage(role="assistant", content=full_content)
            if full_thinking:
                final_msg.thinking = full_thinking
            messages.messages.append(final_msg)
