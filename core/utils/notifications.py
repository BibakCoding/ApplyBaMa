"""
Notification utility functions for ApplyBaMa.

This module provides functions for sending automated notifications to users.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.models import Notification, NotificationRecipient

User = get_user_model()


def send_notification(user, title, message, notification_type='info', sender=None):
    """
    Send a notification to a specific user.

    Args:
        user: User instance or User ID to send notification to
        title: Notification title (str)
        message: Notification message (str)
        notification_type: Type of notification - 'info', 'warning', 'success', 'error', 'reminder'
        sender: User instance who is sending the notification (optional, defaults to system)

    Returns:
        NotificationRecipient: The created notification recipient object

    Example:
        send_notification(
            user=request.user,
            title=_("Welcome to ApplyBaMa!"),
            message=_("Thank you for registering. Here's how to get started..."),
            notification_type='success'
        )
    """
    # Validate notification type
    valid_types = ['info', 'warning', 'success', 'error', 'reminder']
    if notification_type not in valid_types:
        notification_type = 'info'

    # Get user instance if ID was passed
    if isinstance(user, int):
        user = User.objects.get(id=user)

    # Create the notification
    notification = Notification.objects.create(
        title=title,
        message=message,
        notification_type=notification_type,
        recipient_type=Notification.RecipientType.SPECIFIC_USERS,
        sender=sender,
    )

    # Link notification to user
    notification_recipient = NotificationRecipient.objects.create(
        notification=notification,
        user=user,
        is_read=False,
    )

    return notification_recipient


def send_welcome_notification(user):
    """
    Send a welcome notification to a newly registered user.

    Args:
        user: User instance to send welcome notification to

    Returns:
        NotificationRecipient: The created notification recipient object
    """
    welcome_title = _("Welcome to ApplyBaMa!")
    welcome_message = _(
        "Thank you for registering with ApplyBaMa! "
        "We're here to help you find your dream university and program. "
        "Explore our dashboard to search universities, browse programs, and start your application. "
        "If you need any assistance, feel free to contact our support team."
    )

    return send_notification(
        user=user,
        title=welcome_title,
        message=welcome_message,
        notification_type='success',
    )