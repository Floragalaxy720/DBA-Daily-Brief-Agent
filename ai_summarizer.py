"""
ai_summarizer.py
----------------
Responsibility: Take filtered articles and generate concise, insightful summaries
                via OpenRouter (using OpenAI-compatible client).

Input:  List of filtered article dicts
        [{"title": ..., "link": ..., "summary": ..., "source": ...}, ...]

Output: Same list with summary fields added to each article
        [
            {
                "title": ...,
                "link": ...,
                "source": ...,
                "english_summary": ...,
                "chinese_summary": ...,
                "ai_summary": ...
            },
            ...
        ]

Tone:   Morning Brew / business brief style
        - Sharp, readable, information-dense
        - Not robotic or academic

API:    OpenRouter (https://openrouter.ai/api/v1)
        Uses OpenAI-compatible client — same code structure as OpenAI,
        just pointed at a different base_url with your OpenRouter key.
"""

import os
import time
import logging
from openai import OpenAI, RateLimitError, APIStatusError

from config import (
    OPENROUTER_MODEL,
    SUMMARIZER_MAX_TOKENS,
    SUMMARIZER_BATCH_SIZE,
    SUMMARIZER_RETRY_ATTEMPTS,
    SUMMARIZER_RETRY_DELAY,
)

# Set up logger for this module
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# OPENROUTER CLIENT
# ─────────────────────────────────────────────

def _create_client() -> OpenAI:
    """
    Create an OpenAI-compatible client pointed at OpenRouter.

    Why does this work?
        OpenRouter exposes the same API interface as OpenAI.
        The OpenAI Python library just needs a different base_url and API key.
        No special SDK needed — works out of the box.

    The API key is read from your .env file:
        OPENROUTER_API_KEY=sk-or-...
    """
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not found. "
            "Make sure it's set in your .env file and dotenv is loaded."
        )

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


# ─────────────────────────────────────────────
# CORE PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a sharp, insightful tech and business news editor
writing for a daily AI/business newsletter (think Morning Brew meets AI Insider).

Your job: Read a raw article snippet and write a 3-part mini-brief in both
English and Simplified Chinese.

Format your response EXACTLY like this (use these exact labels):

ENGLISH SUMMARY:
KEY EVENT: [One crisp sentence — what happened]
WHY IT MATTERS: [One or two sentences — the real significance]
IMPACT: [One sentence — what to watch for next]

CHINESE SUMMARY:
KEY EVENT: [用简体中文写一句话说明发生了什么]
WHY IT MATTERS: [用简体中文写一到两句话说明真正重要性]
IMPACT: [用简体中文写一句话说明后续值得关注什么]

Rules:
- Be direct and confident. No fluff.
- Avoid phrases like "In conclusion" or "It is worth noting"
- Write like you're briefing a smart, busy professional
- Keep each language concise
- Do NOT repeat the article title
- Chinese must be Simplified Chinese
"""


def _build_user_prompt(article: dict) -> str:
    """
    Build the user message for a single article.
    Combines title + raw summary snippet for the model to work with.
    """
    title   = article.get("title",   "Untitled")
    snippet = article.get("summary", "No content available.")
    source  = article.get("source",  "Unknown Source")

    return f"""Source: {source}
Title: {title}
Content: {snippet}

Write the bilingual 3-part brief now:"""


def _split_bilingual_summary(ai_response: str) -> tuple[str | None, str | None]:
    """Split the model response into English and Simplified Chinese summaries."""
    english_marker = "ENGLISH SUMMARY:"
    chinese_marker = "CHINESE SUMMARY:"

    if english_marker not in ai_response or chinese_marker not in ai_response:
        return ai_response.strip() or None, None

    english_start = ai_response.index(english_marker) + len(english_marker)
    chinese_start = ai_response.index(chinese_marker)

    english_summary = ai_response[english_start:chinese_start].strip()
    chinese_summary = ai_response[chinese_start + len(chinese_marker):].strip()

    return english_summary or None, chinese_summary or None


# ─────────────────────────────────────────────
# SINGLE ARTICLE SUMMARIZER
# ─────────────────────────────────────────────

def summarize_article(client: OpenAI, article: dict) -> dict:
    """
    Summarize a single article using the OpenRouter API.

    Args:
        client:  OpenAI-compatible client pointed at OpenRouter (reused across calls)
        article: Dict with keys: title, link, summary, source

    Returns:
        Article dict with "english_summary" and "chinese_summary" fields added.
        If summarization fails after all retries, summary fields are None.

    How the API call works:
        client.chat.completions.create() sends a chat-style request.
        - "system" message = the standing instructions (tone, format rules)
        - "user"   message = the actual article content to summarize
        This is identical to how you'd call OpenAI — OpenRouter uses the same format.
    """
    title = article.get("title", "Untitled")

    for attempt in range(1, SUMMARIZER_RETRY_ATTEMPTS + 1):
        try:
            logger.debug(f"Summarizing: '{title}' (attempt {attempt})")

            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                max_tokens=SUMMARIZER_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": _build_user_prompt(article)},
                ],
            )

            # Extract the text from the response
            # response.choices[0].message.content is the standard OpenAI response path
            ai_response = response.choices[0].message.content.strip()
            english_summary, chinese_summary = _split_bilingual_summary(ai_response)

            logger.info(f"✓ Summarized: '{title}'")

            return {
                **article,
                "english_summary": english_summary,
                "chinese_summary": chinese_summary,
                # Keep the legacy field so current downstream formatters still work.
                "ai_summary": english_summary,
            }

        except RateLimitError:
            # Hit API rate limit — back off and wait longer each retry
            wait_time = SUMMARIZER_RETRY_DELAY * attempt
            logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

        except APIStatusError as e:
            # API returned an HTTP error (e.g. 500 server error, 529 overloaded)
            logger.error(f"API error on '{title}': {e.status_code} — {e.message}")
            if attempt < SUMMARIZER_RETRY_ATTEMPTS:
                time.sleep(SUMMARIZER_RETRY_DELAY)
            else:
                break  # Give up after max retries

        except Exception as e:
            # Catch-all for unexpected errors (network timeout, JSON parse, etc.)
            logger.error(f"Unexpected error summarizing '{title}': {e}")
            break

    # All retries exhausted — return article with summary fields set to None
    logger.warning(f"✗ Failed to summarize: '{title}'. Will be excluded from newsletter.")
    return {
        **article,
        "english_summary": None,
        "chinese_summary": None,
        "ai_summary": None,
    }


# ─────────────────────────────────────────────
# BATCH SUMMARIZER (main entry point)
# ─────────────────────────────────────────────

def summarize_articles(articles: list[dict]) -> list[dict]:
    """
    Summarize a list of articles in batches.

    Why batches?
        - Prevents hammering the API with all requests at once
        - Easier to debug — you can see which batch failed
        - Natural place to add rate-limit pauses between groups

    Args:
        articles: List of filtered article dicts from ai_filter.py

    Returns:
        List of articles that were successfully summarized.
        Articles that failed are excluded from the output.
    """
    if not articles:
        logger.warning("summarize_articles() received an empty list. Nothing to summarize.")
        return []

    logger.info(f"Starting summarization of {len(articles)} articles via OpenRouter...")

    # Create the client once — reused for every API call in this run
    try:
        client = _create_client()
    except EnvironmentError as e:
        logger.error(f"Cannot create OpenRouter client: {e}")
        return []

    summarized    = []
    total         = len(articles)
    total_batches = (total + SUMMARIZER_BATCH_SIZE - 1) // SUMMARIZER_BATCH_SIZE

    for batch_start in range(0, total, SUMMARIZER_BATCH_SIZE):
        batch     = articles[batch_start : batch_start + SUMMARIZER_BATCH_SIZE]
        batch_num = (batch_start // SUMMARIZER_BATCH_SIZE) + 1

        logger.info(f"Batch {batch_num}/{total_batches} — processing {len(batch)} articles...")

        for article in batch:
            result = summarize_article(client, article)

            # Only keep articles where bilingual summarization produced content.
            if result.get("english_summary") and result.get("chinese_summary"):
                summarized.append(result)

        # Short pause between batches — polite to the API, helps avoid rate limits
        if batch_start + SUMMARIZER_BATCH_SIZE < total:
            logger.debug(f"Batch {batch_num} done. Pausing 1s before next batch...")
            time.sleep(1)

    logger.info(
        f"Summarization complete: {len(summarized)}/{total} articles successful."
    )
    return summarized


# ─────────────────────────────────────────────
# QUICK TEST — run this file directly to verify
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Load .env so OPENROUTER_API_KEY is available when running this file directly
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Fake articles — no RSS feed needed for this test
    test_articles = [
        {
            "title": "OpenAI Releases GPT-5 with Reasoning Improvements",
            "link": "https://example.com/gpt5",
            "summary": (
                "OpenAI has announced GPT-5, claiming significant improvements in "
                "multi-step reasoning and coding tasks. The model is available via API "
                "and reportedly costs 3x less than GPT-4 Turbo at equivalent performance."
            ),
            "source": "TechCrunch",
        },
        {
            "title": "Anthropic Raises $2B Series D at $18B Valuation",
            "link": "https://example.com/anthropic",
            "summary": (
                "Anthropic secured $2 billion in new funding led by Google, pushing "
                "its valuation to $18 billion. The funds will go toward model safety "
                "research and expanding Claude's enterprise features."
            ),
            "source": "The Verge",
        },
    ]

    results = summarize_articles(test_articles)

    print("\n" + "=" * 60)
    for r in results:
        print(f"\n📰 {r['title']}")
        print(f"   Source: {r['source']}")
        print(f"\nEnglish:\n{r['english_summary']}")
        print(f"\nChinese:\n{r['chinese_summary']}")
        print("-" * 60)
