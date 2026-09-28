# realtime/push.py
"""
Server → browser push helpers.

Every producer of a realtime event calls exactly one entry point:
``notify_user``. It is safe to call from sync code (Django views, admin
actions, Celery tasks, signals) and from async code alike — it never raises,
because a failed push must degrade into "the user refreshes like before", not
a 500 in the producer's request.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def unread_counts_for_users(user_ids):
    """Return ``{user_id: unread_total}`` for the given user ids.

    One aggregate query instead of one per user; producers attach the result
    to their events so the browser can move the unread badge without a
    round-trip. Users with zero unread are simply absent from the mapping.
    """
    from django.db.models import Count

    from core.models import NotificationRecipient

    user_ids = list(user_ids)
    if not user_ids:
        return {}
    rows = NotificationRecipient.objects.filter(
        user_id__in=user_ids, is_read=False
    ).values("user_id").annotate(unread=Count("id"))
    return {row["user_id"]: row["unread"] for row in rows}


def notify_user(user_id, payload, type="notification.new"):
    """Push a realtime event to one user's open sockets.

    Args:
        user_id: primary key of the target user.
        payload: dict with the event data (already JSON-serializable).
        type: the event ``type`` the browser listens for. The notification
            producers use ``notification.new``; chat will introduce its own.

    The payload is nested under ``payload`` so the consumer can add envelope
    fields later (ids, timestamps) without breaking clients.
    """
    try:
        layer = get_channel_layer()
        if layer is None:
            # No channel layer configured: realtime is off. Not an error —
            # plain requests still work exactly as before.
            return
        async_to_sync(layer.group_send)(
            f"notify.user.{user_id}",
            {"type": "notify.event", "payload": {"type": type, **payload}},
        )
    except Exception:
        # A push must never take the request that produced it down.
        logger.warning("realtime: push to user %s failed", user_id, exc_info=True)
