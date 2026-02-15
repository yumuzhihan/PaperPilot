from pathlib import Path
from datetime import datetime
from rich.style import Style
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown

from src.config import settings
from src.llms import llm_factory
from src.models.message import ChatHistory, Message
from src.utils import LoggerFactory, SHARED_CONSOLE


class AgentEngine:
    """核心 agent 调度器"""

    def __init__(self, system_prompt: str = "你是一个专业的学术助手。") -> None:
        self.llm = llm_factory.get_llm()
        self.console = SHARED_CONSOLE
        self.system_prompt = system_prompt
        self.memory = ChatHistory(messages=[])

    def _init_session(self):
        """初始化会话，清空历史并加载 System Prompt"""
        self.memory.messages.append(Message(role="system", content=self.system_prompt))

    def reset(self):
        """重置对话"""
        self._init_session()
        self.console.print("[dim]🔄 会话已重置[/dim]")

    async def chat(self, user_input: str):
        self.memory.messages.append(Message(role="user", content=user_input))

        full_response_text = ""
        current_thinking_text = ""

        is_thinking = False

        thinking_style = Style(color="bright_black", italic=True)
        content_style = Style(color="white")
        tool_style = Style(color="cyan")

        with Live(
            console=self.console, refresh_per_second=10, vertical_overflow="visible"
        ) as live:
            async for chunk in self.llm.response_stream(self.memory):
                if isinstance(chunk, str):
                    if "> **Thinking Process:**" in chunk:
                        is_thinking = True
                        chunk = chunk.replace("> **Thinking Process:**", "")

                    elif "\n\n---\n\n" in chunk:
                        is_thinking = False
                        chunk = chunk.replace("\n\n---\n\n", "")

                    elif "> 🛠️" in chunk:
                        is_thinking = False

                    if is_thinking:
                        current_thinking_text += chunk
                    else:
                        full_response_text += chunk

                    render_content = ""
                    if current_thinking_text:
                        render_content += f"> *Thinking:*\n> {current_thinking_text.replace(chr(10), chr(10)+'> ')}\n\n"

                    if full_response_text:
                        render_content += full_response_text

                    panel = Panel(
                        Markdown(render_content),
                        title="🤖 Agent Response",
                        subtitle="Thinking..." if is_thinking else "Finished",
                        border_style="green" if not is_thinking else "yellow",
                    )

                    live.update(panel)

        self._save_turn_log()

    def _save_turn_log(self):
        # 这里可以使用你的 Logger
        logger = LoggerFactory.get_logger("History")
        last_msg = self.memory.messages[-1]
        logger.info(
            f"Turn finished. Role: {last_msg.role}, Length: {len(last_msg.content)}"
        )

    def export_history(self, filename: str | None = None):
        """导出对话历史为 Markdown"""
        if filename is None:
            filename = f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        path = Path(settings.DATA_DIR) / filename

        with open(path, "w", encoding="utf-8") as f:
            for msg in self.memory.messages:
                role = msg.role.upper()
                content = msg.content
                f.write(f"# {role}\n\n{content}\n\n---\n\n")

        self.console.print(f"[green]历史记录已导出: {path}[/green]")
