import time
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils import LoggerFactory
from src.utils import markdown_streamer

# 1. 获取 Logger (带文件记录功能)
logger = LoggerFactory.get_logger("MainFlow")


def mock_llm_stream():
    """模拟 LLM 流式输出"""
    text = """
# 第一章：绪论

这是第一段话，非常长... (生成中)
... (生成完毕，SmartStreamer 会自动把它 print 上去，不再刷新)

## 1.1 研究背景

这里是第二段话。

```python
def hello():
    print("代码块内部不会被折叠")
    print("直到遇到闭合的 ```")
这是代码块后的新段落。
```

# 只需要调用 stream
full_content = markdown_streamer.stream(mock_llm_stream())

### 这种方案的优点

1.  **极致性能**：不管论文有 100 页还是 1000 页，Rich 永远只计算和渲染最后几行（Buffer）。CPU 占用率极低。
2.  **阅读体验好**：
    * 旧的内容（已生成的章节）是静止的，你可以随时向上滚动查看，不会因为屏幕刷新而跳动。
    * 新的内容（正在生成的段落）在一个漂亮的小框框里跳动。
3.  **代码块保护**：逻辑中增加了 `in_code_block` 检测，防止把代码块拦腰截断，导致语法高亮失效或格式错乱。

### 可能遇到的微小问题

* **标题层级**：如果你把 `# H1` 打印出去了，下面的 `## H2` 单独渲染时，Rich 可能不知道它属于 H1 下面（缩进可能受影响，不过通常 Markdown 渲染器不关心上下文缩进，所以问题不大）。
* **列表断裂**：如果一个列表项很长被切断了，Rich 渲染下一个列表项时可能会重新开始计数（比如从 `1.` 开始）。
    * *修复思路*：如果这对你很重要，可以将折叠条件改为仅在 `#` (标题) 出现时折叠，但这会降低折叠频率。通常按段落 `\n\n` 折叠是最佳平衡点。
"""
    for char in text:
        yield char
        time.sleep(0.02)  # 模拟网络延迟


def main():
    # --- 阶段 1: 思考与工具调用 (使用 Log + Status) ---
    # 这一步使用我们之前定义的 status_task
    with LoggerFactory.status_task("正在检索相关文献...", logger) as status:
        time.sleep(2)  # 模拟搜索
        logger.info("检索到 3 篇相关论文")
        status.update("正在阅读摘要...")
        time.sleep(1)

    # --- 阶段 2: 生成回复 (使用 Live Markdown) ---
    logger.info("开始生成大纲")  # 这条日志记录进文件

    # 这里的 stream 既负责展示，又负责收集完整文本
    full_response = markdown_streamer.stream(
        mock_llm_stream(), title="🤖 Qwen2.5 生成中..."
    )

    # --- 阶段 3: 后续处理 ---
    logger.info(f"生成完毕，全文字数: {len(full_response)}")
    # save_to_file(full_response) ...


if __name__ == "__main__":
    main()
