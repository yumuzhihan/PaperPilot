from pathlib import Path

from pydantic import BaseModel, Field

from src.config.settings import settings
from src.utils.logger_factory import LoggerFactory
from .tool_base import BaseTool


class FileReadInput(BaseModel):
    file_path: str = Field(..., description="要读取的文件路径")
    encoding: str = Field(default="utf-8", description="文件编码，默认 UTF-8")


class FileReadTool(BaseTool):
    name = "file_read"
    description = f"读取指定文件的内容（纯文本格式）。注意：此工具仅适用于文本文件，如需读取 PDF 文件，请使用 pdf_read 工具。数据的根目录为：{settings.DATA_DIR.resolve()}"
    args_schema = FileReadInput

    def __init__(self) -> None:
        super().__init__()
        self.logger = LoggerFactory.get_logger("file_read")

    async def process(self, **kwargs) -> str:
        try:
            args = FileReadInput(**kwargs)
        except Exception as e:
            return f"参数错误: {str(e)}"

        self.logger.debug(f"开始读取文件: {args.file_path}")

        try:
            base_dir = settings.DATA_DIR
            file_path = (
                base_dir / args.file_path
                if not Path(args.file_path).is_absolute()
                else Path(args.file_path)
            )

            if not file_path.exists():
                return f"文件不存在: {file_path}"

            if not file_path.is_file():
                return f"路径不是文件: {file_path}"

            # 检查文件扩展名，排除 PDF 文件
            if file_path.suffix.lower() == ".pdf":
                return f"检测到 PDF 文件，请使用 pdf_read 工具读取: {file_path}"

            with open(file_path, "r", encoding=args.encoding) as f:
                content = f.read()

            result_str = f"成功读取文件: {file_path}\n\n文件内容:\n{content}"
            self.logger.debug(f"成功读取文件: {file_path}，共 {len(content)} 个字符")
            return result_str

        except UnicodeDecodeError:
            return f"文件编码错误: 无法使用 {args.encoding} 编码读取文件，请尝试其他编码（如 gbk、latin-1）"
        except Exception as e:
            result_str = f"file_read 出错：{str(e)}"
            self.logger.error(result_str)
            return result_str
