# PaperPilot

一个用于自动撰写学术论文的 AI Agent，支持从文献检索、研究笔记整理到论文生成的全流程自动化。

## 功能特点

- **多阶段论文生成流程**：PLANNING（大纲生成）→ RESEARCHING（文献检索）→ WRITING（论文撰写）
- **智能文献检索**：自动搜索 ArXiv 论文，下载并阅读 PDF 全文
- **支持多种 LLM 提供商**：Ollama（本地）、OpenAI、智谱 AI（Zhipu）
- **流式输出**：实时查看生成进度和思考过程
- **自动生成 PDF**：使用 Typst 编译生成高质量学术论文 PDF
- **模块化设计**：易于扩展的工具系统，支持 Function Calling
- **完整状态管理**：追踪论文生成全流程状态
- **彩色日志输出**：基于 Rich 的美观终端输出和文件日志

## 项目结构

```
paperpilot/
├── src/
│   ├── config/      # 配置模块（Settings、Prompt模板）
│   ├── core/        # 核心逻辑（AgentEngine、LLM 接口）
│   ├── llms/        # LLM 实现（Ollama、OpenAI、Zhipu）
│   ├── models/      # 数据模型（Message、PaperContext）
│   ├── tools/       # 工具模块（ArXiv、PDF、文件操作）
│   └── utils/       # 工具类（日志、JSON提取、Markdown渲染）
├── data/            # 数据目录
│   ├── arxiv_download/  # 下载的 ArXiv 论文
│   └── outputs/         # 生成的论文输出
├── logs/            # 日志文件
├── main.py          # 项目入口
└── pyproject.toml   # 项目配置
```

## 工作原理

PaperPilot 采用三阶段状态机完成论文自动生成：

1. **PLANNING（规划阶段）**
   - 根据用户输入的主题生成论文大纲
   - 确定章节结构和标题

2. **RESEARCHING（研究阶段）**
   - 对每个章节进行 ArXiv 文献检索
   - 自动下载相关论文 PDF
   - 阅读全文并生成研究笔记
   - 收集参考文献信息

3. **WRITING（撰写阶段）**
   - 基于研究笔记撰写各章节内容
   - 生成 Typst 格式源文件
   - 编译输出最终 PDF

## 环境要求

- Python 3.13+
- uv 包管理工具
- Typst（用于 PDF 编译，可选，默认尝试使用 `typst` 库进行渲染，如果出错需要手动修复后重新尝试渲染）

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

#### 使用 Ollama（本地模型，不推荐小于等于 8B 的模型，可能会对任务理解有误）
```bash
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
```

#### 使用智谱 AI（Zhipu）
```bash
LLM_PROVIDER=zhipu
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_API_KEY=your_api_key_here
LLM_MODEL=glm-4.7-flash
```

#### 使用 OpenAI 兼容 API
```bash
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1/
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4
```

#### 可选配置项
```bash
# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# 最大对话轮数
MAX_TURNS=30

# 输出语言
OUTPUT_LANGUAGE=中文 # 使用自然语言描述即可，会注入到 Prompt 中

# LLM 温度参数 (0.0-1.0)
LLM_TEMP=0.7

# 是否启用思考模式
LLM_THINK=true
```

### 3. 运行项目

```bash
python main.py
```

然后输入你想要撰写的论文主题，Agent 将自动完成论文生成。

## 支持的工具

| 工具名 | 功能说明 |
|--------|----------|
| `arxiv_search` | 在 ArXiv 搜索学术论文 |
| `arxiv_download` | 下载 ArXiv 论文 PDF |
| `pdf_read` | 读取 PDF 文件内容 |
| `file_read` | 读取文本文件 |
| `file_write` | 写入文件内容 |
| `time_sleep` | 等待指定时间 |

## 输出文件

生成的论文将保存在 `outputs/` 目录下

## 支持的 LLM 提供商

| 提供商 | 说明 | 特点 |
|--------|------|------|
| Ollama | 本地部署 | 无需网络，隐私性好 |
| OpenAI | OpenAI API | 功能强大，兼容性好 |
| Zhipu | 智谱 AI | 国内可用，中文优化 |

## 开发指南

### 添加新的 LLM 支持

1. 在 `src/llms/` 目录下创建新的 LLM 类，继承 `LLMInterface`
2. 在 `src/llms/llm_factory.py` 中注册新的提供商

### 添加新的工具

1. 在 `src/tools/` 目录下创建新的工具类，继承 `BaseTool`
2. 在 `src/tools/register.py` 中，将新工具添加到 `all_tools` 中

## 重要说明

1. 本项目仅用于辅助撰写课程结课论文的**内容生成和文献整理**，不提供任何降低 AI 率（降重）的功能。
2. 使用本项目生成的论文后，请自行处理 AI 率检测和学术规范相关问题。
3. 生成的内容仅供参考和学习使用，请遵守学术诚信原则。
4. ArXiv 下载功能受网络环境影响，可能需要配置代理。

## 许可证

MIT License
