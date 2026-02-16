# PaperPilot

一个用于自动撰写课程结课论文的 AI Agent。

## 功能特点

- 基于大语言模型（LLM）的论文自动生成
- 支持流式输出，实时查看生成进度
- 模块化设计，便于扩展
- 灵活的提示词（Prompt）配置
- 完整的日志记录

## 项目结构

```
paperpilot/
├── src/
│   ├── config/      # 配置模块
│   ├── core/        # 核心接口（LLM 接口定义）
│   ├── models/      # 数据模型
│   ├── tools/       # 工具模块
│   └── utils/       # 工具类
├── main.py          # 项目入口
└── pyproject.toml   # 项目配置
```

## 环境要求

- Python 3.13+
- uv 包管理工具

## 快速开始

1. 安装依赖：

```bash
uv sync
```

2. 配置环境变量：

在项目根目录创建 `.env` 文件，配置你的 LLM API 密钥。示例：

```bash
# LLM 提供商（支持 zhipu, openai, anthropic 等）
LLM_PROVIDER=zhipu

# API 地址（根据提供商不同而变化）
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

# API 密钥
LLM_API_KEY=your_api_key_here

# 使用的模型
LLM_MODEL=glm-4.7-flash
```

> 注意：请将 `your_api_key_here` 替换为你的实际 API 密钥。

3. 运行项目：

```bash
python main.py
```

## 重要说明

本项目仅用于辅助撰写课程结课论文的**内容生成**，不提供任何降低 AI 率（降重）的功能。使用本项目生成的论文后，请自行处理 AI 率检测相关问题。

## 许可证

MIT License
