"""Chat tests: permissions, read receipts, soft delete and upload policy.

The chat framework is closed by design, so the tests that matter most are the
negative ones: who may *not* be messaged, who may *not* delete or pin, and who
may *not* attach a file. The HTTP endpoints are exercised with a real Django
test client (a JSON POST body) because the SPA calls them exactly that way.
"""

import json
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core import chat as chat_domain
from core.models import (
    AgentProfile,
    Application,
    CompanyProfile,
    Conversation,
    ConversationParticipant,
    FilePermission,
    Message,
    MessageAttachment,
    SiteSettings,
    User,
)


def make_student(username="student"):
	return User.objects.create_user(
		username=username,
		email="%s@example.com" % username,
		password="Password123!",
		email_verified=True,
	)


def make_agent(username="agent"):
	return User.objects.create_user(
		username=username,
		email="%s@example.com" % username,
		password="Password123!",
		user_type=User.UserType.AGENT,
		email_verified=True,
	)


def make_admin(username="support"):
	return User.objects.create_user(
		username=username,
		email="%s@example.com" % username,
		password="Password123!",
		is_staff=True,
		email_verified=True,
	)


def link(agent, student):
	"""The ownership row "My Students" and chat both read."""
	return Application.objects.create(agent=agent, student=student)


class ChatPairingTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.agent = make_agent()
		self.student = make_student()
		self.stranger = make_student("stranger")
		link(self.agent, self.student)

	def test_admin_is_reachable_by_everyone_both_ways(self):
		self.assertTrue(chat_domain.user_can_message(self.student, self.admin))
		self.assertTrue(chat_domain.user_can_message(self.admin, self.student))

	def test_student_and_managing_agent_can_message_each_other(self):
		self.assertTrue(chat_domain.user_can_message(self.student, self.agent))
		self.assertTrue(chat_domain.user_can_message(self.agent, self.student))

	def test_agent_cannot_message_a_student_it_does_not_manage(self):
		self.assertFalse(chat_domain.user_can_message(self.agent, self.stranger))
		self.assertFalse(chat_domain.user_can_message(self.stranger, self.agent))

	def test_unrelated_students_cannot_message_each_other(self):
		self.assertFalse(chat_domain.user_can_message(self.student, self.stranger))

	def test_two_agents_cannot_message_each_other(self):
		other_agent = make_agent("agent-two")

		self.assertFalse(chat_domain.user_can_message(self.agent, other_agent))

	def test_a_user_cannot_message_themselves(self):
		self.assertFalse(chat_domain.user_can_message(self.student, self.student))

	def test_company_reaches_the_students_of_its_agents(self):
		company = User.objects.create_user(
			username="agency",
			email="agency@example.com",
			password="Password123!",
			user_type=User.UserType.COMPANY,
			email_verified=True,
		)
		profile = CompanyProfile.objects.create(
			user=company,
			company_name="Example Agency",
			company_email="agency@example.com",
			tax_number="TAX-1",
			phone="+905000000000",
		)
		AgentProfile.objects.create(user=self.agent, agency=profile)

		self.assertTrue(chat_domain.user_can_message(company, self.student))
		self.assertTrue(chat_domain.user_can_message(self.student, company))

	def test_partner_list_is_the_framework_only(self):
		partners = [user.pk for user, _label in chat_domain.chat_partners_for(self.student)]

		self.assertIn(self.admin.pk, partners)
		self.assertIn(self.agent.pk, partners)
		self.assertNotIn(self.stranger.pk, partners)

	def test_admin_does_not_see_a_user_directory(self):
		# The admin replies to whoever writes first; the contact list stays empty
		# until a thread exists, so there is nothing to enumerate.
		self.assertEqual(chat_domain.chat_partners_for(self.admin), [])

	def test_a_pair_has_exactly_one_conversation(self):
		first = chat_domain.get_or_create_conversation(self.student, self.admin)
		second = chat_domain.get_or_create_conversation(self.admin, self.student)

		self.assertEqual(first.pk, second.pk)
		self.assertLess(first.user_low_id, first.user_high_id)
		self.assertEqual(Conversation.objects.count(), 1)


class ChatMessageEndpointTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.agent = make_agent()
		self.student = make_student()
		link(self.agent, self.student)
		self.client.force_login(self.student)

	def send(self, partner, body):
		return self.client.post(
			reverse("chat_send"),
			data=json.dumps({"partner": partner.pk, "body": body}),
			content_type="application/json",
		)

	def test_sending_to_the_admin_creates_the_thread(self):
		response = self.send(self.admin, "Hello support")

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload["success"])
		conversation = Conversation.objects.get()
		self.assertEqual(payload["message"]["conversation"], conversation.pk)
		self.assertEqual(conversation.user_low_id, min(self.admin.pk, self.student.pk))
		self.assertEqual(Message.objects.get().body, "Hello support")

	def test_sending_to_an_unrelated_user_is_refused(self):
		stranger = make_student("other")

		response = self.send(stranger, "let me in")

		self.assertEqual(response.status_code, 403)
		self.assertFalse(Conversation.objects.exists())
		self.assertFalse(Message.objects.exists())

	def test_empty_and_overlong_bodies_are_refused(self):
		self.assertEqual(self.send(self.admin, "   ").status_code, 400)
		self.assertEqual(self.send(self.admin, "x" * 4001).status_code, 400)

	def test_anonymous_visitors_cannot_read_the_list(self):
		self.client.logout()

		response = self.client.get(reverse("chat_conversations"))

		self.assertEqual(response.status_code, 302)
		self.assertIn("next=", response.url)

	def test_unverified_accounts_are_read_only(self):
		pending = make_student("pending")
		pending.email_verified = False
		pending.save(update_fields=["email_verified"])
		link(self.agent, pending)
		self.client.force_login(pending)

		response = self.send(self.admin, "hello")

		self.assertEqual(response.status_code, 403)
		self.assertTrue(response.json()["email_verification_required"])

	def test_thread_is_private_to_its_participants(self):
		conversation = chat_domain.get_or_create_conversation(self.student, self.admin)
		outsider = make_student("outsider")
		self.client.force_login(outsider)

		response = self.client.get(reverse("chat_thread", args=[conversation.pk]))

		self.assertEqual(response.status_code, 403)

	def test_the_list_offers_contacts_instead_of_a_directory(self):
		response = self.client.get(reverse("chat_conversations"))

		payload = response.json()
		self.assertEqual(payload["conversations"], [])
		contacts = {row["id"]: row for row in payload["contacts"]}
		self.assertIn(self.admin.pk, contacts)
		self.assertIn(self.agent.pk, contacts)
		self.assertTrue(contacts[self.admin.pk]["is_staff"])
		self.assertIsNone(payload["can_file"])


class ChatMessageActionTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.student = make_student()
		self.conversation = chat_domain.get_or_create_conversation(self.student, self.admin)
		self.message = chat_domain.send_message(self.conversation, self.student, body="hi")

	def test_edit_sets_the_marker_for_the_sender_only(self):
		self.client.force_login(self.admin)
		peer_response = self.client.post(
			reverse("chat_edit", args=[self.message.pk]),
			data=json.dumps({"body": "tampered"}),
			content_type="application/json",
		)
		self.assertEqual(peer_response.status_code, 403)

		self.client.force_login(self.student)
		response = self.client.post(
			reverse("chat_edit", args=[self.message.pk]),
			data=json.dumps({"body": "edited"}),
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 200)
		self.message.refresh_from_db()
		self.assertEqual(self.message.body, "edited")
		self.assertTrue(self.message.is_edited)

	def test_delete_is_soft_and_sender_only(self):
		self.client.force_login(self.admin)

		peer_response = self.client.post(reverse("chat_delete", args=[self.message.pk]))

		self.assertEqual(peer_response.status_code, 403)
		self.message.refresh_from_db()
		self.assertFalse(self.message.is_deleted)

		self.client.force_login(self.student)
		response = self.client.post(reverse("chat_delete", args=[self.message.pk]))

		self.assertEqual(response.status_code, 200)
		self.message.refresh_from_db()
		# The row (and any file) stays in the database; only the view is hidden.
		self.assertTrue(self.message.is_deleted)
		self.assertEqual(self.message.deleted_by_id, self.student.pk)
		self.assertIsNotNone(self.message.deleted_at)
		self.assertEqual(Message.objects.filter(pk=self.message.pk).count(), 1)

	def test_soft_deleted_messages_serialize_without_content(self):
		self.message.soft_delete(self.student)

		payload = chat_domain.serialize_message(self.message, self.admin.pk)

		self.assertTrue(payload["deleted"])
		self.assertEqual(payload["body"], "")

	def test_pin_only_touches_own_messages_and_keeps_one_pin(self):
		second = chat_domain.send_message(self.conversation, self.admin, body="reply")
		self.client.force_login(self.student)

		denied = self.client.post(reverse("chat_pin", args=[second.pk]))
		self.assertEqual(denied.status_code, 403)

		first = self.client.post(reverse("chat_pin", args=[self.message.pk]))
		self.assertEqual(first.status_code, 200)
		self.assertTrue(first.json()["pinned"])

		self.client.force_login(self.admin)
		again = self.client.post(reverse("chat_pin", args=[second.pk]))
		self.assertEqual(again.status_code, 200)

		# One pinned message per conversation, Telegram-style.
		self.assertEqual(
			list(
				self.conversation.messages.filter(is_pinned=True).values_list("pk", flat=True)
			),
			[second.pk],
		)

	def test_forwarding_copies_the_body_into_another_thread(self):
		target = chat_domain.get_or_create_conversation(self.student, make_admin("help2"))
		self.client.force_login(self.student)

		response = self.client.post(
			reverse("chat_forward", args=[self.message.pk]),
			data=json.dumps({"partner": target.partner_of(self.student).pk}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		copy = target.messages.get()
		self.assertEqual(copy.body, self.message.body)
		self.assertEqual(copy.forwarded_from_id, self.message.pk)
		self.assertIsNotNone(copy.forwarded_from)

	def test_forwarding_into_the_same_thread_is_refused(self):
		self.client.force_login(self.student)

		response = self.client.post(
			reverse("chat_forward", args=[self.message.pk]),
			data=json.dumps({"partner": self.admin.pk}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)

	def test_deleted_messages_cannot_be_forwarded(self):
		self.message.soft_delete(self.student)
		self.client.force_login(self.student)

		response = self.client.post(
			reverse("chat_forward", args=[self.message.pk]),
			data=json.dumps({"partner": self.admin.pk}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 403)


class ChatReadReceiptTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.student = make_student()
		self.conversation = chat_domain.get_or_create_conversation(self.student, self.admin)
		self.message = chat_domain.send_message(self.conversation, self.student, body="hi")

	def read_ticks_for_sender(self):
		reads = chat_domain.participant_reads(self.conversation)
		return chat_domain.serialize_message(self.message, self.student.pk, reads=reads)["read"]

	def test_a_fresh_message_shows_one_tick(self):
		self.assertFalse(self.read_ticks_for_sender())

	def test_the_peers_read_turns_it_into_two(self):
		self.client.force_login(self.admin)

		response = self.client.post(reverse("chat_read", args=[self.conversation.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(self.read_ticks_for_sender())

	def test_unread_counts_track_the_peer_only(self):
		self.assertEqual(chat_domain.unread_counts_for(self.admin), {self.conversation.pk: 1})
		self.assertEqual(chat_domain.total_unread_for(self.admin), 1)
		self.assertEqual(chat_domain.total_unread_for(self.student), 0)

		chat_domain.mark_conversation_read(self.conversation, self.admin)

		self.assertEqual(chat_domain.total_unread_for(self.admin), 0)

	def test_presence_flips_for_the_participant_rows(self):
		chat_domain.mark_conversation_read(self.conversation, self.student)
		chat_domain.set_presence(self.student, True)

		marker = ConversationParticipant.objects.get(
			conversation=self.conversation, user=self.student
		)
		self.assertTrue(marker.is_online)

		chat_domain.set_presence(self.student, False)
		marker.refresh_from_db()
		self.assertFalse(marker.is_online)


class ChatUploadPolicyTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.agent = make_agent()
		self.student = make_student()
		link(self.agent, self.student)
		self.conversation = chat_domain.get_or_create_conversation(self.student, self.admin)
		self.message = chat_domain.send_message(self.conversation, self.student, body="here")

	def upload(self, name="note.pdf", size=32):
		return SimpleUploadedFile(name, b"x" * size, content_type="application/pdf")

	def test_a_student_without_a_grant_cannot_upload(self):
		with self.assertRaises(ValidationError):
			chat_domain.validate_chat_upload(self.upload(), self.student)

		self.assertIsNone(chat_domain.user_file_allowance_mb(self.student))

	def test_a_grant_opens_uploads_and_the_default_comes_from_settings(self):
		SiteSettings.objects.update_or_create(
			pk=1, defaults={"chat_default_file_mb": 7}
		)

		row, created = FilePermission.grant(self.student, granted_by=self.admin)

		self.assertTrue(created)
		self.assertEqual(row.max_file_mb, 7)
		self.assertEqual(chat_domain.user_file_allowance_mb(self.student), 7)
		chat_domain.validate_chat_upload(self.upload(), self.student)

	def test_a_grant_is_clamped_to_the_hard_ceiling(self):
		high, _created = FilePermission.grant(
			self.student, granted_by=self.admin, max_file_mb=999
		)
		self.assertEqual(high.max_file_mb, chat_domain.CHAT_FILE_MAX_MB)

		low, _created = FilePermission.grant(
			self.student, granted_by=self.admin, max_file_mb=0
		)
		self.assertEqual(low.max_file_mb, 1)

	def test_the_peers_allowance_bounds_the_file_size(self):
		FilePermission.grant(self.student, granted_by=self.admin, max_file_mb=1)

		with self.assertRaises(ValidationError):
			chat_domain.validate_chat_upload(self.upload(size=2 * 1024 * 1024), self.student)

	def test_disallowed_types_are_refused(self):
		FilePermission.grant(self.student, granted_by=self.admin, max_file_mb=5)

		with self.assertRaises(ValidationError):
			chat_domain.validate_chat_upload(self.upload(name="payload.exe"), self.student)

	def test_the_site_storage_ceiling_stops_uploads(self):
		FilePermission.grant(self.student, granted_by=self.admin, max_file_mb=5)
		SiteSettings.objects.update_or_create(
			pk=1, defaults={"chat_max_total_storage_mb": 0}
		)

		with self.assertRaises(ValidationError):
			chat_domain.validate_chat_upload(self.upload(), self.student)

	def test_staff_uploads_are_bounded_by_the_ceiling_only(self):
		self.assertEqual(
			chat_domain.user_file_allowance_mb(self.admin), chat_domain.CHAT_FILE_MAX_MB
		)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ChatUploadEndpointTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.student = make_student()
		self.conversation = chat_domain.get_or_create_conversation(self.student, self.admin)
		self.message = chat_domain.send_message(self.conversation, self.student, body="here")

	def upload(self, name="note.pdf", size=32):
		return SimpleUploadedFile(name, b"x" * size, content_type="application/pdf")

	def test_upload_attaches_to_the_senders_latest_message(self):
		FilePermission.grant(self.student, granted_by=self.admin, max_file_mb=2)
		self.client.force_login(self.student)

		response = self.client.post(
			reverse("chat_upload", args=[self.conversation.pk]), {"file": self.upload()}
		)

		self.assertEqual(response.status_code, 200)
		attachment = MessageAttachment.objects.get()
		self.assertEqual(attachment.message_id, self.message.pk)
		self.assertEqual(attachment.original_name, "note.pdf")
		self.assertFalse(attachment.is_image)

	def test_upload_is_refused_without_a_grant(self):
		self.client.force_login(self.student)

		response = self.client.post(
			reverse("chat_upload", args=[self.conversation.pk]), {"file": self.upload()}
		)

		self.assertEqual(response.status_code, 400)
		self.assertFalse(MessageAttachment.objects.exists())

	def test_a_stranger_cannot_upload_into_the_thread(self):
		intruder = make_student("intruder")
		FilePermission.grant(intruder, granted_by=self.admin, max_file_mb=2)
		self.client.force_login(intruder)

		response = self.client.post(
			reverse("chat_upload", args=[self.conversation.pk]), {"file": self.upload()}
		)

		self.assertEqual(response.status_code, 403)


class ChatGrantEndpointTests(TestCase):
	def setUp(self):
		self.admin = make_admin()
		self.agent = make_agent()
		self.student = make_student()
		link(self.agent, self.student)

	def test_the_admin_grants_any_student(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse("chat_grant", args=[self.student.pk]),
			data=json.dumps({"max_file_mb": 12}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(FilePermission.objects.get().max_file_mb, 12)

	def test_an_agent_grants_a_managed_student(self):
		self.client.force_login(self.agent)

		response = self.client.post(
			reverse("chat_grant", args=[self.student.pk]),
			data=json.dumps({"max_file_mb": 3}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(FilePermission.objects.get().is_active)

	def test_an_agent_cannot_grant_a_student_it_does_not_manage(self):
		stranger = make_student("ungoverned")
		self.client.force_login(self.agent)

		response = self.client.post(
			reverse("chat_grant", args=[stranger.pk]),
			data=json.dumps({"max_file_mb": 3}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 403)
		self.assertFalse(FilePermission.objects.exists())

	def test_revoke_deactivates_the_row(self):
		FilePermission.grant(self.student, granted_by=self.admin, max_file_mb=4)
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse("chat_grant", args=[self.student.pk]),
			data=json.dumps({"revoke": True}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertFalse(FilePermission.objects.get().is_active)
		self.assertIsNone(chat_domain.user_file_allowance_mb(self.student))
