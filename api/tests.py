from django.test import TestCase
from django.urls import reverse

from core.models import City, Country


class CityListApiTests(TestCase):
	def setUp(self):
		self.country = Country.objects.create(name="Turkey")
		self.istanbul = City.objects.create(country=self.country, name="Istanbul")
		self.ankara = City.objects.create(country=self.country, name="Ankara")

	def test_cities_are_returned_in_name_order(self):
		response = self.client.get(reverse("api-cities"), {"country_id": self.country.pk})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json(),
			[
				{"id": self.ankara.pk, "name": "Ankara"},
				{"id": self.istanbul.pk, "name": "Istanbul"},
			],
		)

	def test_missing_country_id_returns_bad_request(self):
		response = self.client.get(reverse("api-cities"))

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json(), {"error": "Missing country_id"})

	def test_invalid_country_id_returns_bad_request(self):
		response = self.client.get(reverse("api-cities"), {"country_id": "invalid"})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json(), {"error": "Invalid country_id"})
