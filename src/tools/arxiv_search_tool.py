from pydantic import BaseModel, Field
import arxiv


from src.utils.logger_factory import LoggerFactory
from .tool_base import BaseTool


class ArxivInput(BaseModel):
    query: str = Field(..., description="搜索关键词")
    max_results: int = Field(default=5, description="返回的最大结果数量")
    offset: int = Field(default=0, description="分页偏移量，用于翻页")


class ArxivSearchTool(BaseTool):
    name = "arxiv_search"
    description = "在 ArXiv 上搜索学术论文。如果结果不足，请使用 offset 参数翻页。"
    args_schema = ArxivInput

    def __init__(self) -> None:
        super().__init__()

        self.client = arxiv.Client(delay_seconds=3, num_retries=5)
        self.logger = LoggerFactory.get_logger("search_arxiv")

    async def process(self, **kwargs) -> str:
        try:
            args = ArxivInput(**kwargs)
        except Exception as e:
            return f"参数错误: {str(e)}"

        self.logger.debug(f"开始搜索 Arxiv，关键词为：{args.query}")

        try:
            search = arxiv.Search(
                query=args.query,
                max_results=args.max_results,
                sort_by=arxiv.SortCriterion.Relevance,
                sort_order=arxiv.SortOrder.Descending,
            )

            results_generator = self.client.results(search=search, offset=args.offset)

            papers: list[arxiv.Result] = []

            for result in results_generator:
                papers.append(result)
                if len(papers) >= args.max_results:
                    break

            if not papers:
                return (
                    f"未找到关于 '{args.query}' 的更多论文(当前 offset: {args.offset})"
                )

            response = [f"找到了 {len(papers)} 篇论文 (Offset: {args.offset}):\n"]

            for i, paper in enumerate(papers):
                index = args.offset + i + 1
                response.append(
                    f"[{index}] Title: {paper.title}\n"
                    f"    Authors: {', '.join(a.name for a in paper.authors[:3])}\n"
                    f"    Published: {paper.published.strftime('%Y-%m-%d')}\n"
                    f"    Abstract: {paper.summary[:10]}... (如果你需要详细信息，请调用工具下载论文)\n"
                    f"    PDF: {paper.pdf_url}\n"
                    f"    PDF_ID: {paper.get_short_id()}\n"
                )

            result_str = "\n".join(response)
            self.logger.debug(f"查询完成，结果包含 {len(result_str)} 个字符")
            return result_str
        except Exception as e:
            result_str = f"search_arxiv 出错：{str(e)}"
            return result_str
