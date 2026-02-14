# programs/importer.py

import decimal

from django.db import transaction

from core.models import (
    Country,
    City,
    YearOption,
    Faculty,
    University,
    Program,
    TermOption,
)


# Example single JSON record, for reference:
#
# {
#   "id": 5990,
#   "years": "4",
#   "deposit_fee": "1000",
#   "deposit_note": "",
#   "prep_school_fee": "3250",
#   "prep_school_note": "",
#   "note": "",
#   "program_name": "Midwifery",
#   "language_name": "Turkish",
#   "university_id": 32,
#   "university_name": "ISTANBUL TOPKAPI UNIVERSITY",
#   "country_name": "Turkey",
#   "city_name": "İstanbul",
#   "university_website": "https://www.topkapi.edu.tr/",
#   "faculty_name": "Health.Sciences",
#   "degree_name": "Bachelor",
#   "currency_name": "USD",
#   "campus_name": "Kazlıçeşme Campus",
#   "campus_address": "Prof. Muammer Aksoy Cad. No: 10 Kazlıçeşme / Zeytinburnu / Istanbul",
#   "programs_fees": [
#     {
#       "id": 22498,
#       "semester": "2025 Full Semester",
#       "status": "Available",
#       "fees": "6500",
#       "discounted_fees": "3250",
#       "cash_fees": "3250"
#     }
#   ]
# }

def parse_decimal(value_str, default=decimal.Decimal('0.00')):
    """
    Safely parse a string into a Decimal. Returns `default` on failure or empty.
    """
    try:
        return decimal.Decimal(value_str)
    except Exception:
        return default


@transaction.atomic
def import_program_record(record):
    """
    Given one JSON‐decoded record (a dict like the example above),
    create or update the corresponding Country, City, University,
    Faculty, YearOption, TermOption, and Program objects.
    """

    # 1) COUNTRY
    country_name = record.get("country_name", "").strip()
    if not country_name:
        raise ValueError("Missing country_name in record")
    country_obj, _ = Country.objects.get_or_create(
        name__iexact=country_name,
        defaults={"name": country_name}
    )

    # 2) CITY (tied to that Country)
    city_name = record.get("city_name", "").strip()
    if not city_name:
        raise ValueError("Missing city_name in record")
    city_obj, _ = City.objects.get_or_create(
        country=country_obj,
        name__iexact=city_name,
        defaults={"name": city_name}
    )

    # 3) UNIVERSITY
    #
    # We have an external `university_id` (32) and `university_name`.
    # Our University model does not have a field for “external ID,”
    # so we’ll match by exact name (case‐insensitive). If you prefer, you
    # could add a field `external_id = models.IntegerField(unique=True, null=True, blank=True)`
    # to University and use that. For now, we’ll do get_or_create by name.
    uni_name = record.get("university_name", "").strip()
    if not uni_name:
        raise ValueError("Missing university_name in record")

    uni_obj, created = University.objects.get_or_create(
        name__iexact=uni_name,
        defaults={
            "name": uni_name,
            "country": country_obj,
            "city": city_obj,
            "website": record.get("university_website", "").strip(),
            "address": record.get("campus_address", "").strip(),
        }
    )
    # If the university already existed but we want to update fields:
    if not created:
        changed = False
        web = record.get("university_website", "").strip()
        addr = record.get("campus_address", "").strip()
        if uni_obj.website != web:
            uni_obj.website = web
            changed = True
        if uni_obj.address != addr:
            uni_obj.address = addr
            changed = True
        if uni_obj.country_id != country_obj.id:
            uni_obj.country = country_obj
            changed = True
        if uni_obj.city_id != city_obj.id:
            uni_obj.city = city_obj
            changed = True
        if changed:
            uni_obj.save()

    # 4) FACULTY
    fac_name = record.get("faculty_name", "").strip()
    if not fac_name:
        raise ValueError("Missing faculty_name in record")

    fac_obj, _ = Faculty.objects.get_or_create(
        name__iexact=fac_name,
        defaults={"name": fac_name}
    )

    # 5) YEAR OPTION (duration)
    years_value = record.get("years", "").strip()  # e.g. "4"
    if not years_value:
        raise ValueError("Missing years (duration) in record")
    year_option_obj, _ = YearOption.objects.get_or_create(
        value=years_value
    )
    # If the Faculty doesn’t already reference this YearOption, add it
    if year_option_obj not in fac_obj.year_options.all():
        fac_obj.year_options.add(year_option_obj)

    # 6) DEGREE
    # Normalize degree_name to one of Program.DEGREE_CHOICES
    deg_map = {
        'associate': 'associate',
        'bachelor': 'bachelor',
        'master': 'master',
        'phd': 'phd',
        'integrated_phd': 'integrated_phd',
    }
    raw_degree = record.get("degree_name", "").strip().lower()
    degree_key = deg_map.get(raw_degree)
    if degree_key is None:
        # If it’s not one of our exact keys, fallback to 'bachelor' or raise
        degree_key = 'bachelor'
    # 7) TERM OPTION - parse from programs_fees[0]["semester"] if possible
    term_label = None
    fees_array = record.get("programs_fees", [])
    if fees_array and isinstance(fees_array, list):
        first_fee = fees_array[0]
        term_label = first_fee.get("semester", "").strip()  # e.g. "2025 Full Semester"
    term_obj = None
    if term_label:
        term_obj, _ = TermOption.objects.get_or_create(label=term_label)

    # 8) PROGRAM DETAILS (check if already exists by name+university)
    prog_name = record.get("program_name", "").strip()
    if not prog_name:
        raise ValueError("Missing program_name in record")

    # Try to find an existing Program with the same name and university
    prog_obj, prog_created = Program.objects.get_or_create(
        name__iexact=prog_name,
        university=uni_obj,
        defaults={
            "name": prog_name,
            "status": Program.StatusChoices.AVAILABLE,  # default
            "faculty": fac_obj,
            "degree": degree_key,
            "duration": years_value,
            "deposit_fee": parse_decimal(record.get("deposit_fee", "0")),
            "prep_school_fee": parse_decimal(record.get("prep_school_fee", "0")),
            "cash_fees": parse_decimal(first_fee.get("cash_fees", "0")) if fees_array else decimal.Decimal("0"),
            "semester_fee": parse_decimal(first_fee.get("fees", "0")) if fees_array else decimal.Decimal("0"),
            "deposit": parse_decimal(first_fee.get("discounted_fees", "0")) if fees_array else decimal.Decimal("0"),
            "offer": parse_decimal(first_fee.get("discounted_fees", "0")) if fees_array else decimal.Decimal("0"),
            "term": term_obj,
        }
    )

    # 9) If the Program already existed, update any changed fields
    if not prog_created:
        changed = False

        # status – we can infer from programs_fees[0]["status"] if it exists
        if fees_array:
            raw_status = first_fee.get("status", "").strip().lower()
            status_map = {
                'available': Program.StatusChoices.AVAILABLE,
                'near_to_close': Program.StatusChoices.NEAR_TO_CLOSE,
                'quota_full': Program.StatusChoices.QUOTA_FULL,
                'closed': Program.StatusChoices.CLOSED,
            }
            new_status = status_map.get(raw_status, Program.StatusChoices.AVAILABLE)
            if prog_obj.status != new_status:
                prog_obj.status = new_status
                changed = True

        # Check each numeric/foreign‐key field for changes
        new_vals = {
            "faculty": fac_obj,
            "degree": degree_key,
            "duration": years_value,
            "deposit_fee": parse_decimal(record.get("deposit_fee", "0")),
            "prep_school_fee": parse_decimal(record.get("prep_school_fee", "0")),
            "cash_fees": parse_decimal(first_fee.get("cash_fees", "0")) if fees_array else decimal.Decimal("0"),
            "semester_fee": parse_decimal(
                first_fee.get("fees", "0")) if fees_array else prog_obj.semester_fee or decimal.Decimal("0"),
            "deposit": parse_decimal(
                first_fee.get("discounted_fees", "0")) if fees_array else prog_obj.deposit or decimal.Decimal("0"),
            "offer": parse_decimal(
                first_fee.get("discounted_fees", "0")) if fees_array else prog_obj.offer or decimal.Decimal("0"),
            "term": term_obj,
        }
        for field, new_val in new_vals.items():
            old_val = getattr(prog_obj, field)
            # Compare carefully for decimals / foreign keys
            if old_val != new_val:
                setattr(prog_obj, field, new_val)
                changed = True

        if changed:
            prog_obj.save()

    return prog_obj
