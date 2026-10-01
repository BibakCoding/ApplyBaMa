"""Representation-request tests: the consent gate in front of "My Students".

The rules that must not drift are the negative ones — who may *not* be linked
without consent, who may *not* answer a request, and what a second request for
the same pair does. Approval is the moment ownership is created, so it is also
asserted end-to-end: the Application link, the chat thread and the notification
the requester receives.

The endpoints are called the way the SPA calls them (a real test client and a
form-encoded POST), so a change to the URL names or the response shape fails
here rather than in the browser.
"""

from django.test import TestCase
from django.urls import reverse

from core import agent_requests
from core.models import (
    AgentLinkRequest,
    Application,
    Conversation,
    Notification,
    NotificationRecipient,
    User,
)

PASSWORD = "Password123!"


def make_agent(username="request-agent"):
    return User.objects.create_user(
        username=username,
        email="%s@example.com" % username,
        password=PASSWORD,
        user_type=User.UserType.AGENT,
        email_verified=True,
    )


def make_student(username="request-student"):
    return User.objects.create_user(
        username=username,
        email="%s@example.com" % username,
        password=PASSWORD,
        email_verified=True,
    )


class PublicIdTests(TestCase):
    """Every account has a unique 16-digit ID, assigned on first save."""

    def test_id_is_assigned_on_creation_and_is_16_digits(self):
        user = make_student()
        self.assertEqual(len(user.public_id), agent_requests.PUBLIC_ID_LENGTH)
        self.assertTrue(user.public_id.isdigit())

    def test_ids_are_unique_across_accounts(self):
        ids = {make_student("id-a").public_id, make_student("id-b").public_id}
        self.assertEqual(len(ids), 2)

    def test_normalize_strips_everything_but_digits(self):
        self.assertEqual(
            agent_requests.normalize_public_id(" 1234-5678 9012 3456 "),
            "1234567890123456",
        )

    def test_lookup_requires_the_full_id(self):
        user = make_student()
        self.assertIsNone(agent_requests.find_user_by_public_id(user.public_id[:-1]))
        self.assertEqual(
            agent_requests.find_user_by_public_id(user.public_id), user
        )


class SendRequestRulesTests(TestCase):
    def setUp(self):
        self.agent = make_agent()
        self.student = make_student()

    def test_agent_may_request_an_unlinked_student(self):
        allowed, reason = agent_requests.can_send_request(self.agent, self.student)
        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_a_user_cannot_request_themselves(self):
        allowed, reason = agent_requests.can_send_request(self.agent, self.agent)
        self.assertFalse(allowed)
        self.assertEqual(reason, "self")

    def test_an_already_managed_student_is_not_requested_again(self):
        Application.objects.create(agent=self.agent, student=self.student)
        allowed, reason = agent_requests.can_send_request(self.agent, self.student)
        self.assertFalse(allowed)
        self.assertEqual(reason, "already_managed")

    def test_a_second_live_request_for_the_same_pair_is_refused(self):
        agent_requests.send_link_request(self.agent, self.student)
        allowed, reason = agent_requests.can_send_request(self.agent, self.student)
        self.assertFalse(allowed)
        self.assertEqual(reason, "pending")

    def test_the_database_refuses_two_live_requests(self):
        agent_requests.send_link_request(self.agent, self.student)
        with self.assertRaises(Exception):
            AgentLinkRequest.objects.create(
                requester=self.agent, target=self.student
            )

    def test_a_self_request_is_refused_by_the_database_too(self):
        with self.assertRaises(Exception):
            AgentLinkRequest.objects.create(
                requester=self.agent, target=self.agent
            )

    def test_a_declined_request_may_be_sent_again(self):
        link = agent_requests.send_link_request(self.agent, self.student)
        agent_requests.respond_to_request(link, self.student, accept=False)
        allowed, _reason = agent_requests.can_send_request(self.agent, self.student)
        self.assertTrue(allowed)

    def test_sending_creates_the_target_notification_with_the_action_link(self):
        agent_requests.send_link_request(self.agent, self.student)
        delivery = NotificationRecipient.objects.get(user=self.student)
        self.assertEqual(delivery.notification.action_url, "requests")
        self.assertEqual(delivery.notification.sender, self.agent)
        self.assertFalse(delivery.is_read)


class ApprovalTests(TestCase):
    def setUp(self):
        self.agent = make_agent()
        self.student = make_student()
        self.link = agent_requests.send_link_request(self.agent, self.student)

    def test_only_the_target_may_answer(self):
        with self.assertRaises(PermissionError):
            agent_requests.respond_to_request(self.link, self.agent, accept=True)
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, AgentLinkRequest.Status.PENDING)

    def test_approval_creates_ownership_and_the_chat_thread(self):
        agent_requests.respond_to_request(self.link, self.student, accept=True)

        self.link.refresh_from_db()
        self.assertEqual(self.link.status, AgentLinkRequest.Status.APPROVED)
        self.assertIsNotNone(self.link.responded_at)

        self.assertTrue(
            Application.objects.filter(
                agent=self.agent, student=self.student
            ).exists()
        )
        self.assertTrue(
            Conversation.objects.filter(
                user_low=min(self.agent, self.student, key=lambda u: u.pk),
                user_high=max(self.agent, self.student, key=lambda u: u.pk),
            ).exists()
        )

        # The student now shows up where ownership is read.
        from dashboard.views import get_managed_students

        self.assertIn(self.student.pk, set(get_managed_students(self.agent)))

    def test_approval_notifies_the_requester(self):
        agent_requests.respond_to_request(self.link, self.student, accept=True)
        delivery = NotificationRecipient.objects.get(
            user=self.agent, notification__title__icontains="accepted"
        )
        self.assertEqual(delivery.notification.notification_type, "success")

    def test_a_request_can_only_be_answered_once(self):
        agent_requests.respond_to_request(self.link, self.student, accept=True)
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            agent_requests.respond_to_request(self.link, self.student, accept=False)

    def test_declining_leaves_no_ownership(self):
        agent_requests.respond_to_request(self.link, self.student, accept=False)
        self.assertFalse(
            Application.objects.filter(
                agent=self.agent, student=self.student
            ).exists()
        )
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, AgentLinkRequest.Status.DECLINED)

    def test_cancelling_is_the_requesters_privilege_only(self):
        with self.assertRaises(PermissionError):
            agent_requests.cancel_request(self.link, self.student)
        agent_requests.cancel_request(self.link, self.agent)
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, AgentLinkRequest.Status.CANCELLED)

    def test_pending_received_count_tracks_the_open_requests(self):
        self.assertEqual(agent_requests.pending_received_count(self.student), 1)
        agent_requests.respond_to_request(self.link, self.student, accept=False)
        self.assertEqual(agent_requests.pending_received_count(self.student), 0)


class RequestEndpointTests(TestCase):
    def setUp(self):
        self.agent = make_agent()
        self.student = make_student()

    def test_lookup_returns_the_candidate(self):
        self.client.force_login(self.agent)
        response = self.client.get(
            reverse("agent_request_search"), {"public_id": self.student.public_id}
        )
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["found"])
        self.assertTrue(data["can_send"])
        self.assertEqual(data["candidate"]["username"], self.student.username)

    def test_lookup_reports_an_unknown_id_without_leaking(self):
        self.client.force_login(self.agent)
        response = self.client.get(
            reverse("agent_request_search"), {"public_id": "0" * 16}
        )
        data = response.json()
        self.assertFalse(data["found"])
        self.assertNotIn("candidate", data)

    def test_lookup_refuses_a_student_account(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("agent_request_search"), {"public_id": self.agent.public_id}
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_visitors_cannot_use_the_endpoints(self):
        response = self.client.get(
            reverse("agent_request_search"), {"public_id": self.student.public_id}
        )
        self.assertNotEqual(response.status_code, 200)

    def test_sending_records_the_request_and_answers_the_dialog(self):
        self.client.force_login(self.agent)
        response = self.client.post(
            reverse("agent_request_send"),
            {"public_id": self.student.public_id, "message": "Hello!"},
        )
        data = response.json()
        self.assertTrue(data["success"])

        link = AgentLinkRequest.objects.get()
        self.assertEqual(link.requester, self.agent)
        self.assertEqual(link.target, self.student)
        self.assertEqual(link.message, "Hello!")

    def test_a_request_for_a_user_i_already_manage_is_refused(self):
        Application.objects.create(agent=self.agent, student=self.student)
        self.client.force_login(self.agent)
        response = self.client.post(
            reverse("agent_request_send"), {"public_id": self.student.public_id}
        )
        self.assertFalse(response.json()["success"])

    def test_a_student_cannot_send_requests(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("agent_request_send"), {"public_id": self.agent.public_id}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AgentLinkRequest.objects.exists())

    def test_unverified_accounts_are_read_only(self):
        pending = make_agent("pending-agent")
        pending.email_verified = False
        pending.save(update_fields=["email_verified"])
        self.client.force_login(pending)
        response = self.client.post(
            reverse("agent_request_send"), {"public_id": self.student.public_id}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["email_verification_required"])

    def test_the_target_accepts_through_the_endpoint(self):
        link = agent_requests.send_link_request(self.agent, self.student)
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("agent_request_respond", args=[link.pk]), {"action": "accept"}
        )
        self.assertTrue(response.json()["success"])
        self.assertTrue(
            Application.objects.filter(
                agent=self.agent, student=self.student
            ).exists()
        )

    def test_an_outsider_cannot_answer_a_request(self):
        link = agent_requests.send_link_request(self.agent, self.student)
        outsider = make_student("outsider")
        self.client.force_login(outsider)
        response = self.client.post(
            reverse("agent_request_respond", args=[link.pk]), {"action": "accept"}
        )
        self.assertEqual(response.status_code, 404)
        link.refresh_from_db()
        self.assertEqual(link.status, AgentLinkRequest.Status.PENDING)

    def test_the_requester_can_withdraw_a_pending_request(self):
        link = agent_requests.send_link_request(self.agent, self.student)
        self.client.force_login(self.agent)
        response = self.client.post(reverse("agent_request_cancel", args=[link.pk]))
        self.assertTrue(response.json()["success"])
        link.refresh_from_db()
        self.assertEqual(link.status, AgentLinkRequest.Status.CANCELLED)


class RequestsPageTests(TestCase):
    def setUp(self):
        self.agent = make_agent()
        self.student = make_student()

    def test_the_page_shows_both_sections_to_an_agent(self):
        agent_requests.send_link_request(self.agent, self.student)
        self.client.force_login(self.agent)
        response = self.client.get(
            reverse("dashboard_content", args=["requests"])
        )
        self.assertContains(response, self.student.username)
        self.assertContains(response, "data-requests-page")

    def test_a_student_sees_the_received_section_only(self):
        agent_requests.send_link_request(self.agent, self.student)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("dashboard_content", args=["requests"])
        )
        self.assertContains(response, self.agent.username)
        # No "Sent" heading for an account that cannot send.
        self.assertNotContains(response, "data-page=\"my_students\"")

    def test_the_shell_renders_the_requests_badge(self):
        agent_requests.send_link_request(self.agent, self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "requestsBadge")
        self.assertContains(response, ">1<")

    def test_receiving_a_request_creates_one_unread_notification(self):
        agent_requests.send_link_request(self.agent, self.student)
        self.assertEqual(
            NotificationRecipient.objects.filter(
                user=self.student, is_read=False
            ).count(),
            1,
        )

    def test_notification_detail_carries_the_action_url(self):
        agent_requests.send_link_request(self.agent, self.student)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("notification_detail", args=[Notification.objects.get().pk])
        )
        self.assertEqual(response.json()["action_url"], "requests")
