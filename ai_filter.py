"""
ai_filter.py
━━━━━━━━━━━━
【真正职责】
  • 接收 rss_reader.py 输出的 JSON 列表（stdin 或文件）
  • 调用本地 Qwen 模型（通过 Ollama API）进行：
      1. 新闻筛选（剔除广告/低质/重复）
      2. 新闻分类（科技/商业/娱乐/其他）
      3. 语义去重（相似内容只留 1 条）
  • 输出结构化简报（Markdown 格式）

【不负责】
  • 不抓取 RSS（输入必须由上游提供）
  • 不写网络请求（除调用本地 Ollama）
  • 不管理配置（模型名/温度等从 config 或参数读取）

【输入格式】（严格遵循 rss_reader 输出）
[
  {
    "title": str,
    "link": str,
    "summary": str,
    "published": str,  # optional
    "source": str      # optional
  },
  ...
]

【输出格式】
[
  {
    "title": str,
    "link": str,
    "summary": str,
    "source": str,
    "category": str
  },
  ...
]
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')  # 强制终端输出 UTF-8
import json
import requests
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime

# ===== 配置（建议移到 config.py） =====
OLLAMA_BASE_URL = "http://localhost:11434"
# 支持 14B/32B 自动适配：用户可传 --model 参数覆盖
DEFAULT_MODEL = "qwen2.5:14b"  
TEMPERATURE = 0.1  # 筛选任务需要确定性，低温
MAX_TOKENS = 2048

def call_ollama(prompt: str, model: str = None) -> str:
    """调用本地 Ollama API，返回纯文本响应"""
    model = model or DEFAULT_MODEL
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        #"keep_alive":"-1", #模型常驻显存，防止卸载
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS
        }
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=600)  # 长任务给 2 分钟
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except Exception as e:
        print(f"❌ Ollama 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

def build_filter_prompt(news_items: List[Dict], max_items: int = 50) -> str:
    """构建 AI 筛选提示词，控制 token 用量"""
    # 截断过长列表，避免爆 token（32B 也需节制）
    items = news_items[:max_items]
    
    # 格式化输入，节省 token：用 tab 分隔字段
    news_text = "\n".join([
        f"{i+1}. [{item['title']}]({item['link']}) · {item.get('source','?')}\n   {item['summary']}"
        for i, item in enumerate(items)
    ])
    
    return f"""你是一个专业的科技资讯编辑，请严格按以下规则处理新闻：

【任务】
1. 筛选：剔除广告、软文、低信息量内容（如"震惊！"标题党）
2. 分类：将新闻分到 [🔬 科技] [💼 商业] [🎮 娱乐] [🌍 其他] 四类
3. 去重：语义相似的新闻只保留 1 条（保留信息更全的）

【输入】（共 {len(items)} 条）
{news_text}

【输出格式】（严格遵循，不要额外解释）
## 🔬 科技
- [标题](链接) · 来源 · 一句话摘要
- ...

## 💼 商业
- ...

## 🎮 娱乐
- ...

## 🌍 其他
- ...

【末尾统计】
✅ 共筛选 {len(items)}→X 条，去重 Y 条"""

def parse_ai_output(ai_response: str) -> Dict[str, List[Dict]]:
    """解析 AI 返回的 Markdown，转为结构化数据（便于后续扩展）"""
    # 简单按 ## 标题分割（生产环境可用 markdown 解析库）
    sections = ai_response.split("## ")
    result = defaultdict(list)
    
    for section in sections[1:]:  # 跳过第一个空元素
        lines = section.strip().split("\n")
        if not lines: 
            continue
        category = lines[0].strip()  # 如 "🔬 科技"
        for line in lines[1:]:
            if line.startswith("- ["):
                # 解析：- [标题](链接) · 来源 · 摘要
                try:
                    title_part, rest = line[3:].split("](", 1)
                    link, rest = rest.split(") · ", 1)
                    source, summary = rest.split(" · ", 1)
                    result[category].append({
                        "title": title_part,
                        "link": link,
                        "source": source,
                        "summary": summary,
                        "category": category
                    })
                except:
                    continue  # 解析失败跳过，保持健壮性
    return dict(result)

def flatten_filtered_articles(structured: Dict[str, List[Dict]]) -> List[Dict]:
    """将按分类分组的筛选结果转成下游 summarizer 需要的文章列表"""
    articles = []
    for category, items in structured.items():
        for item in items:
            articles.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "category": item.get("category", category),
            })
    return articles

def generate_brief_markdown(structured: Dict[str, List[Dict]]) -> str:
    """将结构化数据转为最终 Markdown 简报"""
    md = ["# 📰 Daily Brief · " + datetime.now().strftime("%Y-%m-%d"), ""]
    
    for category, items in structured.items():
        if not items:
            continue
        md.append(f"## {category}")
        for item in items:
            md.append(f"- [{item['title']}]({item['link']}) · {item['source']} · {item['summary']}")
        md.append("")
    
    total = sum(len(v) for v in structured.values())
    md.append(f"> ✅ 共筛选 {total} 条高质量资讯")
    return "\n".join(md)

# ===== 主流程 =====
def filter_news(news_items: List[Dict], model: str = None) -> List[Dict]:
    """端到端：输入原始新闻列表 → 输出筛选后的扁平文章列表"""
    if not news_items:
        return []
    
    prompt = build_filter_prompt(news_items)
    ai_response = call_ollama(prompt, model)
    structured = parse_ai_output(ai_response)
    return flatten_filtered_articles(structured)

# ===== 独立测试入口 =====
if __name__ == "__main__":
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="AI 新闻筛选器")
    parser.add_argument("--input", type=str, help="输入 JSON 文件路径（不传则读 stdin）")
    parser.add_argument("--model", type=str, help=f"模型名（默认: {DEFAULT_MODEL}）")
    parser.add_argument("--output", type=str, help="输出 Markdown 文件路径（不传则打印到 stdout）")
    args = parser.parse_args()
    
    # 1. 读取输入
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            news_items = json.load(f)
    else:
        # 从 stdin 读取（支持管道：python rss_reader.py | python ai_filter.py）
        news_items = json.load(sys.stdin)
    
    print(f"🤖 正在用 {args.model or DEFAULT_MODEL} 筛选 {len(news_items)} 条新闻...", file=sys.stderr)
    
    # 2. 调用 AI 处理
    filtered_articles = filter_news(news_items, model=args.model)
    
    # 3. 输出结果
    if args.output:
        import os
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(filtered_articles, f, ensure_ascii=False, indent=2)
        print(f"💾 简报已保存至 {args.output}", file=sys.stderr)
    else:
        print(json.dumps(filtered_articles, ensure_ascii=False, indent=2))  # 打印到 stdout
