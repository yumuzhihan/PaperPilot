import re
import json
from datetime import datetime
from pathlib import Path
import typst
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
        self.current_turn = 0
        self.max_turns = settings.MAX_TURNS

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
                    self.console.print(f"[red]错误: {e}[/]")
                    continue
            elif current_status == PaperStatus.RESEARCHING:
                try:
                    await self.phase_researching()
                    self.paper_context.status = PaperStatus.WRITING
                except Exception as e:
                    self.console.print(f"[red]错误: {e}[/]")
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
                raise ValueError(
                    f"LLM 未返回有效 JSON。原始输出片段: {outline_str[:50]}..."
                )

            if isinstance(data, dict):
                generated_title = data.get("title", self.paper_context.topic)
                self.paper_context.title = generated_title

                sections_data = data.get("sections", data.get("outline", []))
            elif isinstance(data, list):
                self.paper_context.title = f"Research on {self.paper_context.topic}"
                sections_data = data
            else:
                raise ValueError("JSON 结构既不是字典也不是列表")

            self.paper_context.outline = [
                SectionContext(**item) for item in sections_data
            ]

            self.console.print()
            self.console.print(
                f"[bold cyan]正式标题设定为:[/bold cyan] {self.paper_context.title}"
            )
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
                f"\n[bold magenta]正在研究章节 {index + 1} / {len(self.paper_context.outline)}: {section.section_name}[/bold magenta]"
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
            _, raw_response = await self._call_llm(
                msgs,
                tools=tool_register.get_func_call_list(
                    ["arxiv_search", "arxiv_download", "pdf_read"]
                ),
            )
            notes_match = re.search(r"<notes>(.*?)</notes>", raw_response, re.DOTALL)
            refs_match = re.search(
                r"<references>(.*?)</references>", raw_response, re.DOTALL
            )

            research_notes = (
                notes_match.group(1).strip() if notes_match else raw_response
            )
            references_text = refs_match.group(1).strip() if refs_match else ""

            note_key = f"{section.section_name}_notes"
            self.paper_context.drafts[note_key] = research_notes

            if references_text:
                pattern = r"(@[a-zA-Z]+\s*\{([^,]+),.*?\n\})"

                for match in re.finditer(pattern, references_text, re.DOTALL):
                    full_bib_block = match.group(1).strip()
                    cite_key = match.group(2).strip()

                    self.paper_context.bibliography[cite_key] = full_bib_block

            section.section_status = SectionStatus.WRITING

            self.console.print()
            self.console.print(
                f"> 章节{section.section_name} 查找完毕，当前积累了 {len(self.paper_context.bibliography)} 篇文献",
                style="dim",
            )
            self.console.print()

    async def phase_writing(self) -> None:
        self.console.print(Rule("进入论文生成阶段...", style="magenta", align="center"))

        child_dir = datetime.now().strftime(f"%YYYY-%mm-%dd_{self.paper_context.title}")

        output_dir = settings.DATA_DIR.parent / "outputs" / child_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        available_keys = (
            ", ".join(self.paper_context.bibliography.keys())
            if hasattr(self.paper_context, "bibliography")
            else "无可用文献"
        )

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
                bib_keys=available_keys,
            )

            msgs = ChatHistory(messages=[Message(role="user", content=prompt)])

            _, content = await self._call_llm(msgs, tools=[])

            clean_content = self._clean_typst_content(content)
            self.paper_context.drafts[section.section_name] = clean_content

            filename = f"{index + 1:02d}_{section.section_name.replace(' ', '_')}.typ"
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

        self.current_turn = 0

        while current_turn < max_turns:
            current_turn += 1
            self.current_turn = current_turn
            tool_called = False

            # 打印当前回合状态（只在开始时打印一次，不持续刷新）
            status_text = self._get_status_text(current_turn, max_turns)
            self.console.print(f"\n[dim]>>> {status_text} <<<[/dim]\n")

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

    def _clean_typst_content(self, text: str) -> str:
        """清洗 LLM 返回的 Typst 文本"""
        text = text.replace("```typst", "").replace("```typ", "").replace("```", "")

        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)

        text = re.sub(r"^#\s+", "= ", text, flags=re.MULTILINE)
        text = re.sub(r"^##\s+", "== ", text, flags=re.MULTILINE)
        text = re.sub(r"^###\s+", "=== ", text, flags=re.MULTILINE)
        text = re.sub(r"^####\s+", "==== ", text, flags=re.MULTILINE)

        text = re.sub(r"\\sqrt\{([^}]+)\}", r"sqrt(\1)", text)
        text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1)/(\2)", text)
        text = text.replace(r"\left", "").replace(r"\right", "")

        greek_letters = (
            r"\\(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|tau|phi|omega)"
        )
        text = re.sub(greek_letters, r"\1", text)

        text = re.sub(r"\\mathbf\{([^}]+)\}", r"bold(\1)", text)
        text = re.sub(r"\\mathcal\{([^}]+)\}", r"cal(\1)", text)

        return text.strip()

    def _generate_main_tex(self, output_dir: Path):
        """生成一个 main.tex 将所有章节串起来"""

        bib_path = output_dir / "references.bib"

        if (
            hasattr(self.paper_context, "bibliography")
            and self.paper_context.bibliography
        ):
            with open(bib_path, "w", encoding="utf-8") as f:
                for bib_text in self.paper_context.bibliography.values():
                    f.write(bib_text + "\n\n")
        else:
            bib_path.touch()

        main_content = [
            '#set document(title: "'
            + self.paper_context.topic
            + '", author: "AI PaperPilot")',
            '#set page(paper: "a4", margin: 2.5cm)',
            '#set text(font: "New Computer Modern", size: 11pt)',
            "#set par(justify: true, leading: 0.65em)",
            '#set heading(numbering: "1.1")',
            "",
            "#align(center)[",
            '  #text(17pt, weight: "bold")[' + self.paper_context.topic + "]",
            "]",
            "#v(2em)",
            '#outline(title: "目录", depth: 2)',
            "#pagebreak()",
            "",
        ]

        for index, section in enumerate(self.paper_context.outline):
            filename = f"{index + 1:02d}_{section.section_name.replace(' ', '_')}.typ"
            main_content.append(f"= {section.section_name}")
            main_content.append(f'#include "{filename}"')
            main_content.append("")

        if self.paper_context.bibliography:
            main_content.append("#pagebreak()")
            main_content.append('#bibliography("references.bib", style: "ieee")')

        main_typ_path = output_dir / "main.typ"
        with open(main_typ_path, "w", encoding="utf-8") as f:
            f.write("\n".join(main_content))

        self.console.print(
            f"\n[bold blue]主配置文件已生成: {main_typ_path}[/bold blue]"
        )

        try:
            self.console.print("正在调用 Typst 引擎编译 PDF...")
            pdf_path = output_dir / "Paper_Output.pdf"

            # 使用 Python 的 typst 库直接编译
            typst.compile(str(main_typ_path), output=str(pdf_path))

            self.console.print(
                f"🎉 [bold green]PDF 编译成功！路径: {pdf_path}[/bold green]"
            )
        except Exception as e:
            self.console.print(f"[red]PDF 编译失败，可能是语法错误: {e}[/red]")
            self.console.print("您可以手动检查 output 目录下的 .typ 文件。")

    def _get_status_text(self, current_turn: int, max_turns: int) -> str:
        """生成状态栏文本"""
        status_map = {
            PaperStatus.PLANNING: "规划中",
            PaperStatus.RESEARCHING: "研究中",
            PaperStatus.WRITING: "写作中",
            PaperStatus.FINISHED: "已完成",
        }
        current_phase = status_map.get(
            self.paper_context.status, str(self.paper_context.status)
        )

        if self.paper_context.outline:
            curr_idx = self.paper_context.current_section_index + 1
            total_sec = len(self.paper_context.outline)
            try:
                sec_name = self.paper_context.outline[
                    self.paper_context.current_section_index
                ].section_name
            except IndexError:
                sec_name = "N/A"
            section_info = f"章节 {curr_idx}/{total_sec}: {sec_name}"
        else:
            section_info = "等待大纲生成..."

        return f"[{current_phase}] {section_info} | 回合: {current_turn}/{max_turns}"
