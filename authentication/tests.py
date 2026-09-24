from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import User

from .forms import ChangePasswordForm, LoginForm, RegisterForm
from .models import VerificationCode
from core.utils.jwt_auth import JWTManager, authenticate_with_jwt


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
		data = response.json()
		self.assertTrue(data["success"])
		self.assertEqual(data["redirect"], reverse("dashboard"))
		# Check JWT tokens are returned
		self.assertIn("access", data)
		self.assertIn("refresh", data)
		self.assertIn("user", data)

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


@override_settings(RATELIMIT_ENABLE=False)
class LoginRedirectTargetTests(TestCase):
	"""A dashboard deep link has to survive the whole authentication detour.

	The SPA reads the page to open from ?page=, so a visitor who follows (or
	bookmarks) /dashboard/?page=profile must still land on the profile fragment
	after logging in or registering -- not on the default landing page.
	"""

	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			email="student@example.com",
			password="StrongPassword123!",
			is_active=True,
		)
		self.target = reverse("dashboard") + "?page=profile"

	def test_login_form_carries_the_target_in_a_hidden_field(self):
		response = self.client.get(reverse("login"), {"next": self.target})

		self.assertContains(response, f'name="next" value="{self.target}"')

	def test_ajax_login_redirects_to_the_requested_target(self):
		response = self.client.post(
			reverse("login"),
			{
				"username": "student@example.com",
				"password": "StrongPassword123!",
				"next": self.target,
			},
			HTTP_X_REQUESTED_WITH="XMLHttpRequest",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["redirect"], self.target)

	def test_non_ajax_login_redirects_to_the_requested_target(self):
		response = self.client.post(
			reverse("login"),
			{
				"username": "student@example.com",
				"password": "StrongPassword123!",
				"next": self.target,
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, self.target)

	def test_already_authenticated_visitor_opens_the_requested_target(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse("login"), {"next": self.target})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, self.target)

	def test_offsite_target_is_ignored(self):
		response = self.client.post(
			reverse("login"),
			{
				"username": "student@example.com",
				"password": "StrongPassword123!",
				"next": "https://evil.example.com/steal",
			},
			HTTP_X_REQUESTED_WITH="XMLHttpRequest",
		)

		self.assertEqual(response.json()["redirect"], reverse("dashboard"))

	@patch("authentication.views.dispatch_email", return_value=True)
	def test_registration_detour_carries_the_target(self, dispatch_email):
		response = self.client.post(
			reverse("register"),
			{
				"email": "new@example.com",
				"password1": "StrongPassword123!",
				"password2": "StrongPassword123!",
				"next": self.target,
			},
			HTTP_X_REQUESTED_WITH="XMLHttpRequest",
		)

		user = User.objects.get(email="new@example.com")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			unquote(response.json()["redirect"]),
			reverse("confirm_code", kwargs={"pk": user.pk}) + f"?next={self.target}",
		)

	def test_confirmation_step_hands_the_target_to_the_username_step(self):
		vc = VerificationCode.create_registration(self.user)

		response = self.client.post(
			reverse("confirm_code", kwargs={"pk": self.user.pk}),
			{"code": vc.code, "next": self.target},
			HTTP_X_REQUESTED_WITH="XMLHttpRequest",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			unquote(response.json()["redirect"]),
			reverse("username_selection") + f"?next={self.target}",
		)

	def test_username_step_opens_the_requested_target(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("username_selection"),
			{"action": "skip", "next": self.target},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, self.target)


class JWTManagerTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			email="student@example.com",
			password="StrongPassword123!",
			is_active=True,
		)

	def test_create_access_token_returns_valid_jwt(self):
		access_token = JWTManager.create_access_token(self.user)
		self.assertIsInstance(access_token, str)
		self.assertTrue(access_token.count('.') == 2)  # JWT format: header.payload.signature

	def test_create_refresh_token_returns_valid_jwt(self):
		refresh_token = JWTManager.create_refresh_token(self.user)
		self.assertIsInstance(refresh_token, str)
		self.assertTrue(refresh_token.count('.') == 2)

	def test_verify_token_returns_payload(self):
		access_token = JWTManager.create_access_token(self.user)
		payload = JWTManager.verify_token(access_token, token_type='access')

		self.assertEqual(payload['user_id'], self.user.id)
		self.assertEqual(payload['email'], self.user.email)
		self.assertEqual(payload['user_type'], self.user.user_type)
		self.assertEqual(payload['token_type'], 'access')

	def test_get_user_from_token_returns_user(self):
		access_token = JWTManager.create_access_token(self.user)
		user = JWTManager.get_user_from_token(access_token)

		self.assertEqual(user, self.user)

	def test_get_user_from_invalid_token_returns_none(self):
		user = JWTManager.get_user_from_token('invalid.token.here')
		self.assertIsNone(user)

	def test_refresh_access_token_creates_new_token(self):
		refresh_token = JWTManager.create_refresh_token(self.user)
		new_access = JWTManager.refresh_access_token(refresh_token)

		self.assertIsInstance(new_access, str)
		self.assertNotEqual(new_access, refresh_token)

		# Verify new token is valid
		payload = JWTManager.verify_token(new_access, token_type='access')
		self.assertEqual(payload['user_id'], self.user.id)

	def test_wrong_token_type_raises_error(self):
		access_token = JWTManager.create_access_token(self.user)
		with self.assertRaises(Exception):
			JWTManager.verify_token(access_token, token_type='refresh')

	def test_expired_token_raises_error(self):
		# Create token with very short expiration
		import jwt
		from datetime import datetime, timedelta

		payload = {
			'user_id': self.user.id,
			'email': self.user.email,
			'user_type': self.user.user_type,
			'exp': datetime.utcnow() - timedelta(hours=1),  # Expired
			'iat': datetime.utcnow() - timedelta(hours=2),
			'token_type': 'access',
		}
		expired_token = jwt.encode(payload, JWTManager.SECRET_KEY, algorithm=JWTManager.ALGORITHM)

		with self.assertRaises(jwt.ExpiredSignatureError):
			JWTManager.verify_token(expired_token)

	def test_authenticate_with_jwt_returns_user_tuple(self):
		access_token = JWTManager.create_access_token(self.user)
		user, _ = authenticate_with_jwt(access_token)

		self.assertEqual(user, self.user)

	def test_inactive_user_token_returns_none(self):
		self.user.is_active = False
		self.user.save()

		access_token = JWTManager.create_access_token(self.user)
		user = JWTManager.get_user_from_token(access_token)

		self.assertIsNone(user)


@override_settings(RATELIMIT_ENABLE=False)
class JWTAuthAPITests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			email="student@example.com",
			password="StrongPassword123!",
			is_active=True,
		)

	def test_obtain_token_with_valid_credentials(self):
		response = self.client.post(
			reverse('api-token-obtain'),
			data='{"username": "student@example.com", "password": "StrongPassword123!"}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertIn('access', data)
		self.assertIn('refresh', data)
		self.assertIn('user', data)
		self.assertEqual(data['user']['email'], self.user.email)

	def test_obtain_token_with_invalid_credentials(self):
		response = self.client.post(
			reverse('api-token-obtain'),
			data='{"username": "student@example.com", "password": "wrongpassword"}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 401)
		data = response.json()
		self.assertIn('error', data)

	def test_obtain_token_with_missing_credentials(self):
		response = self.client.post(
			reverse('api-token-obtain'),
			data='{}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		data = response.json()
		self.assertIn('error', data)

	def test_refresh_token_with_valid_refresh_token(self):
		refresh_token = JWTManager.create_refresh_token(self.user)

		response = self.client.post(
			reverse('api-token-refresh'),
			data=f'{{"refresh": "{refresh_token}"}}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertIn('access', data)
		self.assertIn('user', data)

	def test_refresh_token_with_invalid_token(self):
		response = self.client.post(
			reverse('api-token-refresh'),
			data='{"refresh": "invalid.token.here"}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 401)
		data = response.json()
		self.assertIn('error', data)

	def test_verify_token_with_valid_token(self):
		access_token = JWTManager.create_access_token(self.user)

		response = self.client.post(
			reverse('api-token-verify'),
			data=f'{{"token": "{access_token}"}}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertTrue(data['valid'])
		self.assertIn('user', data)

	def test_verify_token_with_invalid_token(self):
		response = self.client.post(
			reverse('api-token-verify'),
			data='{"token": "invalid.token.here"}',
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertFalse(data['valid'])
