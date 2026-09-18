# PROJECT

DBA - Daily Brief Agent 的项目上下文文档。

## 项目目标

把 RSS 新闻源抓取、AI 筛选、AI 总结、格式化和邮件发送串成一个每天可运行的日报流水线，输出一封面向科技/商业信息的简报邮件。

当前项目的核心方向是先做稳定的 pipeline v1.0，再逐步加 ranking、trend analysis、memory 和更强的 agent 能力。

## 当前架构

项目采用固定顺序的线性流水线：

1. `rss_reader.py` 抓取 RSS 源，整理为统一 JSON 列表
2. `ai_filter.py` 调用本地 Ollama/Qwen，对新闻做筛选、分类和去重
3. `ai_summarizer.py` 调用 OpenRouter 上的 Claude 模型生成短摘要
4. `formatter.py` 把结果拼成简报正文
5. `sender.py` 负责邮件发送
6. `main.py` 统一编排流程并返回运行结果

当前设计仍然是 pipeline，不是具备自主规划能力的 agent。

## 文件职责

### `main.py`

主入口和总编排器。负责依次执行抓取、筛选、总结、格式化和发送，并记录每一步状态。

### `rss_reader.py`

负责 RSS 抓取与标准化输出。把各个 feed 的内容转成统一字段：
`title`、`link`、`summary`、`published`、`source`。

### `ai_filter.py`

调用本地 Ollama/Qwen 做新闻筛选、分类和去重。当前目标输出是扁平化文章列表，供下游 summarizer 直接消费。

### `ai_summarizer.py`

调用 OpenRouter 的 OpenAI-compatible 接口，使用 Claude 模型为每篇文章生成简洁摘要。输出会在原文章结构上增加 `ai_summary`。

### `formatter.py`

把文章列表转换为最终可发送的简报正文。目前实现非常轻量，属于最小可用版本。

### `sender.py`

邮件发送模块。当前仓库中该文件为空，属于未完成部分。

### `config.py`

集中管理 RSS 源、模型名、摘要参数、日志参数和邮件环境变量。

### `brief.md`

已有的一份示例简报产物，可作为格式参考，但不代表当前 pipeline 的最终输出规范。

### `output/raw_news.json`

RSS 抓取样例数据，说明抓取阶段已经有过一次成功运行。

### `gpt-prompt modules.txt`

关于项目阶段划分和后续演进方向的文字草稿，偏产品/路线说明。

### `gpt-prompt improvements.txt`

关于后续优化方向的补充草稿，偏愿景和增强项。

## 当前完成状态

### 已完成

1. RSS 抓取模块已经成型，并能产出标准化 JSON。
2. `ai_filter.py` 已经接上本地 Ollama 调用与 Markdown 风格解析。
3. `ai_summarizer.py` 已经具备完整的 OpenRouter 调用、重试和 batch 逻辑。
4. `main.py` 已经有完整的 pipeline 编排骨架和状态回传结构。
5. `config.py` 已经把大部分可调参数集中管理。

### 未完成

1. `sender.py` 为空，邮件发送闭环未完成。
2. `ai_filter.py` 和 `ai_summarizer.py` 的数据契约需要继续统一和稳定。
3. `formatter.py` 仍是最简实现，离真正可读的日报格式还有差距。
4. 缺少 README、运行说明、环境变量示例和测试。
5. 还没有完整的端到端稳定验证流程。

## TODO

1. 实现 `sender.py`，先打通最小邮件发送闭环。
2. 固化 `ai_filter.py` 的输出结构，确保返回 `list[dict]`。
3. 强化 `formatter.py`，让输出更适合邮件阅读。
4. 增加 `.env.example` 和 README，补齐运行所需配置说明。
5. 添加 smoke test，验证 fetch → filter → summarize → format 的链路。
6. 统一 prompt、模型配置和项目文档中的阶段描述。
7. 清理乱码注释和历史草稿，统一编码和文档风格。

## 开发规范

1. 先读现有代码，再改动，优先沿用项目里已有的模式。
2. 尽量保持最小修改，避免无关重构。
3. 不要随意改动其他模块的接口契约，尤其是 pipeline 上下游的数据结构。
4. 新增功能前先确认输入输出格式，避免主流程断裂。
5. 配置集中放在 `config.py`，敏感值从 `.env` 读取。
6. 保持 ASCII 为默认字符集，除非文件本身已经使用 Unicode。
7. 只在必要时添加简短注释，避免解释性废话。
8. 修改后优先做语法检查和最小可运行验证。
9. 不要引入不必要的复杂抽象，先把 v1.0 做稳。

## 备注

这个项目当前最重要的不是扩展功能，而是让现有 pipeline 真正跑通并稳定产出日报。

