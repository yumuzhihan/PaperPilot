import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

from src.core import AgentEngine
from src.utils import SHARED_CONSOLE

SYSTEM_PROPMT = """
你是一个严谨的学术研究助手。你的目标是基于**真实文件内容**回答问题。除非用户明确表示不需要，你需要尽可能对你的工作存档，保存为 Markdown 文件。

### 核心协议 (CRITICAL PROTOCOL)
当用户要求总结、分析或解读论文时，你必须严格遵守以下执行流程。**禁止跳过任何步骤**：

1.  **SEARCH**: 使用 `search_arxiv` 查找论文。
2.  **CHECK**: 检查搜索结果。摘要(Abstract)仅供参考，**严禁**直接用于最终总结。
3.  **DOWNLOAD**: 必须对目标论文调用 `arxiv_download`。
4.  **READ**: 必须对下载的文件调用 `pdf_read`。
5.  **SUMMARIZE**: 仅基于 `pdf_read` 返回的真实文本内容生成回答。

### 违规惩罚
如果你在没有调用 `pdf_read` 的情况下输出了论文总结，将被视为**严重错误**。
如果你发现搜索结果中的 Summary 被截断，这是明确的信号要求你下载全文。

### 思考格式
在 Thinking 过程中，你必须显式列出：
- "我是否已经下载了论文？" -> No
- "我是否读取了全文？" -> No
- "因此，我现在必须调用工具..."

### 补充
除非用户明确表示不需要，你需要尽可能对你的工作存档，保存为 Markdown 文件。
"""


async def main():
    engine = AgentEngine()

    SHARED_CONSOLE.print("[bold blue]Agent 启动完成！请输入一个主题：")
    session = PromptSession()

    while True:
        try:
            user_input = await session.prompt_async(
                HTML("<b><yellow>User ></yellow></b> ")
            )

            user_input = user_input.strip()

            await engine.run(user_input)

            SHARED_CONSOLE.print()

        except KeyboardInterrupt:
            print("\nUser interrupted.")
            break
        except EOFError:
            break
        except Exception as e:
            SHARED_CONSOLE.print_exception()


if __name__ == "__main__":
    asyncio.run(main())
