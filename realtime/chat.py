# realtime/chat.py
"""
Chat WebSocket consumer for ApplyBaMa (/ws/chat/).

Design: messages are *created* over HTTP (the dashboard endpoints validate,
upload files through Django's normal pipeline and enforce CSRF). This socket is
the delivery and low-state channel:

* the browser sends only typing and read markers — no message content ever
  crosses the socket, so nothing here can bypass view-level authorization;
* the server pushes every chat event on the conversations the user takes part
  in (new message, read, edit, delete, pin, presence, typing).

Rate limiting: a sliding window over the lightweight client events, so a
malicious client cannot flood the layer. Overage is dropped silently — the
socket stays open, the sender just stops being amplified.

Presence: connect flips the participant rows' ``is_online`` on, disconnect
turns it off, and peers get one ``chat.presence`` push either way.
"""

import logging
import time

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from .push import push_to_user

logger = logging.getLogger(__name__)

CHAT_WS_PATH = "ws/chat/"

# Client events per second allowed before the rest of the window is dropped.
# Typing throttles client-side too; this bound exists for hostile clients.
RATE_LIMIT_EVENTS = 20
RATE_LIMIT_WINDOW = 10.0


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """One open browser tab of one logged-in user."""

    async def connect(self):
        user = self.scope.get("user")
        if not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        self.user = user
        self.group_name = f"chat.user.{user.pk}"
        # Sliding-window rate limiter state for receive().
        self.event_times = []
        # Set while this tab has a conversation open, so typing is only
        # amplified for the thread the user is actually looking at.
        self.active_conversation_id = None

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connection.established"})
        # Presence on: peers' conversation lists update live.
        await self.set_presence(True)

    async def disconnect(self, code):
        if hasattr(self, "user"):
            try:
                await self.set_presence(False)
            except Exception:
                logger.warning("chat: presence cleanup failed", exc_info=True)
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Client → server: only typing markers and read markers.

        Message content is deliberately NOT accepted here — it would bypass
        the upload pipeline and the authorization the HTTP endpoints run.
        """
        if not self._rate_ok():
            return

        kind = content.get("type")

        if kind == "chat.typing":
            conversation_id = content.get("conversation")
            if isinstance(conversation_id, int):
                # One typing flag per tab; switching threads clears the old one.
                await self.set_typing(conversation_id, self.active_conversation_id, False)
                self.active_conversation_id = conversation_id
                await self.set_typing(conversation_id, None, True)

        elif kind == "chat.read":
            conversation_id = content.get("conversation")
            if isinstance(conversation_id, int):
                await self.handle_read(conversation_id)

    def _rate_ok(self):
        """Sliding window: keep at most RATE_LIMIT_EVENTS per window."""
        now = time.monotonic()
        self.event_times = [t for t in self.event_times if now - t < RATE_LIMIT_WINDOW]
        if len(self.event_times) >= RATE_LIMIT_EVENTS:
            return False
        self.event_times.append(now)
        return True

    # ------------------------------------------------------------------
    # Database work (sync ORM behind database_sync_to_async)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def set_presence(self, online):
        from core import chat

        peer_ids = chat.peers_of(self.user)
        chat.set_presence(self.user, online)
        for peer_id in peer_ids:
            push_to_user(
                peer_id,
                {"type": "chat.presence", "user": self.user.pk, "online": online},
            )

    @database_sync_to_async
    def set_typing(self, conversation_id, previous_id, typing):
        from django.db.models import Q

        from core.models import Conversation, ConversationParticipant
        from core import chat

        try:
            conversation = Conversation.objects.get(pk=conversation_id)
        except Conversation.DoesNotExist:
            return
        if not conversation.is_participant(self.user):
            return

        # Switching threads: clear the flag on the thread being left so the
        # peer there does not see a stuck "typing…".
        if isinstance(previous_id, int) and previous_id != conversation_id:
            ConversationParticipant.objects.filter(
                Q(conversation_id=previous_id) & Q(user=self.user) & Q(is_typing=True)
            ).update(is_typing=False)

        marker, _created = ConversationParticipant.objects.get_or_create(
            conversation=conversation, user=self.user
        )
        if marker.is_typing != typing:
            marker.is_typing = typing
            marker.save(update_fields=["is_typing"])
        if typing:
            push_to_user(
                conversation.partner_of(self.user).pk,
                {"type": "chat.typing", "conversation": conversation_id, "typing": True},
            )

    @database_sync_to_async
    def handle_read(self, conversation_id):
        """Record the read and push the receipt to both sides."""
        from core.models import Conversation
        from core import chat

        try:
            conversation = Conversation.objects.get(pk=conversation_id)
        except Conversation.DoesNotExist:
            return
        if not conversation.is_participant(self.user):
            return

        previous = chat.mark_conversation_read(conversation, self.user)
        reads = chat.participant_reads(conversation)
        payload = {
            "type": "chat.read",
            "conversation": conversation_id,
            "reader": self.user.pk,
            "last_read_at": reads.get(self.user.pk).isoformat() if reads.get(self.user.pk) else None,
            "unread_total": chat.total_unread_for(self.user),
        }
        # Both participants care: the reader's other tabs clear the badge,
        # the peer's ticks flip to double.
        for participant in conversation.both_users():
            push_to_user(participant.pk, payload)

    # ------------------------------------------------------------------
    # Group event handlers: pushed by realtime.push.push_to_user with
    # {"type": "chat.event"} — dispatched here by Channels' naming.
    # ------------------------------------------------------------------

    async def chat_event(self, event):
        payload = event.get("payload") or {}
        try:
            await self.send_json(payload)
        except Exception:  # pragma: no cover - transport already failing
            logger.debug("chat: send failed on %s", self.channel_name)

    async def send_json(self, content, close=False):
        try:
            await super().send_json(content, close=close)
        except Exception:
            logger.debug("chat: send failed on %s", self.channel_name)
