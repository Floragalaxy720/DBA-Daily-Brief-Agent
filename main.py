"""
main.py
-------
Responsibility: Orchestrate the entire DBA pipeline from start to finish.

Pipeline flow:
    rss_reader      → fetch raw articles from RSS feeds
    ai_filter       → keep only relevant articles (via local Qwen14B)
    ai_summarizer   → generate insightful summaries (via Claude API)
    formatter       → build the email newsletter layout
    sender          → send the final email via Gmail SMTP

Design principles:
    - Each step is a clearly named function call
    - Failures in one step do not crash the whole pipeline
    - Easy to comment out any step for testing
    - Extensible: future steps (ranking, trends) slot in naturally

Future scaling points are marked with: # [FUTURE: ...]
"""

import logging
import sys
from datetime import datetime

# ── Pipeline modules ──────────────────────────────────────────────────────────
from rss_reader import fetch_all_feeds
from ai_filter import filter_news
from ai_summarizer import summarize_articles
from formatter import format_newsletter
from sender import send_email

# ── Config ────────────────────────────────────────────────────────────────────
from config import (
    LOG_LEVEL,
    LOG_FORMAT,
    MIN_ARTICLES_TO_SEND,   # Don't send if too few articles passed filtering
    PIPELINE_NAME,
)


# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────

def setup_logging():
    """
    Configure logging for the entire application.

    - INFO and above goes to console (stdout)
    - Makes each module's logger visible with its name

    To see debug messages, set LOG_LEVEL = "DEBUG" in config.py
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
            # [FUTURE: add FileHandler here to write logs to a file]
        ],
    )

# Get this module's logger (named "main")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PIPELINE STEPS
# ─────────────────────────────────────────────

def step_fetch(feed_urls: list[str]) -> list[dict]:
    """
    Step 1: Fetch raw articles from all RSS feeds.

    Returns empty list on failure so pipeline can still continue
    or exit gracefully (handled in run_pipeline).
    """
    logger.info("── STEP 1: Fetching RSS feeds ──")
    try:
        articles = fetch_all_feeds(feed_urls)
        logger.info(f"Fetched {len(articles)} raw articles.")
        return articles
    except Exception as e:
        logger.error(f"RSS fetch failed: {e}")
        return []


def step_filter(articles: list[dict]) -> list[dict]:
    """
    Step 2: Filter articles using local Qwen14B model.
    Keeps only AI/tech/business articles worth reading.

    Returns empty list on failure.
    """
    logger.info("── STEP 2: Filtering articles ──")
    try:
        filtered = filter_news(articles)
        logger.info(f"Filtered down to {len(filtered)} relevant articles.")
        return filtered
    except Exception as e:
        logger.error(f"Filtering failed: {e}")
        return []


def step_summarize(articles: list[dict]) -> list[dict]:
    """
    Step 3: Summarize articles using Claude API.
    Generates KEY EVENT / WHY IT MATTERS / IMPACT for each article.

    Returns empty list on failure.
    """
    logger.info("── STEP 3: Summarizing articles ──")
    try:
        summarized = summarize_articles(articles)
        logger.info(f"Successfully summarized {len(summarized)} articles.")
        return summarized
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return []


def step_format(articles: list[dict]) -> str | None:
    """
    Step 4: Format articles into a newsletter-ready email body (HTML or plain text).

    Returns None on failure.
    """
    logger.info("── STEP 4: Formatting newsletter ──")
    try:
        newsletter_body = format_newsletter(articles)
        logger.info("Newsletter formatted successfully.")
        return newsletter_body
    except Exception as e:
        logger.error(f"Formatting failed: {e}")
        return None


def step_send(newsletter_body: str) -> bool:
    """
    Step 5: Send the formatted newsletter via Gmail SMTP.

    Returns True if sent successfully, False otherwise.
    """
    logger.info("── STEP 5: Sending email ──")
    try:
        send_email(newsletter_body)
        logger.info("Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


# ─────────────────────────────────────────────
# MAIN PIPELINE ORCHESTRATOR
# ─────────────────────────────────────────────

def run_pipeline(feed_urls: list[str]) -> dict:
    """
    Run the full DBA pipeline end-to-end.

    Args:
        feed_urls: List of RSS feed URLs to pull from (defined in config.py)

    Returns:
        A result summary dict — useful for logging, monitoring, or future webhooks.
        {
            "status": "success" | "failed" | "skipped",
            "articles_fetched": int,
            "articles_filtered": int,
            "articles_summarized": int,
            "email_sent": bool,
            "run_at": str (ISO timestamp),
            "error": str | None
        }
    """
    run_at = datetime.now().isoformat()
    logger.info(f"\n{'='*60}")
    logger.info(f"  {PIPELINE_NAME} — Run started at {run_at}")
    logger.info(f"{'='*60}\n")

    result = {
        "status": "failed",
        "articles_fetched": 0,
        "articles_filtered": 0,
        "articles_summarized": 0,
        "email_sent": False,
        "run_at": run_at,
        "error": None,
    }

    # ── Step 1: Fetch ─────────────────────────────────────────────────────────
    raw_articles = step_fetch(feed_urls)
    result["articles_fetched"] = len(raw_articles)

    if not raw_articles:
        result["status"] = "failed"
        result["error"] = "No articles fetched. Check RSS feed URLs or internet connection."
        logger.error(result["error"])
        return result

    # ── Step 2: Filter ────────────────────────────────────────────────────────
    filtered_articles = step_filter(raw_articles)
    result["articles_filtered"] = len(filtered_articles)

    if not filtered_articles:
        result["status"] = "skipped"
        result["error"] = "No articles passed the filter. Nothing to send today."
        logger.warning(result["error"])
        return result

    # [FUTURE: Step 2.5 — Rank articles by importance score here]
    # ranked_articles = rank_articles(filtered_articles)

    # ── Step 3: Summarize ─────────────────────────────────────────────────────
    summarized_articles = step_summarize(filtered_articles)
    result["articles_summarized"] = len(summarized_articles)

    if len(summarized_articles) < MIN_ARTICLES_TO_SEND:
        result["status"] = "skipped"
        result["error"] = (
            f"Only {len(summarized_articles)} articles summarized — "
            f"below minimum threshold of {MIN_ARTICLES_TO_SEND}. Not sending."
        )
        logger.warning(result["error"])
        return result

    # [FUTURE: Step 3.5 — Trend analysis / topic clustering here]
    # trend_data = analyze_trends(summarized_articles)

    # ── Step 4: Format ────────────────────────────────────────────────────────
    newsletter_body = step_format(summarized_articles)

    if not newsletter_body:
        result["status"] = "failed"
        result["error"] = "Newsletter formatting failed. Cannot send empty email."
        logger.error(result["error"])
        return result

    # ── Step 5: Send ──────────────────────────────────────────────────────────
    sent = step_send(newsletter_body)
    result["email_sent"] = sent
    result["status"] = "success" if sent else "failed"

    if not sent:
        result["error"] = "Email sending failed. See logs for SMTP error details."

    # ── Final summary log ──────────────────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"  Pipeline complete — Status: {result['status'].upper()}")
    logger.info(f"  Fetched: {result['articles_fetched']}  |  "
                f"Filtered: {result['articles_filtered']}  |  "
                f"Summarized: {result['articles_summarized']}  |  "
                f"Sent: {result['email_sent']}")
    if result["error"]:
        logger.warning(f"  Note: {result['error']}")
    logger.info(f"{'='*60}\n")

    return result


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # 1. Set up logging first — so all modules can log from the start
    setup_logging()

    # 2. Load RSS feed URLs from config
    #    (Define RSS_FEEDS list in config.py)
    from config import RSS_FEEDS

    # 3. Run the pipeline
    final_result = run_pipeline(RSS_FEEDS)

    # 4. Exit with error code if pipeline failed
    #    (Useful when running as a cron job — scheduler can detect failures)
    if final_result["status"] == "failed":
        sys.exit(1)
    else:
        sys.exit(0)
