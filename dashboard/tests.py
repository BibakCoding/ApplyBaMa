from urllib.parse import unquote

from django.test import TestCase
from django.urls import reverse

from core.models import Application, CompanyProfile, User

from .views import get_managed_students


class DashboardAccessTests(TestCase):
	def setUp(self):
		self.student = User.objects.create_user(
			username="student", email="student@example.com", password="Password123!"
		)
		self.agent = User.objects.create_user(
			username="agent",
			email="agent@example.com",
			password="Password123!",
			user_type=User.UserType.AGENT,
		)

	def test_dashboard_requires_authentication(self):
		response = self.client.get(reverse("dashboard"))

		self.assertEqual(response.status_code, 302)
		# LOGIN_URL is a URL name rather than a path, so compare against the
		# resolved route and confirm the target survives as ?next=.
		self.assertTrue(response.url.startswith(reverse("login")))
		self.assertIn("next=", response.url)

	def test_deep_link_survives_the_login_bounce(self):
		response = self.client.get(reverse("dashboard"), {"page": "profile"})

		self.assertEqual(response.status_code, 302)
		# The requested page travels to the login form as ?next=, so the user is
		# returned to it instead of landing on the default dashboard page.
		self.assertIn(
			unquote(reverse("dashboard") + "?page=profile"), unquote(response.url)
		)

	def test_student_cannot_open_restricted_dashboard_page(self):
		self.client.force_login(self.student)

		response = self.client.get(reverse("dashboard_content", kwargs={"page": "my_students"}))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("dashboard"))

	def test_agent_managed_students_are_returned_distinctly(self):
		first_application = Application.objects.create(agent=self.agent, student=self.student)
		Application.objects.create(agent=self.agent, student=self.student)

		managed_students = list(get_managed_students(self.agent))

		self.assertEqual(managed_students, [first_application.student_id])

	def test_company_managed_students_are_returned_through_its_agents(self):
		company_user = User.objects.create_user(
			username="company",
			email="company@example.com",
			password="Password123!",
			user_type=User.UserType.COMPANY,
		)
		company = CompanyProfile.objects.create(
			user=company_user,
			company_name="Example Agency",
			company_email="agency@example.com",
			tax_number="TAX-1",
			phone="+905000000000",
		)
		agent_user = User.objects.create_user(
			username="company-agent",
			email="company-agent@example.com",
			password="Password123!",
			user_type=User.UserType.AGENT,
		)
		from core.models import AgentProfile

		AgentProfile.objects.create(user=agent_user, agency=company)
		application = Application.objects.create(agent=agent_user, student=self.student)

		self.assertEqual(list(get_managed_students(company_user)), [application.student_id])


class AddStudentPasswordControlTests(TestCase):
	"""The copy control's contract with static/js/pages/dashboard.js.

	The script finds the button by #copyPwdBtn and reads the two labels it needs
	from data attributes — static JS is never rendered as a template, so the
	translated strings have to come from the fragment. If those attributes are
	dropped, the copy loses its acknowledgement text instead of failing loudly.
	"""

	def setUp(self):
		self.company_user = User.objects.create_user(
			username="copy-company",
			email="copy-company@example.com",
			password="Password123!",
			user_type=User.UserType.COMPANY,
			# Unverified accounts get the read-only gate instead of the fragment.
			email_verified=True,
		)
		self.client.force_login(self.company_user)

	def test_add_student_fragment_wires_the_password_copy_button(self):
		response = self.client.get(
			reverse("dashboard_content", kwargs={"page": "my_students"})
		)
		html = response.content.decode()

		self.assertEqual(response.status_code, 200)
		self.assertIn('id="copyPwdBtn"', html)
		self.assertIn('class="copy-pwd-btn"', html)

		copy_title = html.split('data-copy-title="', 1)[1].split('"', 1)[0]
		copied_title = html.split('data-copied-title="', 1)[1].split('"', 1)[0]
		self.assertTrue(copy_title)
		self.assertTrue(copied_title)
		# The acknowledgement is its own string, not the default one echoed twice.
		self.assertNotEqual(copy_title, copied_title)

	def test_copy_labels_are_translated(self):
		from django.utils.translation import override

		with override("fa"):
			url = reverse("dashboard_content", kwargs={"page": "my_students"})
		html = self.client.get(url).content.decode()

		self.assertIn("کپی رمز عبور", html)
		self.assertIn("رمز عبور کپی شد", html)
