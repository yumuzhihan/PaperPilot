import re
from typing import Iterable
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .logger_factory import SHARED_CONSOLE


class SmartMarkdownStreamer:
    """
    智能流式 Markdown 渲染器
    功能：自动检测段落结束，将已完成的段落“固化”到控制台，
    只保留正在生成的段落进行 Live 刷新
    """

    def __init__(self, console: Console = SHARED_CONSOLE):
        self.console = console
        self.code_block_pattern = re.compile(r"```")

    def stream(self, token_generator: Iterable[str], title: str = "正在生成..."):
        """
        Args:
            token_generator: LLM 的流式输出迭代器
            title: Live 面板的标题
        Returns:
            full_text: 最终生成的完整文本
        """
        full_text = ""
        frozen_text = ""
        buffer_text = ""
        in_code_block = False

        with Live(
            console=self.console,
            auto_refresh=True,
            refresh_per_second=10,
            vertical_overflow="visible",
        ) as live:

            for chunk in token_generator:
                full_text += chunk
                buffer_text += chunk

                if chunk.count("```") % 2 != 0:
                    in_code_block = not in_code_block

                if "\n\n" in buffer_text and not in_code_block:

                    parts = buffer_text.split("\n\n")

                    if len(parts) > 1:
                        to_freeze = "\n\n".join(parts[:-1]) + "\n\n"

                        buffer_text = parts[-1]

                        frozen_text += to_freeze

                display_content = frozen_text + buffer_text
                if not display_content.strip():
                    display_content = "..."

                panel = Panel(
                    Markdown(display_content),
                    title=f"{title}",
                    border_style="blue",
                    subtitle="正在思考..." if buffer_text else "生成完成",
                )
                live.update(panel)

            final_panel = Panel(
                Markdown(full_text),
                title=f"{title}",
                border_style="green",
                subtitle="✓ 生成完成",
            )
            live.update(final_panel)

        return full_text


smart_streamer = SmartMarkdownStreamer()
