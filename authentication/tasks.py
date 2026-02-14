from celery import shared_task
from core.utils.email import send_email


@shared_task
def send_async_email(subject, template_name, context, to):
    send_email(subject, template_name, context, to)
