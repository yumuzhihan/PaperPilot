from ollama import AsyncClient
from typing import AsyncGenerator, Optional

from src.config.settings import settings
from src.core import LLMInterface
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

    async def response_stream(
        self,
        messages: ChatHistory,
        tools: Optional[list] = None,
    ) -> AsyncGenerator[str | dict, None]:
        current_tools = self.resolve_tools(tools)

        request_kwargs = {
            "model": self.model,
            "messages": [message.model_dump() for message in messages.messages],
            "options": {"temperature": self.temperature},
            "stream": True,
        }
        if current_tools is not None:
            request_kwargs["tools"] = current_tools

        stream = await self.call_with_backoff(
            lambda: self._async_client.chat(**request_kwargs),
            "Ollama",
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

                # for tool_call in chunk.message.tool_calls:
                #     yield f"\n\n> 🛠️ **Calling Tool:** `{tool_call.function.name}`\n"

        if tool_calls:
            normalized_tool_calls = [
                self.normalize_tool_call(tool_call, index)
                for index, tool_call in enumerate(tool_calls)
            ]
            assistant_msg = ChatMessage(
                role="assistant", content=full_content, tool_calls=normalized_tool_calls
            )

            if full_thinking:
                assistant_msg.thinking = full_thinking

            messages.messages.append(assistant_msg)

            yield {"type": "tool_call_request", "tool_calls": normalized_tool_calls}
            return

        else:
            final_msg = ChatMessage(role="assistant", content=full_content)

            if full_thinking:
                final_msg.thinking = full_thinking

            messages.messages.append(final_msg)
