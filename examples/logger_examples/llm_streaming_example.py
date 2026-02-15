"""
大模型流式输出集成示例
演示如何在实际项目中集成流式日志输出
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils import LoggerFactory


class MockLLMClient:
    """模拟大模型客户端"""

    def __init__(self):
        self.logger = LoggerFactory.get_logger("LLM_Client")
        _, self.streaming_handler = LoggerFactory.get_streaming_logger("LLM_Stream")

    def stream_chat(self, prompt: str):
        """
        模拟流式聊天接口
        在实际使用中，这里应该是调用真实的大模型API
        """
        self.logger.info(f"[cyan]发送提示:[/cyan] {prompt}")

        # 模拟的响应内容
        mock_response = """基于您的问题，我来详细解答：

首先，这个问题涉及到几个关键概念：
1. 数据结构的选择
2. 算法的时间复杂度
3. 空间优化策略

让我逐一为您分析..."""

        self.logger.info("[yellow]开始接收流式响应...[/yellow]")
        print("\n[AI] ", end="", flush=True)

        # 流式输出每个字符
        for char in mock_response:
            self.streaming_handler.stream_chunk(char)
            time.sleep(0.01)  # 模拟网络延迟

        # 结束流式输出
        full_response = self.streaming_handler.end_stream()

        self.logger.info(f"[green]✓ 响应完成[/green] (共 {len(full_response)} 字符)")

        return full_response


class PaperAnalyzer:
    """论文分析器示例"""

    def __init__(self):
        self.logger = LoggerFactory.get_logger("PaperAnalyzer", show_path=False)
        self.llm_client = MockLLMClient()

    def analyze_paper(self, paper_title: str):
        """分析论文"""
        self.logger.info(f"[bold blue]开始分析论文:[/bold blue] {paper_title}")

        # 构建提示词
        prompt = f"请分析论文《{paper_title}》的核心贡献和创新点"

        # 调用大模型进行流式分析
        response = self.llm_client.stream_chat(prompt)

        self.logger.info("[bold green]✓ 分析完成[/bold green]")

        return response


def example_simple_streaming():
    """简单的流式输出示例"""
    print("\n" + "=" * 60)
    print("示例1: 简单流式输出")
    print("=" * 60 + "\n")

    # 获取流式handler
    streaming_handler = LoggerFactory.get_streaming_handler("demo")

    print("AI回复: ", end="", flush=True)

    text = "这是一个简单的流式输出示例，模拟大模型逐字返回内容。"
    for char in text:
        streaming_handler.stream_chunk(char)
        time.sleep(0.05)

    streaming_handler.end_stream()


def example_with_logger():
    """带日志记录的流式输出"""
    print("\n" + "=" * 60)
    print("示例2: 带日志记录的流式输出")
    print("=" * 60 + "\n")

    logger, streaming_handler = LoggerFactory.get_streaming_logger("chat")

    logger.info("用户发送了一条消息")

    print("\n[助手] ", end="", flush=True)

    response = "收到您的消息！我会尽快为您处理。"
    for char in response:
        streaming_handler.stream_chunk(char)
        time.sleep(0.03)

    full_text = streaming_handler.end_stream()
    logger.info(f"助手回复完成，共 {len(full_text)} 字符")


def example_paper_analysis():
    """论文分析完整示例"""
    print("\n" + "=" * 60)
    print("示例3: 论文分析流式输出")
    print("=" * 60 + "\n")

    analyzer = PaperAnalyzer()
    analyzer.analyze_paper("Attention Is All You Need")


def example_multiple_rounds():
    """多轮对话示例"""
    print("\n" + "=" * 60)
    print("示例4: 多轮对话流式输出")
    print("=" * 60 + "\n")

    logger = LoggerFactory.get_logger("MultiRound", show_time=False)
    streaming_handler = LoggerFactory.get_streaming_handler("conversation")

    conversations = [
        ("用户", "你好，请介绍一下你自己"),
        ("AI", "你好！我是一个AI助手，专注于帮助用户处理各种问题。"),
        ("用户", "你能做什么？"),
        ("AI", "我可以回答问题、提供建议、分析数据等多种任务。"),
    ]

    for role, message in conversations:
        if role == "用户":
            logger.info(f"[bold cyan]{role}:[/bold cyan] {message}")
        else:
            logger.info(f"[bold green]{role}:[/bold green]")
            print(f"  {role}: ", end="", flush=True)
            for char in message:
                streaming_handler.stream_chunk(char)
                time.sleep(0.02)
            streaming_handler.end_stream()

        time.sleep(0.3)  # 轮次间隔


def example_with_progress():
    """带进度提示的流式输出"""
    print("\n" + "=" * 60)
    print("示例5: 带进度提示的流式输出")
    print("=" * 60 + "\n")

    logger = LoggerFactory.get_logger("Progress")
    streaming_handler = LoggerFactory.get_streaming_handler("progress_stream")

    logger.info("[cyan]正在生成长文本...[/cyan]")

    long_text = """这是一段较长的文本，用于演示如何在流式输出时显示进度。
在实际应用中，您可能需要处理更长的内容，比如论文摘要、研究报告等。
通过流式输出，用户可以立即看到生成的内容，而不需要等待全部完成。
这大大改善了用户体验，特别是在处理大型语言模型的响应时。"""

    print("\n[输出] ", end="", flush=True)

    total_chars = len(long_text)
    for i, char in enumerate(long_text):
        streaming_handler.stream_chunk(char)
        time.sleep(0.01)

    full_text = streaming_handler.end_stream()
    logger.info(f"[green]✓ 生成完成[/green] (总计 {len(full_text)} 字符)")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("大模型流式输出集成示例")
    print("=" * 60)

    # 运行所有示例
    example_simple_streaming()
    example_with_logger()
    example_paper_analysis()
    example_multiple_rounds()
    example_with_progress()

    print("\n" + "=" * 60)
    print("所有示例演示完成！")
    print("=" * 60 + "\n")
