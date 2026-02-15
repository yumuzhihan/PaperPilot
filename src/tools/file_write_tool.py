from pydantic import BaseModel, Field

from src.config.settings import settings
from src.utils.logger_factory import LoggerFactory
from .tool_base import BaseTool


class FileWriteInput(BaseModel):
    file_path: str = Field(..., description="要写入的文件路径")
    content: str = Field(..., description="要写入的内容")
    mode: str = Field(default="w", description="写入模式，'w' 为覆盖，'a' 为追加")


class FileWriteTool(BaseTool):
    name = "file_write"
    description = f"将内容写入到指定文件中。如果文件不存在，会自动创建。数据的根目录为：{settings.DATA_DIR.resolve()}"
    args_schema = FileWriteInput

    def __init__(self) -> None:
        super().__init__()
        self.logger = LoggerFactory.get_logger("file_write")

    async def process(self, **kwargs) -> str:
        try:
            args = FileWriteInput(**kwargs)
        except Exception as e:
            return f"参数错误: {str(e)}"

        self.logger.debug(f"开始写入文件: {args.file_path}")

        try:
            if args.mode not in ("w", "a"):
                return f"无效的写入模式: {args.mode}，请使用 'w' (覆盖) 或 'a' (追加)"

            from pathlib import Path

            base_dir = settings.DATA_DIR
            file_path = (
                base_dir / args.file_path
                if not Path(args.file_path).is_absolute()
                else Path(args.file_path)
            )

            dir_path = file_path.parent
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)

            with open(file_path, args.mode, encoding="utf-8") as f:
                f.write(args.content)

            mode_text = "覆盖" if args.mode == "w" else "追加"
            result_str = f"成功以 {mode_text} 模式写入文件: {file_path}，共写入 {len(args.content)} 个字符"
            self.logger.debug(result_str)
            return result_str

        except Exception as e:
            result_str = f"file_write 出错：{str(e)}"
            self.logger.error(result_str)
            return result_str
