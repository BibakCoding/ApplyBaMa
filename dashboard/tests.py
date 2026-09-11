from django.conf import settings
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
		self.assertTrue(response.url.startswith(settings.LOGIN_URL))

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
