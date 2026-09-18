"""
formatter.py
------------
DBA v1.0 Newsletter Formatter.

This module only formats article data into Markdown. It does not fetch data,
filter news, summarize content, or call any external API.
"""

from datetime import datetime


def _value(article: dict, key: str, default: str = "N/A") -> str:
    """Return a readable string value for optional article fields."""
    value = article.get(key)
    if value is None or value == "":
        return default
    return str(value).strip()


def format_newsletter(articles: list[dict]) -> str:
    """Format summarized articles into a Markdown daily brief."""
    today = datetime.now().strftime("%Y-%m-%d")
    total = len(articles)

    lines = [
        "# DBA Daily Brief",
        "",
        f"**Date:** {today}",
        f"**News Count:** {total}",
        "",
        "---",
        "",
    ]

    if not articles:
        lines.append("No qualified news today.")
        return "\n".join(lines)

    for index, article in enumerate(articles, start=1):
        title = _value(article, "title", "Untitled")
        category = _value(article, "category")
        chinese_summary = _value(article, "summary")
        english_summary = _value(article, "ai_summary")
        source = _value(article, "source")
        published = _value(article, "published")
        link = _value(article, "link")

        lines.extend([
            f"## {index}. {title}",
            "",
            f"**Category:** {category}",
            "",
            chinese_summary,
            "",
            "**English Summary**",
            "",
            english_summary,
            "",
            f"**Source:** {source}",
            f"**Published:** {published}",
            f"**Original Link:** {link}",
            "",
            "---",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"

