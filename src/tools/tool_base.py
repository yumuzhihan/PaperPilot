from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class BaseTool(ABC):
    """
    所有工具的基类
    """

    name: str = "base_tool"
    args_schema: type[BaseModel]
    description: str = "这个工具不应该被调用"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "name"):
            raise TypeError(f"类 {cls.__name__} 必须定义 'name' 属性")

    @abstractmethod
    async def process(self, **kwargs) -> str:
        """
        工具的具体执行逻辑
        """
        raise NotImplementedError("工具必须实现 process 方法")

    def to_prompt(self) -> str:
        """
        自动生成 System Prompt 中需要的一行描述
        """
        return f"- {self.name}: {self.description}"

    def to_func_call(self) -> dict[str, Any]:
        """
        自动将工具转换为 Ollama/OpenAI 需要的 JSON Schema 格式
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }
