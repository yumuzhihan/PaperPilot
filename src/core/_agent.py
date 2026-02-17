from pathlib import Path
from datetime import datetime
import json
import re
from rich.rule import Rule
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

        self.console.print("")

        is_thinking = False

        async for chunk in self.llm.response_stream(self.memory):
            if isinstance(chunk, str):

                if "> 🛠️" in chunk:
                    self.console.print()

                    tool_name = "Unknown"
                    match = re.search(r"`(.*?)`", chunk)
                    if match:
                        tool_name = match.group(1)

                    if is_thinking:
                        self.console.print("\n")
                        is_thinking = False
                    self.console.print(
                        Rule(
                            f"🛠️ Calling: [bold cyan]{tool_name}[/bold cyan]",
                            style="blue",
                            align="center",
                        )
                    )
                    continue

                if "> **Thinking Process:**" in chunk:
                    self.console.print()
                    is_thinking = True
                    chunk = chunk.replace("> **Thinking Process:**\n\n", "").replace(
                        "> **Thinking Process:**", ""
                    )
                    self.console.print("\n[dim]⚡ Thinking:[/dim]\n", end="")

                elif "\n\n---\n\n" in chunk:
                    self.console.print()

                    is_thinking = False
                    chunk = chunk.replace("\n\n---\n\n", "")
                    self.console.print("\n")

                if chunk:
                    if is_thinking:
                        self.console.print(chunk, style="dim", end="")
                    else:
                        self.console.print(chunk, end="")

        self.console.print("\n")
        self.console.print(Rule(style="dim"))
        self._save_turn_log()

    def _save_turn_log(self):
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


def optimize_tool_args(tool_name, args_json_str):
    """
    优化工具参数显示：
    1. 如果是 write_file，截断 content 内容。
    2. 尝试格式化 JSON 以便漂亮显示。
    """
    try:
        args = json.loads(args_json_str)

        if tool_name == "write_file" and "content" in args:
            content = args["content"]
            lines = content.split("\n")
            if len(lines) > 5:
                preview = "\n".join(lines[:5])
                args["content"] = f"{preview}\n\n... (剩余 {len(lines)-5} 行已省略) ..."

        return json.dumps(args, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        if tool_name == "write_file":
            return re.sub(
                r'("content":\s*").*?(")',
                r"\1... (内容过长已隐藏) ...\2",
                args_json_str,
                flags=re.DOTALL,
            )
        return args_json_str
