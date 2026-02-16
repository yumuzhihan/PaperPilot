import re
from pathlib import Path
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
import arxiv

from src.config import settings
from src.utils import LoggerFactory
from .tool_base import BaseTool


class ArxivDownloadInput(BaseModel):
    paper_id: str = Field(
        description="论文的ID，例如 '2101.12345'，或者论文的 PDF/ABS 链接"
    )
    filename: Optional[str] = Field(
        default=None,
        description="保存的文件名（不含路径）。如果不提供，默认使用 'paper_id.pdf' 或论文标题",
    )


class ArxivDownloadTool(BaseTool):
    name = "arxiv_download"
    description = "在 ArXiv 上下载学术论文，需要传入论文的 ID 或者 PDF/ABS 连接"
    args_schema = ArxivDownloadInput

    def __init__(self):
        super().__init__()

        self.client = arxiv.Client()
        self.download_dir = Path(settings.DATA_DIR) / "arxiv_download"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.logger = LoggerFactory.get_logger("ArxivDownloader")

    def _extract_id(self, input_str: str) -> str:
        """
        从 URL 或字符串中提取 Arxiv ID
        兼容:
        - 2101.12345
        - https://arxiv.org/abs/2101.12345
        - https://arxiv.org/pdf/2101.12345.pdf
        """
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", input_str)
        if match:
            return match.group(1)
        return input_str

    def _sync_download(self, paper_id: str, filename: str | None = None) -> str:
        """
        同步下载逻辑（将被扔到线程池运行）
        """
        search = arxiv.Search(id_list=[paper_id])
        try:
            paper = next(self.client.results(search))
        except StopIteration:
            raise ValueError(f"未找到 ID 为 {paper_id} 的论文")

        if not filename:
            filename = f"{paper_id}.pdf"

        if not filename.endswith(".pdf"):
            filename += ".pdf"

        path = paper.download_pdf(dirpath=str(self.download_dir), filename=filename)
        return str(path)

    async def process(self, **kwargs) -> str:
        try:
            args = ArxivDownloadInput(**kwargs)

            clean_id = self._extract_id(args.paper_id)
            self.logger.debug(f"正在下载论文 ID: {clean_id}...")

            file_path = await asyncio.to_thread(
                self._sync_download, paper_id=clean_id, filename=args.filename
            )

            return f"下载成功！\n文件已保存至: {file_path} \n"

        except ValueError as ve:
            return f"下载失败: {str(ve)}"
        except Exception as e:
            self.logger.error(f"Arxiv 下载异常: {e}")
            return f"下载过程中发生错误: {str(e)}"
