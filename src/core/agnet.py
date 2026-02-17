import json
from pathlib import Path
from rich.rule import Rule

from src.config import PromptManager, PromptTemplate, settings
from src.models import (
    PaperContext,
    PaperStatus,
    ChatHistory,
    Message,
    SectionContext,
    SectionStatus,
)
from src.llms import llm_factory
from src.tools import tool_register
from src.utils import LoggerFactory, SHARED_CONSOLE, extract_json_from_text


class AgentEngine:
    def __init__(self) -> None:
        self.paper_context = PaperContext()
        self.llm = llm_factory.get_llm()
        self.console = SHARED_CONSOLE
        self.logger = LoggerFactory.get_logger("[Agent Engine]")

    async def run(self, topic: str) -> None:
        """运行 agent

        Args:
            topic (str): 论文主题
        """
        self.paper_context.topic = topic

        while not self.paper_context.status == PaperStatus.FINISHED:
            current_status = self.paper_context.status

            if current_status == PaperStatus.PLANNING:
                try:
                    await self.phase_planing()
                    self.paper_context.status = PaperStatus.RESEARCHING
                except Exception as e:
                    self.console.print(e)
                    continue
            elif current_status == PaperStatus.RESEARCHING:
                try:
                    await self.phase_researching()
                    self.paper_context.status = PaperStatus.WRITING
                except Exception as e:
                    self.console.print(e)
            elif current_status == PaperStatus.WRITING:
                try:
                    await self.phase_writing()
                    self.paper_context.status = PaperStatus.FINISHED
                except Exception as e:
                    self.console.print_exception()

    async def phase_planing(self) -> None:
        prompt = PromptManager.get_prompt(
            PromptTemplate.PLANNING, topic=self.paper_context.topic
        )
        prompt_message = ChatHistory(messages=[Message(role="user", content=prompt)])
        planing_tools = tool_register.get_func_call_list(["arxiv_search", "time_sleep"])
        outline_str = ""

        self.console.print(
            Rule(
                f"生成论文框架中...",
                style="magenta",
                align="center",
            )
        )

        _, outline_str = await self._call_llm(prompt_message, planing_tools)
        outline_str = outline_str.replace("```json", "").replace("```", "").strip()

        try:
            data = extract_json_from_text(outline_str)
            if not data:
                return
            self.paper_context.outline = [SectionContext(**item) for item in data]
            self.console.print()
            self.console.print(
                f"解析框架成功大纲生成完毕，包含 {len(self.paper_context.outline)} 个主章节。"
            )
            self.console.print()
        except Exception as e:
            self.console.print_exception()

    async def phase_researching(self) -> None:
        self.console.print(Rule("进入研究阶段...", style="magenta", align="center"))

        for index, section in enumerate(self.paper_context.outline):
            self.paper_context.current_section_index = index
            section.section_status = SectionStatus.RESEARCHING

            self.console.print(
                f"\n[bold magenta]正在研究章节 {index+1} / {len(self.paper_context.outline)}: {section.section_name}[/bold magenta]"
            )

            prompt = PromptManager.get_prompt(
                PromptTemplate.RESEARCHING,
                topic=self.paper_context.topic,
                section_name=section.section_name,
                subsection_names=(
                    [subsection.section_name for subsection in section.subsections]
                    if section.subsections
                    else None
                ),
            )
            msgs = ChatHistory(messages=[Message(role="user", content=prompt)])
            _, research_notes = await self._call_llm(msgs)
            note_key = f"{section.section_name}_notes"
            self.paper_context.drafts[note_key] = research_notes
            section.section_status = SectionStatus.WRITING

            self.console.print()
            self.console.print(f"> 章节{section.section_name} 查找完毕", style="dim")
            self.console.print()

    async def phase_writing(self) -> None:
        self.console.print(Rule("进入论文生成阶段...", style="magenta", align="center"))

        output_dir = settings.DATA_DIR / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        for index, section in enumerate(self.paper_context.outline):
            self.paper_context.current_section_index = index
            section.section_status = SectionStatus.WRITING

            self.console.print(
                f"\n[bold green]正在撰写章节: {section.section_name}[/bold green]"
            )

            note_key = f"{section.section_name}_notes"
            notes = self.paper_context.drafts.get(note_key, "无可用笔记")

            if notes == "无可用笔记" or len(notes) < 10:
                self.console.print(
                    f"[yellow]跳过章节 {section.section_name}: 笔记内容过少[/yellow]"
                )
                continue
            prompt = PromptManager.get_prompt(
                PromptTemplate.WRITING,
                topic=self.paper_context.topic,
                section_name=section.section_name,
                notes=notes,
            )

            msgs = ChatHistory(messages=[Message(role="user", content=prompt)])

            _, content = await self._call_llm(msgs, tools=None)

            clean_content = self._clean_latex_content(content)
            self.paper_context.drafts[section.section_name] = clean_content

            filename = f"{index+1:02d}_{section.section_name.replace(' ', '_')}.tex"
            filepath = output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(clean_content)

            self.console.print(f"[dim]已保存草稿: {filename}[/dim]")
            section.section_status = SectionStatus.FINISHED

        self._generate_main_tex(output_dir)
        self.paper_context.status = PaperStatus.FINISHED
        self.console.print(Rule("论文撰写完成！", style="green"))

    async def _call_llm(
        self, messages: ChatHistory, tools: list[dict] | None = None
    ) -> tuple[str, str]:
        is_thinking = False
        full_content = ""
        full_thinking = ""

        max_turns = settings.MAX_TURNS
        current_turn = 0

        while current_turn < max_turns:
            current_turn += 1
            tool_called = False

            async for chunk in self.llm.response_stream(messages, tools):
                if isinstance(chunk, str):
                    if "> **Thinking Process:**" in chunk:
                        self.console.print()
                        is_thinking = True
                        chunk = chunk.replace(
                            "> **Thinking Process:**\n\n", ""
                        ).replace("> **Thinking Process:**", "")
                        self.console.print("> 思考中：", style="dim")

                    elif "\n\n---\n\n" in chunk:
                        self.console.print()

                        is_thinking = False
                        chunk = chunk.replace("\n\n---\n\n", "")
                        self.console.print("\n")

                    if chunk:
                        if is_thinking:
                            full_thinking += chunk
                            self.console.print(chunk, style="dim", end="")
                        else:
                            full_content += chunk
                            self.console.print(chunk, end="")

                elif isinstance(chunk, dict):
                    if chunk.get("type") == "tool_call_request":
                        tool_calls = chunk.get("tool_calls")
                        if tool_calls is None:
                            continue

                        tool_called = True

                        for tool_call in tool_calls:
                            tool_name = tool_call.get("function").get("name")
                            arguments = tool_call.get("function").get("arguments")
                            args_dict = {}
                            if isinstance(arguments, dict):
                                args_dict = arguments
                            elif isinstance(arguments, str):
                                args_dict = json.loads(arguments)
                            call_id = tool_call.get("id", None)

                            self.console.print()
                            self.console.print(
                                f"> 调用工具 {tool_name}", style="italic "
                            )
                            self.console.print()

                            tool_call_result = await tool_register.dispatch(
                                tool_name, args_dict
                            )
                            self.console.print(tool_call_result)

                            messages.messages.append(
                                Message(
                                    role="tool",
                                    content=str(tool_call_result),
                                    tool_name=tool_name,
                                    tool_call_id=call_id,
                                )
                            )

            if not tool_called:
                break
            else:
                full_content = ""
            self.console.print(
                f"\n[bold green]工具执行完毕，继续思考...[/bold green]\n"
            )

        if current_turn == max_turns:
            self.console.print("达到单步骤轮次上限，强行截断")
        return full_thinking, full_content

    def _clean_latex_content(self, text: str) -> str:
        """清洗 LLM 返回的 LaTeX 文本"""
        text = text.replace("```latex", "").replace("```tex", "").replace("```", "")
        lines = text.split("\n")
        return text.strip()

    def _generate_main_tex(self, output_dir: Path):
        """生成一个 main.tex 将所有章节串起来"""
        main_content = [
            "\\documentclass{article}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage{geometry}",
            "\\title{" + self.paper_context.topic + "}",
            "\\author{AI Researcher}",
            "\\date{\\today}",
            "\\begin{document}",
            "\\maketitle",
            "\\tableofcontents",
            "\\newpage",
            "",
        ]

        for index, section in enumerate(self.paper_context.outline):
            filename = f"{index+1:02d}_{section.section_name.replace(' ', '_')}"
            main_content.append(f"\\section{{{section.section_name}}}")
            main_content.append(f"\\input{{{filename}}}")
            main_content.append("\\newpage")

        main_content.append("\\end{document}")

        with open(f"{output_dir}/main.tex", "w", encoding="utf-8") as f:
            f.write("\n".join(main_content))

        self.console.print(
            f"\n[bold blue]主文件已生成: {output_dir}/main.tex[/bold blue]"
        )
        self.console.print("你可以使用 LaTeX 编译器 (如 pdflatex) 编译此文件。")
