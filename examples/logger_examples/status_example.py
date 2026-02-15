"""
测试文件输出功能
演示日志同时输出到控制台和文件
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import settings
from src.utils import LoggerFactory


logger = LoggerFactory.get_logger("AgentEngine")


def run_agent_loop():

    # 场景 1: 搜索知网
    # 使用 with 语句，自动处理 UI 转圈和文件日志
    with LoggerFactory.status_task("正在检索知网数据...", logger) as status:
        # 这里执行耗时操作
        # 注意：在 status 内部打印日志，Rich 会自动处理，不会破坏 UI
        logger.debug("连接 Playwright...")
        # results = search_cnki("深度学习")
        time.sleep(3)

        # 如果中间想更新状态文字
        status.update(f"检索完成，正在下载 2 篇文献...")
        time.sleep(2)

    # 场景 2: 大模型思考 (流式输出)
    # 流式输出时，通常不需要 spinner，因为文字在动
    logger.info("开始生成大纲...")
    time.sleep(2)

    # 这里不需要 status_task，直接流式打印
    # 假设你有一个 streaming_handler
    # for chunk in llm.stream():
    #     streaming_handler.stream_chunk(chunk)


if __name__ == "__main__":
    run_agent_loop()
