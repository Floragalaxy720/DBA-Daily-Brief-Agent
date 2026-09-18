"""
config.py
---------
Central configuration for DBA - Daily Brief Agent.

All tuneable settings live here. No magic numbers scattered across files.
Sensitive values (API keys, passwords) are loaded from .env via python-dotenv.
"""

import os
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()


# ─────────────────────────────────────────────
# PIPELINE IDENTITY
# ─────────────────────────────────────────────

PIPELINE_NAME = "DBA - Daily Brief Agent"


# ─────────────────────────────────────────────
# RSS FEEDS
# ─────────────────────────────────────────────

RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://venturebeat.com/feed/",
    # Add more feeds here as needed
]


# ─────────────────────────────────────────────
# OPENROUTER API (ai_summarizer.py)
# ─────────────────────────────────────────────

OPENROUTER_MODEL       = "anthropic/claude-sonnet-4"  # Model to use for summarization
SUMMARIZER_MAX_TOKENS  = 300    # Max tokens per summary (keep summaries tight)
SUMMARIZER_BATCH_SIZE  = 5      # Articles per batch (avoid rate limits)
SUMMARIZER_RETRY_ATTEMPTS = 3   # How many times to retry a failed API call
SUMMARIZER_RETRY_DELAY    = 5   # Seconds to wait between retries


# ─────────────────────────────────────────────
# PIPELINE THRESHOLDS
# ─────────────────────────────────────────────

MIN_ARTICLES_TO_SEND = 3   # Don't send newsletter if fewer than this many articles


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

LOG_LEVEL  = "INFO"   # Change to "DEBUG" to see verbose output
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"


# ─────────────────────────────────────────────
# EMAIL (sender.py — fill in later)
# ─────────────────────────────────────────────

EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")      # Your Gmail address
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")    # Gmail App Password (not your login password)
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")   # Who receives the brief
EMAIL_SUBJECT   = f"📰 {PIPELINE_NAME} — Daily Brief"
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
