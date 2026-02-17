from pydantic import BaseModel, Field
import asyncio

from src.utils.logger_factory import LoggerFactory
from .tool_base import BaseTool


class TimeSleepInput(BaseModel):
    seconds: float = Field(..., description="睡眠时间，单位为秒")


class TimeSleepTool(BaseTool):
    name = "time_sleep"
    description = "让系统等待指定的时间（秒）。用于控制请求速率或等待某些操作完成。"
    args_schema = TimeSleepInput

    def __init__(self) -> None:
        super().__init__()
        self.logger = LoggerFactory.get_logger("time_sleep")

    async def process(self, **kwargs) -> str:
        try:
            args = TimeSleepInput(**kwargs)
        except Exception as e:
            return f"参数错误: {str(e)}"

        self.logger.debug(f"开始等待 {args.seconds} 秒")

        try:
            await asyncio.sleep(args.seconds)
            return f"已等待 {args.seconds} 秒"
        except Exception as e:
            return f"time_sleep 出错：{str(e)}"
