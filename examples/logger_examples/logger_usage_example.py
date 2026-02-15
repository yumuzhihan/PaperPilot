"""
LoggerFactory 使用示例
演示如何使用基于RICH的彩色日志和流式输出功能
"""

import logging
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils import LoggerFactory


def example_basic_logging():
    """基础日志使用示例"""
    print("\n=== 基础彩色日志示例 ===\n")

    # 获取一个带RICH彩色输出的logger
    logger = LoggerFactory.get_logger("MyApp", logging_level=logging.DEBUG)

    logger.debug("这是一条调试信息")
    logger.info("这是一条普通信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    logger.critical("这是一条严重错误信息")

    # 使用RICH的markup语法
    logger.info("[bold green]成功![/bold green] 操作已完成")
    logger.info("[bold blue]进度:[/bold blue] 50%")


def example_custom_logger():
    """自定义logger配置示例"""
    print("\n=== 自定义配置示例 ===\n")

    # 不显示时间和路径的简洁logger
    simple_logger = LoggerFactory.get_logger(
        "SimpleApp", show_time=False, show_path=False
    )
    simple_logger.info("简洁的日志输出")

    # 显示完整路径的详细logger
    detailed_logger = LoggerFactory.get_logger(
        "DetailedApp", show_time=True, show_path=True
    )
    detailed_logger.info("详细的日志输出，包含时间和路径")

    # 不使用RICH的传统logger
    plain_logger = LoggerFactory.get_logger("PlainApp", use_rich=False)
    plain_logger.info("传统格式的日志输出")


def example_streaming_output():
    """流式输出示例（模拟大模型流式返回）"""
    print("\n=== 流式输出示例 ===\n")

    # 获取流式logger和handler
    logger, streaming_handler = LoggerFactory.get_streaming_logger("LLM")

    logger.info("开始生成回复...")

    # 模拟大模型流式返回文本
    response_chunks = [
        "你好",
        "！",
        "我是",
        "一个",
        "AI",
        "助手",
        "。",
        "很高兴",
        "为你",
        "服务",
        "！",
    ]

    print("\n流式输出: ", end="", flush=True)
    for chunk in response_chunks:
        streaming_handler.stream_chunk(chunk)
        time.sleep(0.1)  # 模拟网络延迟

    # 结束流式输出，获取完整内容
    full_response = streaming_handler.end_stream()

    logger.info(f"生成完成，总字符数: {len(full_response)}")
    logger.info(f"完整内容: {full_response}")


def example_llm_integration():
    """模拟与大模型集成的完整示例"""
    print("\n=== 大模型集成示例 ===\n")

    # 创建应用logger和流式handler
    app_logger = LoggerFactory.get_logger("PaperPilot")
    _, streaming_handler = LoggerFactory.get_streaming_logger("LLM_Stream")

    app_logger.info("[bold cyan]开始处理用户请求...[/bold cyan]")

    # 模拟调用大模型API
    app_logger.info("正在连接大模型API...")

    # 模拟流式响应
    print("\n[AI回复] ", end="", flush=True)

    simulated_response = """当然可以！我来为你总结这篇论文的核心要点：

1. 研究背景：本文探讨了深度学习在自然语言处理领域的应用
2. 主要方法：提出了一种新的注意力机制
3. 实验结果：在多个基准数据集上取得了SOTA性能
4. 创新点：降低了计算复杂度，提高了模型效率"""

    # 逐字符流式输出
    for char in simulated_response:
        streaming_handler.stream_chunk(char)
        time.sleep(0.02)  # 模拟真实的流式延迟

    full_response = streaming_handler.end_stream()

    app_logger.info(
        f"[bold green]✓[/bold green] 回复生成完成 (共 {len(full_response)} 字符)"
    )


def example_error_handling():
    """错误处理和异常日志示例"""
    print("\n=== 错误处理示例 ===\n")

    logger = LoggerFactory.get_logger("ErrorDemo")

    try:
        # 模拟一个错误
        result = 10 / 0
    except ZeroDivisionError as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        logger.info("[yellow]已捕获异常，程序继续运行[/yellow]")


if __name__ == "__main__":
    print("=" * 60)
    print("LoggerFactory 功能演示")
    print("=" * 60)

    # 运行所有示例
    example_basic_logging()
    example_custom_logger()
    example_streaming_output()
    example_llm_integration()
    example_error_handling()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
