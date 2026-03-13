from enum import Enum
from typing import Any
import json

from src.config import settings


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

            example_structure = {
                "title": "A Comprehensive Review of [Topic]: Challenges and Opportunities",
                "sections": [
                    {
                        "section_name": "Introduction",
                        "subsections": [
                            {"section_name": "Background"},
                            {"section_name": "Motivation"},
                        ],
                    },
                    {"section_name": "Methodology", "subsections": []},
                ],
            }

            return f"""
你是一名资深的学术论文架构师。我们需要通过以下主题撰写一篇专业的学术论文。
论文主题: "{topic}"

请你规划一份详细的论文大纲。
【严格约束】
1. 你的回答必须只包含合法的 JSON object，不要包含 Markdown 代码块标记（如 ```json）。
2. JSON 结构必须符合以下 Schema，以便我可以自动解析。
3. 如果对于主题包含任何不确定的内容，请你考虑调用工具。
4. 你最终输出的结果应该使用 {settings.OUTPUT_LANGUAGE}
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
1. 使用 arxiv_search 搜索相关论文。
2. 提取有价值的信息，并记录真实的论文来源。
3. 最终输出必须严格包含两部分：【研究笔记】和【参考文献】。

【严格输出格式要求】
请你在最终回答时，使用以下 XML 标签包裹你的输出：

<notes>
在这里写详细的中文研究笔记。提到某项研究时，必须提供引用的键值标记（例如：根据Smith等人的研究 [smith2023]...）。
</notes>

<references>
在这里列出你在笔记中引用的真实文献，**必须使用标准的 BibTeX 格式**！必须是你搜索到的真实论文！
例如：
@article{{smith2023,
  title={{A survey on federated learning}},
  author={{Smith, John and Doe, Jane}},
  journal={{arXiv preprint}},
  year={{2023}}
}}
</references>
"""

        # ------------------------------------------------------------------
        # 3. 写作阶段 (WRITING) - 目标：生成 LaTeX 内容
        # ------------------------------------------------------------------
        elif template == PromptTemplate.WRITING:
            section_name = kwargs.get("section_name", "")
            notes = kwargs.get("notes", "无")
            topic = kwargs.get("topic", "")
            bib_keys = kwargs.get("bib_keys", "")

            return f"""
你是一个专业的学术论文写作者。
论文主题: "{topic}"
当前正在撰写的章节: "{section_name}"

你的任务是根据以下【研究笔记】，扩写并润色出该章节的完整学术正文。

【研究笔记内容】
---
{notes}
---

【全局可用文献的 Cite Keys】
你可以且只能使用以下 Cite Keys 进行学术引用：
{bib_keys}

【Typst 写作语法严格要求(极其重要)】
1. **绝对禁止使用 LaTeX 语法**（如 `\\section`, `\\textbf`, `\\cite` 等）！
2. **章节标题**: 不要输出当前大章节的标题。如果笔记中有子章节，使用 `== 子章节名` (相当于 subsection)，`=== 小节名` (相当于 subsubsection)。
3. **加粗与斜体**: 加粗使用 `*文字*`，斜体使用 `_文字_`。
4. **引用**: 使用 Typst 的引用语法：`@citekey`。例如：“正如之前的研究 @smith2023 所指出的...”。如果引用多个：`@smith2023 @jones2024`。
5. **数学公式**: 行内公式使用 `$x + y$`; 独立成行的公式前后加空格：`$ x + y = z $`。
6. **纯净输出**: 直接输出该章节的正文内容，不要有任何 Markdown 代码块包裹，也不要开场白。
7. **输出语言**: 请你直接以 {settings.OUTPUT_LANGUAGE} 进行输出。
8. **标题**: 严禁使用 `#` 或 `##` 作为标题！必须使用 `=` 表示一级标题，`==` 表示二级子章节，`===` 表示三级子章节。
   - 错误示范：`## 应用场景`
   - 正确示范：`== 应用场景`
9. **加粗**: 严禁使用 `**`！请使用单星号 `*文字*` 进行加粗。
10. **引用**: 必须使用 Typst 语法 `@citekey`（例如 `@smith2023`）。
11. **禁止结构化残留**: 严禁输出 `<notes>`、`<references>`、JSON、tool call 痕迹、provider 报错文本。

【Typst 数学公式严格规范 (极其重要)】
如果你需要在文章中输出数学公式，你必须彻底放弃 LaTeX 的数学语法，改用以下 Typst 原生语法：
1. **分数**: 绝对禁止使用 `\\frac{{A}}{{B}}`！必须使用斜杠：`A / B` 或 `(A) / (B)`。
2. **根号**: 绝对禁止使用 `\\sqrt{{x}}`！必须使用函数写法：`sqrt(x)`。
3. **括号**: 绝对禁止使用 `\\left(` 和 `\\right)`！直接使用普通括号 `()` 即可，Typst 会自动调整大小。
4. **公式中的文字**: 如果在公式中出现由多个字母组成的单词（如 Attention, softmax, ReLU），必须用双引号包裹，否则会报错！
   - 错误写法：`$ Attention(Q) = softmax(...) $`
   - 正确写法：`$ "Attention"(Q) = "softmax"(...) $`
5. **上下标**: 下标使用 `_`，上标使用 `^`。例如：`Q K^T / sqrt(d_k)`。

请牢记你是一个 Typst 专家，开始你的正文输出：
"""

        else:
            raise ValueError(f"未实现的 Prompt 模板: {template}")
