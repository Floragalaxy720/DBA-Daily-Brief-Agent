"""
rss_reader.py
━━━━━━━━━━━━
【真正职责】
  • 从配置的 RSS 源抓取最新文章
  • 提取 title / link / summary（优先用 <description>，降级用 <content> 或截断）
  • 输出标准 JSON 列表，供下游模块消费

【不负责】
  • 不调用任何 AI 模型
  • 不做去重/分类/筛选
  • 不写文件（由调用方决定输出位置）

【输出格式】（严格遵循）
[
  {
    "title": str,      # 文章标题，必填
    "link": str,       # 原文链接，必填
    "summary": str,    # 摘要，≤200 字，空字符串允许
    "published": str,  # 发布时间（ISO 8601），可选
    "source": str      # 来源域名，可选
  },
  ...
]
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')  # 强制终端输出 UTF-8
import feedparser
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

# 配置建议移到 config.py，这里写默认值便于独立测试
DEFAULT_RSS_FEEDS = [
    "https://hnrss.org/frontpage",          # Hacker News
    "https://feeds.arstechnica.com/arstechnica/index",  # Ars Technica
    "https://www.theverge.com/rss/index.xml",  # The Verge
    # 添加你的自定义源...
]

def clean_text(text: str, max_len: int = 200) -> str:
    """移除 HTML 标签 + 截断 + 清理空白"""
    if not text:
        return ""
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 移除多余空白
    text = ' '.join(text.split())
    # 截断（避免切词）
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + '...'
    return text.strip()

def extract_domain(url: str) -> str:
    """从 URL 提取域名，如 'https://example.com/path' → 'example.com'"""
    try:
        return urlparse(url).netloc
    except:
        return ""

def fetch_rss_feed(feed_url: str, max_entries: int = 10) -> List[Dict]:
    """抓取单个 RSS 源，返回标准化条目列表"""
    feed = feedparser.parse(feed_url)
    results = []
    
    for entry in feed.entries[:max_entries]:
        # 优先取 summary，其次 description，最后 content
        summary = (
            getattr(entry, 'summary', '') or 
            getattr(entry, 'description', '') or 
            (entry.content[0].value if hasattr(entry, 'content') and entry.content else '')
        )
        
        item = {
            "title": getattr(entry, 'title', 'No Title'),
            "link": getattr(entry, 'link', ''),
            "summary": clean_text(summary),
            "published": getattr(entry, 'published_parsed', None),
            "source": extract_domain(getattr(entry, 'link', ''))
        }
        # 转换时间戳为 ISO 格式
        if item["published"]:
            item["published"] = datetime(*item["published"][:6]).isoformat()
        else:
            item.pop("published")  # 无时间则删除字段
            
        results.append(item)
    
    return results

def fetch_all_feeds(feeds: List[str] = None, max_per_feed: int = 10) -> List[Dict]:
    """抓取所有配置的源，合并结果（保留 source 字段便于溯源）"""
    if feeds is None:
        feeds = DEFAULT_RSS_FEEDS
    
    all_items = []
    for feed_url in feeds:
        try:
            items = fetch_rss_feed(feed_url, max_per_feed)
            all_items.extend(items)
        except Exception as e:
            print(f"⚠️ 抓取 {feed_url} 失败: {e}")
            continue
    
    # 按发布时间倒序（新的在前）
    all_items.sort(
        key=lambda x: x.get('published', ''), 
        reverse=True
    )
    return all_items

# ===== 独立测试入口 =====
if __name__ == "__main__":
    import json
    import sys
    
    print("📡 正在抓取 RSS...")
    results = fetch_all_feeds(max_per_feed=5)  # 测试时少抓点
    print(f"✅ 抓取完成，共 {len(results)} 条")
    
    # 输出到 stdout（便于管道传递）或文件
    output_path = "output/raw_news.json"
    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        import os
        os.makedirs("output", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存至 {output_path}")
    else:
        # 直接打印 JSON，供 ai_filter.py 通过 subprocess 读取
        print(json.dumps(results, ensure_ascii=False, indent=2))