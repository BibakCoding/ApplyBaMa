"""
Tests for the realtime WebSocket infrastructure.

The communication contract is tested at two levels:

* end-to-end: a browser connects to /ws/notify/, a producer calls
  realtime.push.notify_user(), and the browser receives the event;
* unit-level: the push helper swallows its failures, because a broken
  push must degrade to "no realtime", never to a 500 in the request.
"""

import asyncio
import functools

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from realtime.consumers import NotifyConsumer
from realtime.push import notify_user

User = get_user_model()

# The InMemory channel layer keeps its queues in asyncio structures, so the
# tests drive the layer from one event loop (Django's async-capable TestCase).
TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class NotifyConsumerTests(TestCase):
    """End-to-end: socket handshake, auth gate, and event delivery."""

    async def test_anonymous_user_is_rejected(self):
        communicator = WebsocketCommunicator(NotifyConsumer.as_asgi(), "/ws/notify/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_authenticated_user_receives_pushed_notification(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username="sockuser", password="x"
        )
        communicator = WebsocketCommunicator(NotifyConsumer.as_asgi(), "/ws/notify/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Handshake confirmation arrives first.
        welcome = await communicator.receive_json_from()
        self.assertEqual(welcome["type"], "connection.established")

        # A producer push reaches the socket through the channel layer.
        # notify_user is sync code, exactly like the views/admin/tasks that
        # call it in production: it runs in a worker thread here.
        await asyncio.get_running_loop().run_in_executor(
            None,
            functools.partial(
                notify_user,
                user.pk,
                {
                    "id": 1,
                    "title": "Hello",
                    "message": "Realtime works",
                    "notification_type": "info",
                    "unread_count": 3,
                },
            ),
        )
        event = await communicator.receive_json_from()
        self.assertEqual(event["type"], "notification.new")
        self.assertEqual(event["title"], "Hello")
        self.assertEqual(event["unread_count"], 3)

        await communicator.disconnect()

    async def test_other_users_do_not_receive_the_event(self):
        sender_target = await database_sync_to_async(User.objects.create_user)(
            username="target", password="x"
        )
        outsider = await database_sync_to_async(User.objects.create_user)(
            username="outsider", password="x"
        )

        target_sock = WebsocketCommunicator(NotifyConsumer.as_asgi(), "/ws/notify/")
        target_sock.scope["user"] = sender_target
        outsider_sock = WebsocketCommunicator(NotifyConsumer.as_asgi(), "/ws/notify/")
        outsider_sock.scope["user"] = outsider
        await target_sock.connect()
        await outsider_sock.connect()
        await target_sock.receive_json_from()  # connection.established
        await outsider_sock.receive_json_from()

        await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(notify_user, sender_target.pk, {"title": "private"})
        )

        event = await target_sock.receive_json_from()
        self.assertEqual(event["title"], "private")

        # The outsider must have received nothing beyond the handshake.
        self.assertTrue(await outsider_sock.receive_nothing(timeout=0.3))

        await target_sock.disconnect()
        await outsider_sock.disconnect()


class NotifyPushHelperTests(TestCase):
    """The push helper degrades silently; producers never see an error."""

    def test_push_without_channel_layer_does_not_raise(self):
        # With no CHANNEL_LAYERS configured, get_channel_layer() raises —
        # notify_user must swallow that (realtime off => business as usual).
        from django.test import override_settings as _ov

        with _ov(CHANNEL_LAYERS={}):
            notify_user(1, {"title": "nobody is listening"})

    def test_push_with_broken_layer_does_not_raise(self):
        class BrokenLayer:
            def group_send(self, *args, **kwargs):
                raise RuntimeError("layer is down")

        from unittest import mock

        with mock.patch("channels.layers.get_channel_layer", return_value=BrokenLayer()):
            notify_user(1, {"title": "boom"})
