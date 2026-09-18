# DBA — Daily Brief Agent

把 RSS 新闻变成一封可读的科技与商业日报：本地模型负责筛选、分类和语义去重，OpenRouter 上的模型负责生成摘要，最后输出 Markdown 并通过 SMTP 发送邮件。

这是一个模块化 Python 流水线原型。虽然项目名称包含 Agent，目前仍按固定步骤执行，不具备自主规划、长期记忆或内置定时调度能力。

## 工作流程

```text
RSS 新闻源
  → rss_reader.py       抓取、清洗和标准化
  → ai_filter.py        本地 Ollama / Qwen 筛选、分类、去重
  → ai_summarizer.py    OpenRouter 生成中英双语摘要
  → formatter.py        组装 Markdown 日报
  → sender.py           保存本地文件，再通过 SMTP 发邮件
```

摘要提示词采用三段式结构：`KEY EVENT`（发生了什么）、`WHY IT MATTERS`（为什么重要）、`IMPACT`（后续影响）。摘要基于 RSS 片段，而不是抓取文章全文。

## 环境准备

- Python 3.10 或更高版本；仓库使用了 `str | None` 等类型语法。
- 已安装并运行的 Ollama，默认服务地址为 `http://localhost:11434`。
- 本地模型 `qwen2.5:14b`，需要足够的内存或显存。
- 可用的 OpenRouter API Key，以及能够访问 RSS、OpenRouter 和 SMTP 服务的网络。
- 如需发送邮件，准备支持 STARTTLS 的 SMTP 账号和凭据。

### 1. 获取项目并安装依赖

以下命令以 Windows PowerShell 为例：

```powershell
git clone https://github.com/Floragalaxy720/DBA-Daily-Brief-Agent.git
cd DBA-Daily-Brief-Agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

直接调用虚拟环境中的 Python，无需激活虚拟环境。Linux / macOS 可将后续命令中的 `.\.venv\Scripts\python.exe` 替换为 `.venv/bin/python`。

Python 依赖包括 `feedparser`、`requests`、`openai` 和 `python-dotenv`。其中 `openai` SDK 用于访问 OpenRouter 的兼容接口，不代表直接调用 OpenAI 服务。

### 2. 准备本地模型

```powershell
ollama pull qwen2.5:14b
ollama list
```

确保 Ollama 服务正在运行。若未启动，可在另一个终端执行 `ollama serve`；已经运行时无需重复启动。

### 3. 配置环境变量

在项目根目录创建 `.env`，按实际账号填写以下内容（均为占位值）：

```dotenv
OPENROUTER_API_KEY=your_openrouter_api_key
EMAIL_SENDER=sender@example.com
EMAIL_PASSWORD=your_smtp_password_or_app_password
EMAIL_RECIPIENT=recipient@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

`config.py` 会通过 `python-dotenv` 加载配置。使用 Gmail 时，`EMAIL_PASSWORD` 应填写适用的应用专用密码，而不是普通登录密码；其他服务请使用相应 SMTP 凭据。

`.env` 已被 `.gitignore` 排除。不要把真实密钥、邮箱密码或含凭据的日志提交到公开仓库。

## 运行

### 完整流水线

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe main.py
```

**这条命令会调用外部摘要 API，并在条件满足时实际发送邮件。** OpenRouter 调用可能产生费用。

- 主流程读取 `config.py` 中的 `RSS_FEEDS`，每个源默认最多抓取 10 条。
- 筛选提示词只处理输入的前 50 条新闻。
- 成功生成中英双语摘要的文章少于 `MIN_ARTICLES_TO_SEND`（默认 3）时，跳过邮件发送。
- 进入发送阶段后，先保存 `output/daily_brief.md`，再验证邮件配置并尝试发送；即使 SMTP 失败，已保存的文件仍可查看。
- 当前邮件正文是纯文本 Markdown，不是渲染后的 HTML 邮件。

`run_pipeline()` 返回运行状态、各阶段文章数量、发送结果、运行时间和错误信息。命令行入口遇到 `failed` 时退出码为 1；`success` 和 `skipped` 均为 0，因此退出码为 0 不一定表示邮件已发送。

### 分阶段检查

只抓取新闻并保存 JSON，不调用模型、不发邮件：

```powershell
.\.venv\Scripts\python.exe rss_reader.py --save
```

结果写入 `output/raw_news.json`。注意：这个独立入口使用 `rss_reader.py` 内的 `DEFAULT_RSS_FEEDS`，每个源最多取 5 条，与 `main.py` 的配置不同。

调用本地模型筛选已保存的新闻，不调用 OpenRouter、不发邮件：

```powershell
.\.venv\Scripts\python.exe ai_filter.py --input output/raw_news.json --output output/filtered_news.json
```

可通过 `--model` 覆盖此独立入口的模型名称。虽然参数帮助文字仍提到 Markdown，当前实际输出是扁平化文章列表的 **JSON**。

只预览格式化结果，不访问网络、不发邮件：

```powershell
.\.venv\Scripts\python.exe -c "from formatter import format_newsletter; print(format_newsletter([{'title': 'Demo news', 'summary': '示例新闻片段', 'ai_summary': 'KEY EVENT: Demo event.', 'source': 'example.com', 'link': 'https://example.com', 'category': '科技'}]))"
```

`python ai_summarizer.py` 会对文件中的虚构示例新闻调用真实 OpenRouter API，可能产生费用；这些示例不是事实新闻，也不是离线测试。

## 可调配置

| 位置 | 配置 | 当前默认值 / 用途 |
| --- | --- | --- |
| `config.py` | `RSS_FEEDS` | 完整流水线的新闻源列表 |
| `config.py` | `OPENROUTER_MODEL` | `anthropic/claude-sonnet-4` |
| `config.py` | `SUMMARIZER_MAX_TOKENS` | 每篇摘要响应上限 300 tokens |
| `config.py` | `SUMMARIZER_BATCH_SIZE` | 每组 5 篇，组内逐篇串行调用 |
| `config.py` | `SUMMARIZER_RETRY_ATTEMPTS` | 最多 3 次尝试；具体重试行为取决于异常类型 |
| `config.py` | `SUMMARIZER_RETRY_DELAY` | 基础等待时间 5 秒 |
| `config.py` | `MIN_ARTICLES_TO_SEND` | 至少 3 篇成功摘要才发送 |
| `config.py` | `LOG_LEVEL` | 默认 `INFO`，可改为 `DEBUG` |
| `ai_filter.py` | `DEFAULT_MODEL` | `qwen2.5:14b` |
| `ai_filter.py` | `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `ai_filter.py` | `TEMPERATURE` / `MAX_TOKENS` | 0.1 / 2048 |

上表描述仓库中的配置值，不保证模型或外部服务始终可用。主入口暂无命令行配置参数；调整主流程筛选模型需要修改 `ai_filter.py` 中的默认值。

## 项目结构

```text
DBA-Daily-Brief-Agent/
├── main.py                 流水线编排和退出状态
├── rss_reader.py           RSS 抓取、文本清洗、排序
├── ai_filter.py            Ollama 调用和分类结果解析
├── ai_summarizer.py        OpenRouter 双语摘要和重试
├── formatter.py            Markdown 排版
├── sender.py               本地保存、SMTP STARTTLS 发送
├── config.py               主流程配置和环境变量读取
├── requirements.txt        Python 依赖
├── README.md               安装与使用说明
├── PROJECT.md              历史项目上下文，部分状态已过时
├── brief.md                历史示例简报
├── gpt-prompt modules.txt   阶段规划草稿
├── gpt-prompt improvements.txt  优化方向草稿
├── .gitignore              敏感配置和本地产物排除规则
├── .env                    本地创建，不入库
└── output/                 运行时生成，不入库
```

## 当前限制与排查

- **不是完整的双语邮件展示**：摘要模块生成 `english_summary` 和 `chinese_summary`，但格式化模块仍展示筛选后的 `summary` 和兼容字段 `ai_summary`，尚未读取 `chinese_summary`。筛选阶段也未保留 `published`，最终发布时间通常显示 `N/A`。
- **模型输出解析较脆弱**：筛选模块按固定 Markdown 分隔符解析，不符合格式的条目会被跳过。若筛选结果为空，检查模型输出与日志；Ollama 请求失败目前会直接退出进程。
- **摘要可能被剔除**：只有同时解析到英文和中文摘要的文章才保留。输出截断或格式不符时，可检查日志、提示词以及 `SUMMARIZER_MAX_TOKENS`。
- **RSS 数据不等于当天新闻**：当前没有严格的日期窗口或跨次运行去重；默认新闻源的有效性也需要自行检查。
- **避免直接串联 RSS 标准输出**：独立 RSS 入口会在标准输出中打印状态文字，不能保证输出为纯 JSON；建议使用 `--save` 后再通过 `--input` 读取文件。
- **SMTP 失败**：确认配置完整、端口正确、服务支持 STARTTLS，并检查认证与网络连接。发送阶段已保存的简报可在 `output/daily_brief.md` 查看。
- **尚无内置定时器和自动化测试套件**：每次执行 `main.py` 只运行一轮。每日运行需要另外配置 Windows 任务计划程序或其他调度器，工作目录应设为项目根目录。

后续可完善双语字段对接、结构化筛选输出、日期与去重策略、HTML 邮件、自动化测试和定时部署。目前不要将原型输出视为经过事实核验的新闻结论。
