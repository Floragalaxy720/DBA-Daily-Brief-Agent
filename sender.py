"""
sender.py
---------
Send the formatted DBA newsletter via SMTP.

The Markdown body is always saved locally before sending so each run leaves
a readable artifact at output/daily_brief.md.
"""

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from config import (
    EMAIL_PASSWORD,
    EMAIL_RECIPIENT,
    EMAIL_SENDER,
    EMAIL_SUBJECT,
    SMTP_HOST,
    SMTP_PORT,
)


logger = logging.getLogger(__name__)

OUTPUT_FILE = Path("output") / "daily_brief.md"


def _save_markdown(newsletter_body: str) -> Path:
    """Persist the newsletter Markdown locally before any send attempt."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(newsletter_body or "", encoding="utf-8")
    return OUTPUT_FILE


def _validate_email_config() -> None:
    """Fail early with a clear message if email settings are missing."""
    missing = [
        name
        for name, value in {
            "EMAIL_SENDER": EMAIL_SENDER,
            "EMAIL_PASSWORD": EMAIL_PASSWORD,
            "EMAIL_RECIPIENT": EMAIL_RECIPIENT,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(f"Missing email configuration: {', '.join(missing)}")


def send_email(newsletter_body: str) -> bool:
    """Save the Markdown brief locally, then send it through SMTP."""
    saved_path = _save_markdown(newsletter_body)
    logger.info(f"Newsletter saved to {saved_path}")

    try:
        _validate_email_config()

        message = EmailMessage()
        message["From"] = EMAIL_SENDER
        message["To"] = EMAIL_RECIPIENT
        message["Subject"] = EMAIL_SUBJECT
        message.set_content(newsletter_body or "")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(message)

        logger.info(f"Newsletter sent to {EMAIL_RECIPIENT}")
        return True

    except Exception:
        logger.exception("Failed to send newsletter via SMTP")
        raise
