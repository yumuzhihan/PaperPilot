from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pypdf import PdfReader

from src.config import settings
from src.utils.logger_factory import LoggerFactory
from .tool_base import BaseTool


class PDFReadInput(BaseModel):
    file_path: str = Field(..., description="PDF 文件路径，支持绝对路径以及相对路径")
    page_start: Optional[int] = Field(default=1, description="起始页码（从 1 开始）")
    page_end: Optional[int] = Field(
        default=None, description="结束页码（包含），默认为最后一页"
    )
    max_chars: Optional[int] = Field(
        default=8000,
        description="最大返回字符数，避免输出过长",
    )


class PDFReadTool(BaseTool):
    name = "pdf_read"
    description = "读取 PDF 文件的内容，支持指定页码范围。数据的根目录为：{}".format(
        settings.DATA_DIR.resolve()
    )
    args_schema = PDFReadInput

    def __init__(self) -> None:
        super().__init__()
        self.logger = LoggerFactory.get_logger("pdf_read")

    def _resolve_path(self, file_path: str) -> Path:
        """解析文件路径，支持绝对路径和相对路径"""
        path = Path(file_path)
        if path.is_absolute():
            return path
        return settings.DATA_DIR / path

    async def process(self, **kwargs) -> str:
        try:
            args = PDFReadInput(**kwargs)
        except Exception as e:
            return f"参数错误: {str(e)}"

        try:
            file_path = self._resolve_path(args.file_path)

            if not file_path.exists():
                return f"文件不存在: {file_path}"

            if not file_path.suffix.lower().endswith(".pdf"):
                return f"不是 PDF 文件: {file_path}"

            self.logger.debug(f"正在读取 PDF: {file_path}")

            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)

            page_start = max(1, args.page_start) if args.page_start else 1
            page_end = min(total_pages, args.page_end) if args.page_end else total_pages

            if page_start > page_end:
                return f"起始页码 {page_start} 不能大于结束页码 {page_end}"

            content_parts = [f"文件: {file_path.name}\n总页数: {total_pages}\n"]
            content_parts.append(f"正在读取页码: {page_start} - {page_end}\n\n")

            for page_num in range(page_start, page_end + 1):
                page = reader.pages[page_num - 1]
                text = page.extract_text()
                content_parts.append(f"--- 第 {page_num} 页 ---\n{text}\n")

            full_content = "".join(content_parts)

            if args.max_chars and len(full_content) > args.max_chars:
                full_content = (
                    full_content[: args.max_chars]
                    + f"\n\n... (内容已截断，完整内容约 {len(full_content)} 字符)"
                )

            self.logger.debug(f"读取完成，共提取 {len(full_content)} 个字符")
            return full_content

        except Exception as e:
            self.logger.error(f"PDF 读取异常: {e}")
            return f"读取 PDF 时发生错误: {str(e)}"
