from ollama import AsyncClient
from ollama._types import Message
from typing import AsyncGenerator, Optional

from src.config.prompt import PromptTemplate, PromptManager
from src.config.settings import settings
from src.core import LLMInterface
from src.tools import tool_register
from src.models import ChatHistory, Message as ChatMessage


class OllamaLLM(LLMInterface):
    def __init__(self):
        super().__init__()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL
        self.temperature = settings.LLM_TEMP
        self._async_client = (
            AsyncClient(host=self.base_url) if self.base_url else AsyncClient()
        )

    def _build_message(self, template: str, message: str) -> str:
        if template:
            try:
                prompt_template = PromptTemplate(template)
                prompt = PromptManager.get_prompt(prompt_template)
                return f"{prompt}{message}"
            except ValueError:
                pass
        return message

    async def _excute_tool(self, tool_call: Message.ToolCall) -> str:
        """辅助方法：执行工具并返回结果字符串"""
        func_name = tool_call.function.name
        arguments = dict(tool_call.function.arguments)
        return await tool_register.dispatch(func_name, arguments)

    async def response_stream(
        self,
        messages: ChatHistory,
        tools: Optional[list] = None,
    ) -> AsyncGenerator[str, None]:
        current_tools = tools if tools else tool_register.get_func_call_list()

        stream = await self._async_client.chat(
            model=self.model,
            messages=[message.model_dump() for message in messages.messages],
            options={"temperature": self.temperature},
            stream=True,
            tools=current_tools,
        )

        full_content = ""
        full_thinking = ""
        tool_calls = []

        has_started_thinking = False
        has_started_content = False

        async for chunk in stream:
            if hasattr(chunk.message, "thinking") and chunk.message.thinking:
                if not has_started_thinking:
                    yield "> **Thinking Process:**\n\n"
                    has_started_thinking = True

                full_thinking += chunk.message.thinking
                yield chunk.message.thinking

            elif chunk.message.content:
                if has_started_thinking and not has_started_content:
                    yield "\n\n---\n\n"
                    has_started_content = True

                full_content += chunk.message.content
                yield chunk.message.content

            if chunk.message.tool_calls:
                tool_calls.extend(chunk.message.tool_calls)

        if tool_calls:
            assistant_msg = ChatMessage(
                role="assistant", content=full_content, tool_calls=tool_calls
            )

            if full_thinking:
                assistant_msg.thinking = full_thinking

            messages.messages.append(assistant_msg)

            for tool_call in tool_calls:
                yield f"\n\n> 🛠️ **Calling Tool:** `{tool_call.function.name}`...\n"

                tool_result = await self._excute_tool(tool_call)

                messages.messages.append(
                    ChatMessage(
                        role="tool",
                        content=tool_result,
                        tool_name=tool_call.function.name,
                    )
                )

            async for chunk in self.response_stream(messages, tools=current_tools):
                yield chunk

        else:
            final_msg = ChatMessage(role="assistant", content=full_content)

            if full_thinking:
                final_msg.thinking = full_thinking

            messages.messages.append(final_msg)
