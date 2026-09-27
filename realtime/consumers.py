# realtime/consumers.py
"""
WebSocket consumers for ApplyBaMa's realtime features.

The consumer is deliberately generic: it authenticates the visitor through the
session middleware, groups them under ``notify.user.<id>`` and relays the group
messages through. What the messages mean (a new platform notification today, a
chat message tomorrow) is decided by the producers, not by this file.

Both handlers never raise: a broken socket must degrade into the previous
behaviour (no realtime, the page still works), not take the connection or the
server down.
"""

import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)

# Single source of truth for the group-name scheme. Producers push with
# realtime.push.notify_user(); consumers subscribe here.
NOTIFY_GROUP_TEMPLATE = "notify.user.{user_id}"


class NotifyConsumer(AsyncJsonWebsocketConsumer):
    """A per-user, server-pushed event stream.

    Scope: ``/ws/notify/`` (see realtime/routing.py).

    Messages pushed to the user's group arrive as JSON and are forwarded
    verbatim: ``{"type": "notification.new", ...}`` from the notification
    producers. Other producers can push their own ``type`` values on the same
    group once chat lands.
    """

    async def connect(self):
        user = self.scope.get("user")

        # Anonymous visitors get no stream at all: there is nothing private to
        # deliver, and keeping the socket open would just leak a group name.
        if not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        self.group_name = NOTIFY_GROUP_TEMPLATE.format(user_id=user.pk)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # First payload after the handshake so a page can sync state it missed
        # while the socket was down (see static/js/realtime.js).
        await self.send_json({"type": "connection.established"})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # One-way stream: clients never send application messages. Anything
        # arriving here is either a stray frame or a bug on the other end.
        await self.send_json({"type": "error.unsupported", "received": True})

    # ------------------------------------------------------------------
    # Group event handlers. channel_layer.group_send({"type": "notify.event"})
    # is dispatched to notify_event below by Channels' naming convention.
    # ------------------------------------------------------------------
    async def notify_event(self, event):
        payload = event.get("payload") or {}
        # Never let one malformed payload kill the socket: log and keep the
        # connection alive instead.
        try:
            await self.send_json(payload)
        except Exception:  # pragma: no cover - transport already failing
            logger.warning("realtime: failed to deliver payload to %s", self.channel_name)

    async def send_json(self, content, close=False):
        try:
            await super().send_json(content, close=close)
        except Exception:
            # The browser may have gone away mid-send; that must not bubble
            # into server errors for what is a best-effort stream.
            logger.debug("realtime: send failed on %s", self.channel_name)
