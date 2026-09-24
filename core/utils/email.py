import logging
import re
from contextlib import nullcontext
from html import unescape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.html import strip_tags

# Set up logger
logger = logging.getLogger(__name__)

# Removed entirely: their text content is not prose and must never reach the
# plain-text part (a <style> block would otherwise be dumped in as raw CSS).
_NON_CONTENT_RE = re.compile(
    r"<(?:style|script|head)\b[^>]*>.*?</(?:style|script|head)>|<!--.*?-->",
    re.IGNORECASE | re.DOTALL,
)
# Block boundaries become line breaks in the plain-text alternative.
_BLOCK_BOUNDARY_RE = re.compile(
    r"</(?:p|div|h[1-6]|tr|table|li|ul|ol)>|<br\s*/?>", re.IGNORECASE
)
_HORIZONTAL_SPACE_RE = re.compile(r"[ \t]+")


def _html_to_text(html_content: str) -> str:
    """Readable text/plain part: keep the layout's line breaks, drop the markup."""
    text = _NON_CONTENT_RE.sub("", html_content)
    text = _BLOCK_BOUNDARY_RE.sub("\n", text)
    text = unescape(strip_tags(text))
    lines = (_HORIZONTAL_SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def send_email(
        subject: str,
        template_name: str,
        context: dict,
        to: list[str],
        from_email: str | None = None,
) -> bool:
    try:
        logger.info("Sending email started")
        from_email = from_email or settings.DEFAULT_FROM_EMAIL

        # Render in the recipient's language. This runs in a Celery worker where
        # no request language is active, so the caller passes the language it
        # captured; without it every email would render in the default language.
        language = context.get("language")
        with (translation.override(language) if language else nullcontext()):
            html_content = render_to_string(template_name, context)
        text_content = _html_to_text(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logger.info("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        return False
