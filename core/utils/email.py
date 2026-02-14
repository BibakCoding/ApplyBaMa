import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Set up logger
logger = logging.getLogger(__name__)


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
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logger.info("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        return False
