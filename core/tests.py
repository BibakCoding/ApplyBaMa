from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import (
	Application,
	City,
	Country,
	Notification,
	NotificationRecipient,
	Program,
	University,
	User,
	validate_document_file_extension,
	validate_image_file_extension,
)


class CoreModelTests(TestCase):
	def setUp(self):
		self.country = Country.objects.create(
			name="Turkey", language="Turkish", nationality="Turkish"
		)
		self.city = City.objects.create(country=self.country, name="Istanbul")
		self.university = University.objects.create(
			name="Example University", country=self.country, city=self.city
		)
		self.agent = User.objects.create_user(
			username="agent", email="agent@example.com", password="pass12345", user_type="agent"
		)
		self.student = User.objects.create_user(
			username="student", email="student@example.com", password="pass12345"
		)

	def test_country_and_city_string_representations(self):
		self.assertEqual(str(self.country), "Turkey")
		self.assertEqual(str(self.city), "Istanbul, Turkey")

	def test_program_prices_and_university_starting_fee(self):
		discounted = Program.objects.create(
			name="Computer Science",
			university=self.university,
			degree="bachelor",
			cash_fees=Decimal("12000.00"),
			offer=Decimal("9000.00"),
			language="English",
		)
		Program.objects.create(
			name="Business",
			university=self.university,
			degree="master",
			deposit_fee=Decimal("15000.00"),
			language="Turkish",
		)

		self.assertEqual(discounted.original_price, Decimal("12000.00"))
		self.assertEqual(discounted.display_price, Decimal("9000.00"))
		self.assertTrue(discounted.is_discounted)
		self.assertEqual(self.university.starting_fee, Decimal("9000.00"))
		self.assertEqual(set(self.university.available_languages), {"English", "Turkish"})
		self.assertEqual(self.university.programs_count, 2)

	def test_application_generates_unique_application_name(self):
		application = Application.objects.create(agent=self.agent, student=self.student)

		self.assertEqual(len(application.application_name), 10)
		self.assertEqual(application.application_name, application.application_name.upper())
		self.assertEqual(Application.objects.count(), 1)

	def test_representative_validation_only_allows_default_users(self):
		representative = User(
			username="company-representative",
			user_type=User.UserType.COMPANY,
			is_representative=True,
		)

		with self.assertRaises(ValidationError):
			representative.full_clean()

	def test_notification_recipient_queryset_filters_active_users(self):
		inactive = User.objects.create_user(
			username="inactive", email="inactive@example.com", is_active=False
		)
		notification = Notification.objects.create(
			title="Maintenance",
			message="Scheduled maintenance",
			sender=self.agent,
			recipient_type=Notification.RecipientType.DEFAULT_USERS,
		)

		NotificationRecipient.objects.create(notification=notification, user=self.student)
		NotificationRecipient.objects.create(notification=notification, user=inactive)

		self.assertEqual(list(notification.get_recipients_queryset()), [self.student])


class FileValidationTests(TestCase):
	def test_image_validator_accepts_supported_extension(self):
		validate_image_file_extension(SimpleUploadedFile("avatar.PNG", b"image"))

	def test_image_validator_rejects_unsupported_extension(self):
		with self.assertRaises(ValidationError):
			validate_image_file_extension(SimpleUploadedFile("avatar.txt", b"text"))

	def test_document_validator_accepts_supported_extension(self):
		validate_document_file_extension(SimpleUploadedFile("passport.pdf", b"pdf"))

	def test_document_validator_rejects_unsupported_extension(self):
		with self.assertRaises(ValidationError):
			validate_document_file_extension(SimpleUploadedFile("passport.exe", b"binary"))
