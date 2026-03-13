import json
import re
from datetime import datetime
from pathlib import Path

import typst
from rich.rule import Rule

from src.config import PromptManager, PromptTemplate, settings
from src.models import (
    ChatHistory,
    Message,
    PaperContext,
    PaperStatus,
    SectionContext,
    SectionStatus,
)
from src.llms import llm_factory
from src.tools import tool_register
from src.utils import (
    LoggerFactory,
    SHARED_CONSOLE,
    SessionSnapshot,
    SessionStore,
    ValidationResult,
    extract_json_from_text,
    validate_planning_output,
    validate_research_output,
    validate_writing_output,
)


class AgentEngine:
    MAIN_TYP_DRAFT_KEY = "__main_typ__"
    REFERENCES_BIB_DRAFT_KEY = "__references_bib__"

    def __init__(self, snapshot: SessionSnapshot | None = None) -> None:
        self.paper_context = snapshot.paper_context if snapshot else PaperContext()
        self.llm = llm_factory.get_llm()
        self.console = SHARED_CONSOLE
        self.logger = LoggerFactory.get_logger("[Agent Engine]")
        self.current_turn = snapshot.recent_success_turn if snapshot else 0
        self.max_turns = settings.MAX_TURNS
        self.max_validation_retries = settings.LLM_RETRY_MAX_ATTEMPTS
        self.chat_history = snapshot.chat_history if snapshot else ChatHistory()
        self.session_store = SessionStore()
        self.session_id = (
            snapshot.session_id if snapshot else self.session_store.create_session_id()
        )
        self.last_error = snapshot.recent_error if snapshot else None
        self.last_completed_pdf = snapshot.last_completed_pdf if snapshot else None

    @staticmethod
    def _clone_history(history: ChatHistory) -> ChatHistory:
        return ChatHistory.model_validate(history.model_dump())

    def _new_history(self, prompt: str) -> ChatHistory:
        return ChatHistory(messages=[Message(role="user", content=prompt)])

    @staticmethod
    def _history_starts_with_prompt(history: ChatHistory, prompt: str) -> bool:
        if not history.messages:
            return False
        first_message = history.messages[0]
        return first_message.role == "user" and first_message.content == prompt

    def _resolve_section_history(
        self, *, prompt: str, phase: PaperStatus, section_index: int
    ) -> ChatHistory:
        if (
            self.paper_context.status == phase
            and self.paper_context.current_section_index == section_index
            and self.chat_history.messages
            and self._history_starts_with_prompt(self.chat_history, prompt)
        ):
            return self._clone_history(self.chat_history)
        return self._new_history(prompt)

    @classmethod
    def from_session_id(cls, session_id: str) -> "AgentEngine":
        snapshot = SessionStore().load_snapshot(session_id)
        if snapshot.current_phase in PaperStatus.__members__:
            snapshot.paper_context.status = PaperStatus[snapshot.current_phase]
        snapshot.paper_context.current_section_index = snapshot.current_section_index
        return cls(snapshot=snapshot)

    async def run(self, topic: str | None = None) -> None:
        if topic:
            self.paper_context.topic = topic

        if not self.paper_context.topic:
            raise ValueError("缺少论文主题")

        while self.paper_context.status != PaperStatus.FINISHED:
            current_status = self.paper_context.status

            try:
                if current_status == PaperStatus.PLANNING:
                    await self.phase_planing()
                    self._transition_to_phase(
                        next_phase=PaperStatus.RESEARCHING,
                        label="planning_complete",
                    )
                elif current_status == PaperStatus.RESEARCHING:
                    await self.phase_researching()
                    self._transition_to_phase(
                        next_phase=PaperStatus.WRITING,
                        label="research_complete",
                    )
                elif current_status == PaperStatus.WRITING:
                    await self.phase_writing()
                    self.paper_context.status = PaperStatus.FINISHED
                    self._save_checkpoint("success", "writing_complete")
                else:
                    raise ValueError(f"未知阶段: {current_status}")
            except Exception as exc:
                self.last_error = str(exc)
                self._save_checkpoint(
                    "error", f"{self._current_phase_name().lower()}_failed"
                )
                self.console.print(f"[red]错误: {exc}[/red]")
                raise

    def _transition_to_phase(self, next_phase: PaperStatus, label: str) -> None:
        self.paper_context.status = next_phase
        self.paper_context.current_section_index = 0
        self.current_turn = 0
        self.chat_history = ChatHistory()
        self.last_error = None
        self._save_checkpoint("success", label)

    def _enter_section(self, phase: PaperStatus, section_index: int) -> None:
        is_new_section = self.paper_context.current_section_index != section_index
        self.paper_context.current_section_index = section_index
        self.paper_context.status = phase
        if is_new_section:
            self.current_turn = 0
            self.chat_history = ChatHistory()
            self.last_error = None

    async def phase_planing(self) -> None:
        prompt = PromptManager.get_prompt(
            PromptTemplate.PLANNING, topic=self.paper_context.topic
        )
        planning_tools = tool_register.get_func_call_list(
            ["arxiv_search", "time_sleep"]
        )

        self.console.print(Rule("生成论文框架中...", style="magenta", align="center"))

        planning_history = self._new_history(prompt)

        result = await self._run_llm_with_validation(
            base_history=planning_history,
            tools=planning_tools,
            validator=validate_planning_output,
            label="planning",
        )
        data = result.data
        self.paper_context.title = data["title"].strip()
        self.paper_context.outline = data["sections"]

        self.console.print()
        self.console.print(
            f"[bold cyan]正式标题设定为:[/bold cyan] {self.paper_context.title}"
        )
        self.console.print(
            f"解析框架成功大纲生成完毕，包含 {len(self.paper_context.outline)} 个主章节。"
        )
        self.console.print()

    async def phase_researching(self) -> None:
        self.console.print(Rule("进入研究阶段...", style="magenta", align="center"))

        for index, section in enumerate(self.paper_context.outline):
            if section.section_status in {
                SectionStatus.WRITING,
                SectionStatus.FINISHED,
            }:
                continue
            self._enter_section(PaperStatus.RESEARCHING, index)
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
            section_history = self._resolve_section_history(
                prompt=prompt,
                phase=PaperStatus.RESEARCHING,
                section_index=index,
            )

            result = await self._run_llm_with_validation(
                base_history=section_history,
                tools=tool_register.get_func_call_list(
                    ["arxiv_search", "arxiv_download", "pdf_read"]
                ),
                validator=validate_research_output,
                label=f"research_{index + 1:02d}",
            )

            note_key = f"{section.section_name}_notes"
            self.paper_context.drafts[note_key] = result.data["notes"]

            for bib_block in result.data["bib_entries"]:
                match = re.search(r"@[a-zA-Z]+\s*\{\s*([^,\s]+)", bib_block)
                if match:
                    self.paper_context.bibliography[match.group(1).strip()] = bib_block

            section.section_status = SectionStatus.WRITING
            self._save_checkpoint(
                "success", f"research_section_{index + 1:02d}", result.content
            )

            self.console.print()
            self.console.print(
                f"> 章节{section.section_name} 查找完毕，当前积累了 {len(self.paper_context.bibliography)} 篇文献",
                style="dim",
            )
            self.console.print()

    async def phase_writing(self) -> None:
        self.console.print(Rule("进入论文生成阶段...", style="magenta", align="center"))

        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._restore_generated_files(output_dir)

        available_keys = (
            ", ".join(self.paper_context.bibliography.keys()) or "无可用文献"
        )

        for index, section in enumerate(self.paper_context.outline):
            if section.section_status == SectionStatus.FINISHED:
                continue
            self._enter_section(PaperStatus.WRITING, index)
            section.section_status = SectionStatus.WRITING

            self.console.print(
                f"\n[bold green]正在撰写章节: {section.section_name}[/bold green]"
            )

            note_key = f"{section.section_name}_notes"
            notes = self.paper_context.drafts.get(note_key, "")
            if len(notes.strip()) < 10:
                raise ValueError(
                    f"章节 {section.section_name} 缺少足够研究笔记，无法写作"
                )

            prompt = PromptManager.get_prompt(
                PromptTemplate.WRITING,
                topic=self.paper_context.topic,
                section_name=section.section_name,
                notes=notes,
                bib_keys=available_keys,
            )
            section_history = self._resolve_section_history(
                prompt=prompt,
                phase=PaperStatus.WRITING,
                section_index=index,
            )

            result = await self._run_llm_with_validation(
                base_history=section_history,
                tools=[],
                validator=validate_writing_output,
                label=f"writing_{index + 1:02d}",
            )

            clean_content = self._clean_typst_content(result.content)
            self.paper_context.drafts[section.section_name] = clean_content

            filename = f"{index + 1:02d}_{section.section_name.replace(' ', '_')}.typ"
            filepath = output_dir / filename
            filepath.write_text(clean_content, encoding="utf-8")

            self.console.print(f"[dim]已保存草稿: {filename}[/dim]")
            section.section_status = SectionStatus.FINISHED
            self._save_checkpoint(
                "success", f"writing_section_{index + 1:02d}", clean_content
            )

        main_typ_path = self._restore_generated_files(output_dir)
        pdf_path = await self._compile_pdf(main_typ_path)
        self.last_completed_pdf = str(pdf_path)
        self._save_checkpoint("success", "pdf_compiled")
        self.console.print(Rule("论文撰写完成！", style="green"))

    async def _run_llm_with_validation(
        self,
        *,
        base_history: ChatHistory,
        tools: list[dict] | None,
        validator,
        label: str,
    ):
        last_error = "LLM 未返回有效结果"
        stable_history = self._clone_history(base_history)

        for attempt in range(1, self.max_validation_retries + 1):
            messages = self._clone_history(stable_history)
            if attempt > 1:
                messages.messages.append(
                    Message(
                        role="user",
                        content=f"你上一轮输出不符合要求：{last_error}。请严格修正后重新完整输出。",
                    )
                )

            _, raw_content, turns_used = await self._call_llm(messages, tools)
            result = validator(raw_content)
            if result.ok:
                stable_history = self._clone_history(messages)
                self.chat_history = self._clone_history(stable_history)
                self.current_turn += turns_used
                self.last_error = None
                self._save_checkpoint("success", label, result.content)
                return result

            last_error = result.error or last_error
            self.last_error = last_error
            self._save_checkpoint("error", f"{label}_attempt_{attempt}", raw_content)
            self.console.print(
                f"[yellow]输出校验失败，第 {attempt}/{self.max_validation_retries} 次重试: {last_error}[/yellow]"
            )

        raise ValueError(f"{label} 阶段超过重试上限: {last_error}")

    async def _call_llm(
        self, messages: ChatHistory, tools: list[dict] | None = None
    ) -> tuple[str, str, int]:
        is_thinking = False
        full_content = ""
        full_thinking = ""
        current_turn = self.current_turn
        turns_used = 0

        while turns_used < self.max_turns:
            current_turn += 1
            turns_used += 1
            tool_called = False

            status_text = self._get_status_text(current_turn, self.max_turns)
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
                    continue

                if not isinstance(chunk, dict):
                    continue

                if chunk.get("type") != "tool_call_request":
                    continue

                tool_calls = chunk.get("tool_calls") or []
                tool_called = True

                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    call_id = tool_call.get("id")
                    try:
                        args_dict = self.llm.parse_tool_arguments(
                            function.get("arguments", "")
                        )
                    except ValueError as exc:
                        tool_result = f"工具参数错误: {exc}"
                    else:
                        self.console.print()
                        self.console.print(f"> 调用工具 {tool_name}", style="italic")
                        self.console.print()
                        tool_result = await tool_register.dispatch(tool_name, args_dict)
                        self.console.print(tool_result)

                    messages.messages.append(
                        Message(
                            role="tool",
                            content=str(tool_result),
                            tool_name=tool_name,
                            tool_call_id=call_id,
                        )
                    )

            if not tool_called:
                break

            full_content = ""
            self.console.print("\n[bold green]工具执行完毕，继续思考...[/bold green]\n")

        if turns_used == self.max_turns:
            raise RuntimeError("达到单步骤轮次上限，已中止当前阶段")

        return full_thinking, full_content, turns_used

    def _clean_typst_content(self, text: str) -> str:
        text = text.replace("```typst", "").replace("```typ", "").replace("```", "")
        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
        text = re.sub(r"^#\s+", "= ", text, flags=re.MULTILINE)
        text = re.sub(r"^##\s+", "== ", text, flags=re.MULTILINE)
        text = re.sub(r"^###\s+", "=== ", text, flags=re.MULTILINE)
        text = re.sub(r"^####\s+", "==== ", text, flags=re.MULTILINE)
        text = re.sub(r"\\sqrt\{([^}]+)\}", r"sqrt(\1)", text)
        text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1)/(\2)", text)
        text = text.replace(r"\left", "").replace(r"\right", "")
        text = re.sub(
            r"\\(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|tau|phi|omega)",
            r"\1",
            text,
        )
        text = re.sub(r"\\mathbf\{([^}]+)\}", r"bold(\1)", text)
        text = re.sub(r"\\mathcal\{([^}]+)\}", r"cal(\1)", text)
        return text.strip()

    @staticmethod
    def _get_section_filename(index: int, section_name: str) -> str:
        return f"{index + 1:02d}_{section_name.replace(' ', '_')}.typ"

    def _build_references_content(self) -> str:
        if not self.paper_context.bibliography:
            return ""
        return "\n\n".join(self.paper_context.bibliography.values()) + "\n"

    def _build_main_content(self) -> str:
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
            filename = self._get_section_filename(index, section.section_name)
            main_content.append(f"= {section.section_name}")
            main_content.append(f'#include "{filename}"')
            main_content.append("")

        if self.paper_context.bibliography:
            main_content.append("#pagebreak()")
            main_content.append('#bibliography("references.bib", style: "ieee")')

        return "\n".join(main_content)

    def _restore_generated_files(self, output_dir: Path) -> Path:
        for index, section in enumerate(self.paper_context.outline):
            content = self.paper_context.drafts.get(section.section_name, "").strip()
            if not content:
                continue
            filename = self._get_section_filename(index, section.section_name)
            (output_dir / filename).write_text(content + "\n", encoding="utf-8")

        references_content = self.paper_context.drafts.get(
            self.REFERENCES_BIB_DRAFT_KEY
        )
        if references_content is None:
            references_content = self._build_references_content()
        (output_dir / "references.bib").write_text(references_content, encoding="utf-8")
        self.paper_context.drafts[self.REFERENCES_BIB_DRAFT_KEY] = references_content

        main_content = self.paper_context.drafts.get(self.MAIN_TYP_DRAFT_KEY)
        if not main_content:
            main_content = self._build_main_content()
        main_typ_path = output_dir / "main.typ"
        main_typ_path.write_text(main_content, encoding="utf-8")
        self.paper_context.drafts[self.MAIN_TYP_DRAFT_KEY] = main_content
        self.console.print(
            f"\n[bold blue]主配置文件已生成: {main_typ_path}[/bold blue]"
        )
        return main_typ_path

    def _generate_main_typ(self, output_dir: Path) -> Path:
        return self._restore_generated_files(output_dir)

    def _collect_generated_file_contents(self, output_dir: Path) -> dict[str, str]:
        generated_files: dict[str, str] = {
            "main.typ": (output_dir / "main.typ").read_text(encoding="utf-8"),
            "references.bib": (output_dir / "references.bib").read_text(
                encoding="utf-8"
            ),
        }
        for index, section in enumerate(self.paper_context.outline):
            filename = self._get_section_filename(index, section.section_name)
            filepath = output_dir / filename
            if filepath.exists():
                generated_files[filename] = filepath.read_text(encoding="utf-8")
        return generated_files

    def _validate_typst_repair_output(
        self, text: str, allowed_paths: set[str]
    ) -> ValidationResult:
        stripped = text.strip()
        data = extract_json_from_text(stripped)
        if not isinstance(data, dict):
            return ValidationResult(False, stripped, "修复结果不是合法 JSON object")

        files = data.get("files")
        if not isinstance(files, list) or not files:
            return ValidationResult(False, stripped, "修复结果缺少非空 files 列表")

        normalized_files: dict[str, str] = {}
        for item in files:
            if not isinstance(item, dict):
                return ValidationResult(False, stripped, "files 列表元素必须是 object")
            path = item.get("path")
            content = item.get("content")
            if not isinstance(path, str) or path not in allowed_paths:
                return ValidationResult(
                    False, stripped, f"存在非法修复文件路径: {path}"
                )
            if not isinstance(content, str) or not content.strip():
                return ValidationResult(False, stripped, f"修复文件 {path} 内容为空")
            normalized_files[path] = (
                self._clean_typst_content(content)
                if path.endswith(".typ")
                else content.strip() + "\n"
            )

        return ValidationResult(True, stripped, data=normalized_files)

    async def _repair_typst_files(
        self, output_dir: Path, compile_error: str
    ) -> dict[str, str]:
        generated_files = self._collect_generated_file_contents(output_dir)
        allowed_paths = set(generated_files.keys())
        file_blocks = []
        for path, content in generated_files.items():
            file_blocks.append(f"--- FILE: {path} ---\n{content}\n")

        prompt = "\n".join(
            [
                "你是一名 Typst 编译修复专家。下面给你一个编译失败的 Typst 工程。",
                "请在尽量少改动原文语义、结构、引用键和参考文献内容的前提下，修复会导致编译失败的问题。",
                "你只能修改我提供的这些文件，不能新增文件。",
                "请严格只返回 JSON object，不要输出 Markdown 代码块、解释或额外文字。",
                "JSON 格式如下：",
                '{"files": [{"path": "main.typ", "content": "修复后的完整文件内容"}]}',
                "只返回你实际修改过的文件；path 必须来自以下集合：",
                json.dumps(sorted(allowed_paths), ensure_ascii=False),
                "编译错误信息：",
                compile_error,
                "当前文件内容：",
                "\n".join(file_blocks),
            ]
        )

        result = await self._run_llm_with_validation(
            base_history=self._new_history(prompt),
            tools=[],
            validator=lambda text: self._validate_typst_repair_output(
                text, allowed_paths
            ),
            label="typst_repair",
        )
        return result.data

    def _apply_repaired_files(
        self, output_dir: Path, repaired_files: dict[str, str]
    ) -> None:
        section_path_map = {
            self._get_section_filename(
                index, section.section_name
            ): section.section_name
            for index, section in enumerate(self.paper_context.outline)
        }
        for path, content in repaired_files.items():
            normalized_content = content if content.endswith("\n") else content + "\n"
            (output_dir / path).write_text(normalized_content, encoding="utf-8")
            if path == "main.typ":
                self.paper_context.drafts[self.MAIN_TYP_DRAFT_KEY] = normalized_content
            elif path == "references.bib":
                self.paper_context.drafts[self.REFERENCES_BIB_DRAFT_KEY] = (
                    normalized_content
                )
            elif path in section_path_map:
                self.paper_context.drafts[section_path_map[path]] = (
                    normalized_content.strip()
                )

    async def _compile_pdf(self, main_typ_path: Path) -> Path:
        self.console.print("正在调用 Typst 引擎编译 PDF...")
        pdf_path = main_typ_path.parent / "Paper_Output.pdf"
        temp_pdf_path = main_typ_path.parent / "Paper_Output.tmp.pdf"

        last_error = ""
        for attempt in range(1, self.max_validation_retries + 1):
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()

            try:
                typst.compile(str(main_typ_path), output=str(temp_pdf_path))
            except Exception as exc:
                last_error = str(exc)
                self.last_error = last_error
                self._save_checkpoint(
                    "error",
                    f"typst_compile_attempt_{attempt}",
                    last_error,
                )
                if attempt >= self.max_validation_retries:
                    break

                self.console.print(
                    f"[yellow]Typst 编译失败，第 {attempt}/{self.max_validation_retries} 次修复: {last_error}[/yellow]"
                )
                repaired_files = await self._repair_typst_files(
                    main_typ_path.parent, last_error
                )
                self._apply_repaired_files(main_typ_path.parent, repaired_files)
                self._save_checkpoint(
                    "success",
                    f"typst_repair_attempt_{attempt}",
                    json.dumps(sorted(repaired_files.keys()), ensure_ascii=False),
                )
                continue

            if not temp_pdf_path.exists() or temp_pdf_path.stat().st_size <= 0:
                last_error = "PDF 编译失败：输出文件不存在或为空"
                self.last_error = last_error
                if attempt >= self.max_validation_retries:
                    break
                continue

            temp_pdf_path.replace(pdf_path)
            self.last_error = None
            self.console.print(
                f"[bold green]PDF 编译成功！路径: {pdf_path}[/bold green]"
            )
            return pdf_path

        raise RuntimeError(f"PDF 编译失败，可能是 Typst 语法错误: {last_error}")

    def _save_checkpoint(
        self, checkpoint_type: str, label: str, output_preview: str | None = None
    ) -> None:
        self.session_store.save_snapshot(
            session_id=self.session_id,
            topic=self.paper_context.topic,
            current_phase=self._current_phase_name(),
            current_section_index=self.paper_context.current_section_index,
            paper_context=self.paper_context,
            chat_history=self.chat_history,
            recent_success_turn=self.current_turn,
            recent_error=self.last_error,
            checkpoint_type=checkpoint_type,
            label=label,
            last_completed_pdf=self.last_completed_pdf,
            output_preview=output_preview,
        )

    def _current_phase_name(self) -> str:
        return self.paper_context.status.name

    def _get_output_dir(self) -> Path:
        safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", self.paper_context.title).strip(
            "_"
        )
        if not safe_title:
            safe_title = datetime.now().strftime("paper_%Y%m%d_%H%M%S")
        return settings.DATA_DIR.parent / "outputs" / f"{self.session_id}_{safe_title}"

    def _get_status_text(self, current_turn: int, max_turns: int) -> str:
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
