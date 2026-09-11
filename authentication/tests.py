from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import User

from .forms import ChangePasswordForm, LoginForm, RegisterForm
from .models import VerificationCode


class VerificationCodeTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			email="student@example.com",
			password="OldPassword123!",
			is_active=False,
		)

	def test_registration_codes_are_six_digits_and_invalidate_previous_codes(self):
		first = VerificationCode.create_registration(self.user)
		second = VerificationCode.create_registration(self.user)
		first.refresh_from_db()

		self.assertEqual(len(first.code), 6)
		self.assertTrue(first.code.isdigit())
		self.assertTrue(first.used)
		self.assertFalse(second.used)
		self.assertIsNone(second.token)

	def test_reset_codes_get_expiration_and_unique_token(self):
		code = VerificationCode.create_reset(self.user)

		self.assertEqual(len(code.code), 6)
		self.assertTrue(code.code.isdigit())
		self.assertTrue(code.token)
		self.assertGreater(code.expires_at, timezone.now())


class AuthenticationFormTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			email="student@example.com",
			password="StrongPassword123!",
			is_active=True,
		)

	def test_login_form_authenticates_by_email_or_username(self):
		for identifier in ("STUDENT@EXAMPLE.COM", "STUDENT"):
			form = LoginForm({"username": identifier, "password": "StrongPassword123!"})
			self.assertTrue(form.is_valid(), form.errors)
			self.assertEqual(form.user, self.user)

	def test_login_form_rejects_invalid_credentials(self):
		form = LoginForm({"username": "student", "password": "wrong-password"})

		self.assertFalse(form.is_valid())
		self.assertIn("invalid_credentials", {error.code for error in form.non_field_errors().as_data()})

	def test_register_form_rejects_mismatched_passwords(self):
		form = RegisterForm(
			{
				"email": "new@example.com",
				"password1": "StrongPassword123!",
				"password2": "DifferentPassword123!",
			}
		)

		self.assertFalse(form.is_valid())
		self.assertTrue(form.non_field_errors())

	def test_change_password_form_rejects_mismatched_passwords(self):
		form = ChangePasswordForm(
			{
				"code": "123456",
				"new_password1": "StrongPassword123!",
				"new_password2": "DifferentPassword123!",
			}
		)

		self.assertFalse(form.is_valid())
		self.assertTrue(form.non_field_errors())


@override_settings(RATELIMIT_ENABLE=False)
class AuthenticationViewTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			email="student@example.com",
			password="StrongPassword123!",
			is_active=True,
		)

	def test_login_ajax_returns_redirect_for_valid_credentials(self):
		response = self.client.post(
			reverse("login"),
			{"username": "student@example.com", "password": "StrongPassword123!"},
			HTTP_X_REQUESTED_WITH="XMLHttpRequest",
		)

		self.assertEqual(response.status_code, 200)
		self.assertJSONEqual(
			response.content,
			{"success": True, "message": "Logged in successfully.", "redirect": reverse("dashboard")},
		)

	@patch("authentication.views.dispatch_email", return_value=True)
	def test_registration_ajax_creates_inactive_user_and_code(self, dispatch_email):
		response = self.client.post(
			reverse("register"),
			{
				"email": "new@example.com",
				"password1": "StrongPassword123!",
				"password2": "StrongPassword123!",
			},
			HTTP_X_REQUESTED_WITH="XMLHttpRequest",
		)

		user = User.objects.get(email="new@example.com")
		self.assertEqual(response.status_code, 200)
		self.assertFalse(user.is_active)
		self.assertTrue(
			VerificationCode.objects.filter(
				user=user, code_type=VerificationCode.CodeType.REGISTRATION
			).exists()
		)
		dispatch_email.assert_called_once()

	def test_expired_change_password_token_returns_not_found(self):
		response = self.client.get(reverse("change_password", kwargs={"token": "missing-token"}))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("login"))
