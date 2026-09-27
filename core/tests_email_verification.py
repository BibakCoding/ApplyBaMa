"""Tests for the email verification / read-only mode feature.

Covers the whole journey introduced with ``User.email_verified`` and
``User.pending_email``: requesting a change from the dashboard, confirming it
through the emailed link, the read-only enforcement while unverified, and the
resend / cancel escape hatches.
"""

from unittest import mock

from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import VerificationCode
from core.models import User

PASSWORD = "Password123!"


def make_user(username, **overrides):
    defaults = dict(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        email_verified=True,
    )
    defaults.update(overrides)
    return User.objects.create_user(**defaults)


class ModelBehaviourTests(TestCase):
    def test_is_fully_verified_requires_no_pending_email(self):
        user = make_user("flaguser")
        self.assertTrue(user.is_fully_verified)

        user.pending_email = "new@example.com"
        self.assertFalse(user.is_fully_verified)

        user.email_verified = False
        user.pending_email = None
        self.assertFalse(user.is_fully_verified)

    def test_email_change_codes_receive_a_link_token(self):
        user = make_user("codetoken")
        vc = VerificationCode.create_email_change(user)
        self.assertTrue(vc.token)
        self.assertEqual(vc.code_type, VerificationCode.CodeType.EMAIL_CHANGE)


class RequestEmailChangeTests(TestCase):
    def setUp(self):
        self.user = make_user("changer")
        self.client.force_login(self.user)

    def test_changing_email_sends_link_and_enters_readonly(self):
        response = self.client.post(
            reverse("profile_view"),
            {
                "form_type": "contact_info",
                "email": "new@example.com",
                "mobile": "+905000000001",
            },
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "changer@example.com")
        self.assertEqual(self.user.pending_email, "new@example.com")
        self.assertFalse(self.user.email_verified)
        self.assertFalse(self.user.is_fully_verified)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("new@example.com", data["message"])

        # The link is mailed to the NEW address.
        vc = VerificationCode.objects.filter(
            user=self.user, code_type=VerificationCode.CodeType.EMAIL_CHANGE
        ).first()
        self.assertIsNotNone(vc)
        self.assertFalse(vc.used)

    def test_unchanged_email_saves_normally(self):
        response = self.client.post(
            reverse("profile_view"),
            {
                "form_type": "contact_info",
                "email": self.user.email,
                "mobile": "+905000000002",
            },
        )
        self.user.refresh_from_db()
        self.assertTrue(response.json()["success"])
        self.assertIsNone(self.user.pending_email)
        self.assertTrue(self.user.email_verified)

    def test_change_to_taken_email_is_rejected(self):
        make_user("occupied")
        response = self.client.post(
            reverse("profile_view"),
            {
                "form_type": "contact_info",
                "email": "occupied@example.com",
                "mobile": "+905000000003",
            },
        )
        self.user.refresh_from_db()
        # The SPA's error contract is success:false + errors; the handler
        # never sets an HTTP error status (matching _form_error_response).
        self.assertFalse(response.json()["success"])
        self.assertIsNone(self.user.pending_email)
        self.assertTrue(self.user.email_verified)


class VerificationLinkTests(TestCase):
    def setUp(self):
        self.user = make_user("linker", email_verified=False)
        self.user.pending_email = "new@example.com"
        self.user.save()
        self.vc = VerificationCode.create_email_change(self.user)

    def test_valid_link_commits_the_change(self):
        url = reverse("verify_email", kwargs={"token": self.vc.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "new@example.com")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertIsNone(self.user.pending_email)
        self.assertTrue(self.user.email_verified)
        self.vc.refresh_from_db()
        self.assertTrue(self.vc.used)

    def test_used_link_is_rejected(self):
        url = reverse("verify_email", kwargs={"token": self.vc.token})
        self.client.get(url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")

    def test_expired_link_does_not_commit(self):
        VerificationCode.objects.filter(pk=self.vc.pk).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        url = reverse("verify_email", kwargs={"token": self.vc.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "linker@example.com")
        self.assertIsNone(self.user.pending_email)
        self.vc.refresh_from_db()
        self.assertTrue(self.vc.used)

    def test_unknown_token_returns_404(self):
        response = self.client.get(
            reverse("verify_email", kwargs={"token": "no-such-token"})
        )
        self.assertEqual(response.status_code, 404)


class ReadOnlyEnforcementTests(TestCase):
    def setUp(self):
        self.user = make_user("readonly", email_verified=False)
        self.client.force_login(self.user)

    def test_unverified_user_sees_verification_fragment(self):
        for page in ("universities", "programs"):
            response = self.client.get(
                reverse("dashboard_content", kwargs={"page": page})
            )
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(
                response, "dashboard/fragments/verification_required.html"
            )

    def test_verified_user_sees_real_content(self):
        self.user.email_verified = True
        self.user.save()
        response = self.client.get(
            reverse("dashboard_content", kwargs={"page": "programs"})
        )
        self.assertTemplateUsed(response, "dashboard/fragments/programs.html")

    def test_mutation_views_return_403_with_reason(self):
        response = self.client.post(reverse("generate_password"))
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertTrue(data["email_verification_required"])

    def test_resend_and_cancel_stay_available_while_unverified(self):
        # No pending change yet, but the account itself is unverified, so the
        # resend view runs (it is deliberately outside the read-only gate) and
        # asks the user to confirm the address they already have.
        response = self.client.post(reverse("resend_email_verification"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.user.pending_email = "new@example.com"
        self.user.save()
        response = self.client.post(reverse("resend_email_verification"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        response = self.client.post(reverse("cancel_email_change"))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pending_email)

    def test_verified_user_can_post(self):
        self.user.email_verified = True
        self.user.save()
        response = self.client.post(reverse("generate_password"))
        self.assertEqual(response.status_code, 200)


class ResendAndCancelTests(TestCase):
    # resend_email_verification is rate-limited and the test runner's LocMemCache
    # is shared between test methods, so this class disables the limiter (the
    # project-wide test convention, see authentication.tests) instead of
    # tripping it through accumulated per-user counters.
    @override_settings(RATELIMIT_ENABLE=False)
    def setUp(self):
        cache.clear()
        self.user = make_user("resender")
        self.client.force_login(self.user)

    def test_resend_without_pending_change_fails(self):
        response = self.client.post(reverse("resend_email_verification"))
        data = response.json()
        self.assertEqual(data["errors"], ["There is no pending email change."])
        self.assertFalse(data["success"])

    def test_resend_creates_fresh_code(self):
        self.user.pending_email = "new@example.com"
        self.user.email_verified = False
        self.user.save()
        first = VerificationCode.create_email_change(self.user)

        response = self.client.post(reverse("resend_email_verification"))
        self.assertTrue(response.json()["success"])

        first.refresh_from_db()
        self.assertTrue(first.used)
        live = VerificationCode.objects.filter(
            user=self.user,
            code_type=VerificationCode.CodeType.EMAIL_CHANGE,
            used=False,
        )
        self.assertEqual(live.count(), 1)

    def test_cancel_restores_verified_state_and_invalidates_links(self):
        self.user.pending_email = "new@example.com"
        self.user.email_verified = False
        self.user.save()
        vc = VerificationCode.create_email_change(self.user)

        response = self.client.post(reverse("cancel_email_change"))
        self.assertTrue(response.json()["success"])
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pending_email)
        self.assertTrue(self.user.email_verified)
        vc.refresh_from_db()
        self.assertTrue(vc.used)


class VerificationEmailTemplateTests(TestCase):
    """The verification email serves two situations with different wording."""

    def render(self, is_change):
        return render_to_string(
            "emails/verify_email.html",
            {
                "site_name": "Apply Ba Ma",
                "new_email": "someone@example.com",
                "is_change": is_change,
                "verify_url": "https://example.com/en/auth/verify-email/token/",
                "language": "en",
            },
        )

    def test_change_request_uses_the_change_wording(self):
        html = self.render(True)
        self.assertIn("A request was made to change the email address", html)
        self.assertIn("Verify your new email address", html)
        self.assertNotIn("Please confirm this email address", html)

    def test_confirming_current_address_uses_the_plain_wording(self):
        html = self.render(False)
        self.assertIn("Please confirm this email address for your", html)
        self.assertNotIn("A request was made to change the email address", html)
        self.assertNotIn("Verify your new email address", html)


@override_settings(RATELIMIT_ENABLE=False)
class CurrentAddressVerificationTests(TestCase):
    """A never-verified account can confirm the address it already has.

    Requesting a new link used to require a pending change, which left a
    never-verified account with no in-product way back to full access, while
    the read-only banner told it to re-save the contact form - something that
    (the address being unchanged) sent nothing at all.
    """

    def setUp(self):
        cache.clear()
        self.user = make_user("neververified", email_verified=False)
        self.client.force_login(self.user)

    @mock.patch("authentication.views.send_async_email")
    def test_resend_mails_the_current_address(self, task):
        response = self.client.post(reverse("resend_email_verification"))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("neververified@example.com", data["message"])

        args, _kwargs = task.delay.call_args
        self.assertEqual(str(args[0]), "Verify your email address")
        self.assertEqual(args[3], ["neververified@example.com"])

    @mock.patch("authentication.views.send_async_email")
    def test_link_confirms_the_current_address_without_changing_it(self, task):
        self.client.post(reverse("resend_email_verification"))
        vc = VerificationCode.objects.filter(
            user=self.user,
            code_type=VerificationCode.CodeType.EMAIL_CHANGE,
            used=False,
        ).get()

        response = self.client.get(
            reverse("verify_email", kwargs={"token": vc.token})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "neververified@example.com")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neververified@example.com")
        self.assertIsNone(self.user.pending_email)
        self.assertTrue(self.user.email_verified)
        self.assertTrue(self.user.is_fully_verified)

    @mock.patch("authentication.views.send_async_email")
    def test_change_request_still_uses_the_new_address_wording(self, task):
        self.user.pending_email = "moved@example.com"
        self.user.save()
        response = self.client.post(reverse("resend_email_verification"))
        self.assertTrue(response.json()["success"])

        args, _kwargs = task.delay.call_args
        self.assertEqual(str(args[0]), "Verify your new email address")
        self.assertEqual(args[3], ["moved@example.com"])

    def test_verified_account_without_pending_change_cannot_resend(self):
        self.user.email_verified = True
        self.user.save()
        response = self.client.post(reverse("resend_email_verification"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["errors"], ["There is no pending email change."]
        )

    def test_stale_link_without_pending_change_expires(self):
        # Live code, nothing pending, account already verified: leftover work
        # that must not be able to activate anything.
        self.user.email_verified = True
        self.user.save()
        vc = VerificationCode.create_email_change(self.user)
        response = self.client.get(
            reverse("verify_email", kwargs={"token": vc.token})
        )
        self.assertEqual(response.status_code, 410)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)


class RegistrationSetsVerifiedTests(TestCase):
    def test_confirm_code_marks_email_verified(self):
        from core.utils.notifications import NotificationRecipient

        user = User.objects.create_user(
            username="fresh",
            email="fresh@example.com",
            password=PASSWORD,
            is_active=False,
        )
        VerificationCode.create_registration(user)
        vc = VerificationCode.objects.filter(
            user=user, code_type=VerificationCode.CodeType.REGISTRATION
        ).first()

        self.client.post(
            reverse("confirm_code", kwargs={"pk": user.pk}), {"code": vc.code}
        )
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
