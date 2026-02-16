from .tool_base import BaseTool
from .arxiv_search_tool import ArxivSearchTool
from .file_write_tool import FileWriteTool
from .file_read_tool import FileReadTool
from .arxiv_download_tool import ArxivDownloadTool
from .pdf_read_tool import PDFReadTool

all_tools: list[type[BaseTool]] = [
    ArxivSearchTool,
    FileWriteTool,
    FileReadTool,
    ArxivDownloadTool,
    PDFReadTool,
]


class ToolRegister:
    """工具管理类"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """注册所有内置工具"""
        for tool in all_tools:
            self._tools[tool.name] = tool()

    def register_tool(self, tool: type[BaseTool]):
        """注册新工具

        Args:
            tool (type[BaseTool]): 新的工具，需要从 BaseTool 继承
        """
        self._tools[tool.name] = tool()

    def get_tool(self, name: str) -> BaseTool:
        """根据名字获取工具

        Args:
            name (str): 工具名

        Raises:
            ValueError: 如果没有找到对应工具

        Returns:
            BaseTool: 对应工具
        """
        if not name in self._tools:
            raise ValueError(f"未知工具:{name}")

        return self._tools[name]

    def get_prompt_desc(self) -> str:
        """获取文本形式的工具描述

        Returns:
            str: 文本形式的工具描述
        """
        descriptions = [tool.to_prompt() for tool in self._tools.values()]

        return "\n".join(descriptions)

    def get_func_call_list(self) -> list[dict]:
        """获取 function calling 形式的工具描述，单个工具可能形式为:

        ```json
        {
            "type": "function",
            "function": {
                "name": "arxiv_search",
                "description": "在 ArXiv 上搜索学术论文。如果结果不足，请使用 offset 参数翻页。",
                "parameters": {
                    "properties": {
                        "query": {"description": "搜索关键词", "title": "Query", "type": "string"},
                        "max_results": {
                            "default": 5,
                            "description": "返回的最大结果数量",
                            "title": "Max Results",
                            "type": "integer",
                        },
                        "offset": {
                            "default": 0,
                            "description": "分页偏移量，用于翻页",
                            "title": "Offset",
                            "type": "integer",
                        },
                    },
                    "required": ["query"],
                    "title": "ArxivInput",
                    "type": "object",
                }
            },
        }
        ```

        Returns:
            list[dict]: 工具字典列表
        """
        return [tool.to_func_call() for tool in self._tools.values()]

    async def dispatch(self, tool_name: str, args: dict) -> str:
        tool = self.get_tool(tool_name)
        if not tool:
            return f"系统错误：找不到工具 '{tool_name}'"

        try:
            return await tool.process(**args)
        except Exception as e:
            return f"工具执行异常: {str(e)}"


tool_register = ToolRegister()
