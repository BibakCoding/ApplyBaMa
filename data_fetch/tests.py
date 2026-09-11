from decimal import Decimal

from django.test import SimpleTestCase

from .tasks import (
	parse_decimal,
	parse_deposit_info,
	parse_discount,
	parse_html_table,
	parse_installment,
	parse_preparatory_year,
	parse_required_documents,
)


class DataFetchParserTests(SimpleTestCase):
	def test_parse_decimal_handles_currency_and_invalid_values(self):
		self.assertEqual(parse_decimal("$12,345.67"), Decimal("12345.67"))
		self.assertEqual(parse_decimal("not-a-number"), Decimal("0.00"))
		self.assertEqual(parse_decimal(""), Decimal("0.00"))

	def test_parse_html_table_returns_key_value_pairs(self):
		html = "<table><tr><th>Faculty</th><th>Fee</th></tr><tr><td>Medicine</td><td>12000</td></tr></table>"

		self.assertEqual(parse_html_table(html), {"Faculty": "Fee", "Medicine": "12000"})

	def test_parse_required_documents_returns_plain_text_items(self):
		html = "<ol><li>Passport <strong>copy</strong></li><li>Diploma</li></ol>"

		self.assertEqual(parse_required_documents(html), ["Passport copy", "Diploma"])

	def test_parse_fee_and_description_helpers_strip_markup(self):
		self.assertEqual(
			parse_deposit_info("<p><span>Medicine: </span><span>$14,850</span></p>"),
			{"Medicine": "14,850"},
		)
		self.assertEqual(parse_discount("<p>20% scholarship</p>"), "20% scholarship")
		self.assertEqual(parse_installment("<p>Pay in two installments</p>"), "Pay in two installments")

	def test_parse_preparatory_year_reads_table_rows(self):
		html = "<table><tr><td>Medicine</td><td>13200</td></tr></table>"

		self.assertEqual(parse_preparatory_year(html), {"Medicine": "13200"})
