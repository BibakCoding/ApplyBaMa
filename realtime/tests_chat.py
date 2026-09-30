"""Chat WebSocket tests.

The socket is a delivery channel, not an input channel: the browser may only
send typing and read markers, and every message body is created over HTTP. The
tests below pin that contract down — an anonymous socket is refused, a read
marker round-trips into a ``chat.read`` event, and a payload that pretends to
be a message creates nothing.
"""

import asyncio

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, override_settings

from core import chat as chat_domain
from core.models import Conversation, Message, User
from realtime.chat import ChatConsumer

TEST_CHANNEL_LAYERS = {
	"default": {
		"BACKEND": "channels.layers.InMemoryChannelLayer",
	},
}


def make_users():
	admin = User.objects.create_user(
		username="sock-support",
		email="sock-support@example.com",
		password="Password123!",
		is_staff=True,
		email_verified=True,
	)
	student = User.objects.create_user(
		username="sock-student",
		email="sock-student@example.com",
		password="Password123!",
		email_verified=True,
	)
	conversation = chat_domain.get_or_create_conversation(student, admin)
	return admin, student, conversation


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ChatConsumerTests(TestCase):
	async def test_anonymous_sockets_are_rejected(self):
		communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/")

		connected, _ = await communicator.connect()

		self.assertFalse(connected)
		await communicator.disconnect()

	async def test_handshake_confirms_the_socket(self):
		_admin, student, _conversation = await database_sync_to_async(make_users)()

		communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/")
		communicator.scope["user"] = student
		connected, _ = await communicator.connect()

		self.assertTrue(connected)
		welcome = await communicator.receive_json_from()
		self.assertEqual(welcome["type"], "connection.established")
		await communicator.disconnect()

	async def test_a_read_marker_round_trips_as_a_chat_event(self):
		_admin, student, conversation = await database_sync_to_async(make_users)()
		await database_sync_to_async(chat_domain.send_message)(
			conversation, student, "hello"
		)

		communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/")
		communicator.scope["user"] = student
		await communicator.connect()
		await communicator.receive_json_from()  # connection.established

		await communicator.send_json_to(
			{"type": "chat.read", "conversation": conversation.pk}
		)

		event = await communicator.receive_json_from()
		self.assertEqual(event["type"], "chat.read")
		self.assertEqual(event["conversation"], conversation.pk)
		self.assertEqual(event["reader"], student.pk)

		await database_sync_to_async(self.assert_read_marker)(conversation, student)
		await communicator.disconnect()

	def assert_read_marker(self, conversation, student):
		reads = chat_domain.participant_reads(conversation)
		self.assertIsNotNone(reads.get(student.pk))

	async def test_message_content_over_the_socket_creates_nothing(self):
		_admin, student, conversation = await database_sync_to_async(make_users)()

		communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/")
		communicator.scope["user"] = student
		await communicator.connect()
		await communicator.receive_json_from()  # connection.established

		await communicator.send_json_to(
			{"type": "chat.message", "conversation": conversation.pk, "body": "sneaky"}
		)

		# The consumer ignores anything that is not a typing/read marker: no
		# message row, and no event echoed back to the sender.
		self.assertTrue(await communicator.receive_nothing(timeout=0.2))
		self.assertEqual(await database_sync_to_async(Message.objects.count)(), 0)
		self.assertEqual(await database_sync_to_async(Conversation.objects.count)(), 1)
		await communicator.disconnect()
