from enum import Enum
from typing import Any
import json


class PromptTemplate(Enum):
    """提示词模板"""

    PLANNING = "planning"  # 生成大纲
    RESEARCHING = "researching"  # 进行文献检索
    WRITING = "writing"  # 章节撰写
    REVIEW = "review"  # 内容审查
    MERGE = "merge"  # 合并润色


class PromptManager:
    @staticmethod
    def get_prompt(template: PromptTemplate, **kwargs: Any) -> str:
        """
        根据模板类型和上下文参数生成最终 Prompt
        :param template: PromptTemplate 枚举
        :param kwargs: 动态参数，如 topic, section_name, context_data 等
        :return: 格式化后的 Prompt 字符串
        """

        # ------------------------------------------------------------------
        # 1. 规划阶段 (PLANNING) - 目标：生成 JSON 大纲
        # ------------------------------------------------------------------
        if template == PromptTemplate.PLANNING:
            topic = kwargs.get("topic", "未指定主题")

            example_structure = [
                {
                    "section_name": "Introduction",
                    "subsections": [
                        {"section_name": "Background"},
                        {"section_name": "Motivation"},
                    ],
                },
                {"section_name": "Methodology", "subsections": []},
            ]

            return f"""
你是一名资深的学术论文架构师。我们需要通过以下主题撰写一篇专业的学术论文。
论文主题: "{topic}"

请你规划一份详细的论文大纲。
【严格约束】
1. 你的回答必须只包含合法的 JSON 列表，不要包含 Markdown 代码块标记（如 ```json）。
2. JSON 结构必须符合以下 Schema，以便我可以自动解析。
3. 如果对于主题包含任何不确定的内容，请你考虑调用工具：
{json.dumps(example_structure, indent=4, ensure_ascii=False)}

请开始生成大纲：
"""

        # ------------------------------------------------------------------
        # 2. 研究阶段 (RESEARCHING) - 目标：把章节名转化为 arXiv 搜索词
        # ------------------------------------------------------------------
        elif template == PromptTemplate.RESEARCHING:
            section_name = kwargs.get("section_name", "")
            subsection_names = kwargs.get("subsection_names", "")
            topic = kwargs.get("topic", "")

            return f"""
我们正在研究论文主题 "{topic}"。
目前的任务是为章节 "{section_name}" 总结相关文献。根据提前生成的大纲，这一章节包含的子章节为：{subsection_names}

步骤：
1. 使用 arxiv_search 工具搜索相关论文。
2. 阅读摘要或下载论文(如果需要)。
3. 最终，请根据搜索到的信息，输出一段详细的中文【研究笔记】，包含关键技术点、引用来源。
"""

        # ------------------------------------------------------------------
        # 3. 写作阶段 (WRITING) - 目标：生成 LaTeX 内容
        # ------------------------------------------------------------------
        elif template == PromptTemplate.WRITING:
            section_name = kwargs.get("section_name", "")
            notes = kwargs.get("notes", "无")
            topic = kwargs.get("topic", "")

            return f"""
你是一个专业的学术论文写作者。
论文主题: "{topic}"
当前正在撰写的章节: "{section_name}"

你的任务是根据以下【研究笔记】，扩写并润色出该章节的完整学术正文。

【研究笔记内容】
---
{notes}
---

【写作要求】
1. **格式**: 必须使用 LaTeX 格式。
2. **结构**: 只输出该章节的正文内容。**不要**包含 `\\documentclass`, `\\begin{{document}}`, `\\maketitle` 等导言区代码，因为这只是论文的一部分。
3. **层级**: 如果笔记中有子观点，可以使用 `\\subsection{{...}}` 或 `\\paragraph{{...}}`。
4. **引用**: 如果笔记中包含引用信息（如 [Author, Year]），请将其转换为 LaTeX 的 `\\cite{{...}}` 格式（你可以自定义引用key，例如 `\\cite{{author2023}}`）。
5. **风格**: 保持客观、严谨的学术语调。避免使用“我”、“我们认为”等主观词汇，除非是描述方法论。
6. **长度**: 内容要充实，逻辑要连贯，不要只是简单罗列笔记。

请直接开始输出 LaTeX 代码，不要包含任何开场白或结束语（如“好的，这是正文...”）。
"""

        else:
            raise ValueError(f"未实现的 Prompt 模板: {template}")
