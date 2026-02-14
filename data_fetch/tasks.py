# data_fetch/tasks.py

import decimal
import time

import requests
import urllib3
from bs4 import BeautifulSoup
from celery import shared_task
from django.conf import settings
from django.db import IntegrityError
from selenium import webdriver
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.models import (
    Country,
    City,
    YearOption,
    Faculty,
    University,
    Program,
    TermOption,
)
from data_fetch.models import ConnectSID

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────── URLs ─────────────────────────────────────────────────────────────
LOGIN_URL = "https://info.studyfans.com/login"
UNIVERSITIES_URL = "https://info.studyfans.com/universities"
ALL_UNI_POST_URL = "https://info.studyfans.com/all-universities"
PROGRAMS_URL = "https://info.studyfans.com/programs"
ALL_PROGS_POST_URL = "https://info.studyfans.com/all-programs"

# Credentials pulled from settings.py
EMAIL = settings.SF_EMAIL
PASSWORD = settings.SF_PASSWORD

# ─────────── DataTables payload templates ─────────────────────────────────────
UNI_PAYLOAD_TEMPLATE = {
    "draw": "1",
    "columns[0][data]": "",
    "columns[0][name]": "",
    "columns[0][searchable]": "false",
    "columns[0][orderable]": "false",
    "columns[0][search][value]": "",
    "columns[0][search][regex]": "false",
    "columns[1][data]": "id",
    "columns[1][name]": "",
    "columns[1][searchable]": "true",
    "columns[1][orderable]": "true",
    "columns[1][search][value]": "",
    "columns[1][search][regex]": "false",
    "columns[2][data]": "name",
    "columns[2][name]": "",
    "columns[2][searchable]": "true",
    "columns[2][orderable]": "true",
    "columns[2][search][value]": "",
    "columns[2][search][regex]": "false",
    "columns[3][data]": "country_name",
    "columns[3][name]": "",
    "columns[3][searchable]": "true",
    "columns[3][orderable]": "true",
    "columns[3][search][value]": "",
    "columns[3][search][regex]": "false",
    "columns[4][data]": "city_name",
    "columns[4][name]": "",
    "columns[4][searchable]": "true",
    "columns[4][orderable]": "true",
    "columns[4][search][value]": "",
    "columns[4][search][regex]": "false",
    "columns[5][data]": "website",
    "columns[5][name]": "",
    "columns[5][searchable]": "true",
    "columns[5][orderable]": "true",
    "columns[5][search][value]": "",
    "columns[5][search][regex]": "false",
    "columns[6][data]": "campus_address",
    "columns[6][name]": "",
    "columns[6][searchable]": "true",
    "columns[6][orderable]": "true",
    "columns[6][search][value]": "",
    "columns[6][search][regex]": "false",
    "order[0][column]": "1",  # order by ID descending
    "order[0][dir]": "desc",
    "search[value]": "",
    "search[regex]": "false",
}

PROG_PAYLOAD_TEMPLATE = {
    "draw": "1",
    "columns[0][data]": "",
    "columns[0][name]": "",
    "columns[0][searchable]": "false",
    "columns[0][orderable]": "false",
    "columns[0][search][value]": "",
    "columns[0][search][regex]": "false",
    "columns[1][data]": "",
    "columns[1][name]": "",
    "columns[1][searchable]": "false",
    "columns[1][orderable]": "false",
    "columns[1][search][value]": "",
    "columns[1][search][regex]": "false",
    "columns[2][data]": "id",
    "columns[2][name]": "",
    "columns[2][searchable]": "true",
    "columns[2][orderable]": "true",
    "columns[2][search][value]": "",
    "columns[2][search][regex]": "false",
    "columns[3][data]": "program_name",
    "columns[3][name]": "",
    "columns[3][searchable]": "true",
    "columns[3][orderable]": "true",
    "columns[3][search][value]": "",
    "columns[3][search][regex]": "false",
    "columns[4][data]": "university_id",
    "columns[4][name]": "",
    "columns[4][searchable]": "true",
    "columns[4][orderable]": "true",
    "columns[4][search][value]": "",
    "columns[4][search][regex]": "false",
    "order[0][column]": "2",
    "order[0][dir]": "desc",
    "search[value]": "",
    "search[regex]": "false",
}


def parse_decimal(value_str, default=decimal.Decimal('0.00')):
    """
    Safely parse a string into a Decimal. Returns `default` on failure.
    """
    try:
        return decimal.Decimal(value_str)
    except Exception:
        return default


def parse_html_table(html: str) -> dict:
    """
    Given an HTML <table> snippet (or <figure> containing a table),
    returns a dict of { first_column_text: second_column_text, … }.
    """
    result = {}
    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return result

    for tr in table.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue
        key = tds[0].get_text(separator=" ", strip=True)
        val = tds[1].get_text(separator=" ", strip=True)
        if key:
            result[key] = val
    return result


def parse_required_documents(html: str) -> list:
    """
    Given the raw HTML for 'required_documents', which contains <ol><li>…</li>…,
    returns a list of plain text strings.
    """
    docs = []
    if not html:
        return docs

    soup = BeautifulSoup(html, "html.parser")
    for li in soup.find_all("li"):
        text = li.get_text(separator=" ", strip=True)
        if text:
            docs.append(text)
    return docs


def parse_deposit_info(html: str) -> dict:
    """
    Given the raw HTML for 'deposit', which is multiple <p> lines like
    "<span>deposit for Medicine: </span><span>$14.850</span>", return a dict:
    { "deposit for Medicine": "14.850", … }
    """
    deposits = {}
    if not html:
        return deposits

    soup = BeautifulSoup(html, "html.parser")
    for p in soup.find_all("p"):
        spans = p.find_all("span")
        if len(spans) >= 2:
            label = spans[0].get_text(separator=" ", strip=True).rstrip(":")
            amount = spans[1].get_text(separator=" ", strip=True).lstrip("$")
            if label and amount:
                deposits[label] = amount
    return deposits


def parse_discount(html: str) -> str:
    """
    Returns the plain text of a discount HTML block (only one <p> or so).
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_installment(html: str) -> str:
    """
    Returns the plain text for 'installment_payment' html.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_preparatory_year(html: str) -> dict:
    """
    Given the raw HTML for 'preparatory_year', which is a table listing
    prep‐school fees for different faculties (or just a statement),
    returns a dict mapping e.g. "Medicine" -> "13200", etc.
    """
    prep = {}
    if not html:
        return prep

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return prep
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) >= 2:
            field_label = tds[0].get_text(separator=" ", strip=True)
            value = tds[1].get_text(separator=" ", strip=True)
            if field_label and value:
                prep[field_label] = value
    return prep


def _get_or_create_connect_sid():
    """
    Try re‐using an existing ConnectSID. If none or expired, return None.
    """
    try:
        existing = ConnectSID.objects.latest('fetched_at')
    except ConnectSID.DoesNotExist:
        return None

    sid = existing.sid
    sess = requests.Session()
    sess.verify = False
    sess.cookies.set("connect.sid", sid, domain="info.studyfans.com", path="/")
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    try:
        r = sess.get(UNIVERSITIES_URL, allow_redirects=False, timeout=10, verify=False)
        if r.status_code == 200:
            return sid
        else:
            existing.delete()
            return None
    except requests.RequestException:
        existing.delete()
        return None


def _selenium_login_and_store_sid(timeout=20, max_retries=2):
    """
    Use Selenium to log in, capture connect.sid, store in DB, and return it.
    """
    for attempt in range(1, max_retries + 1):
        driver = None
        try:
            opts = ChromeOptions()
            opts.add_argument("--headless")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--ignore-certificate-errors")
            opts.add_argument("--ignore-ssl-errors")
            opts.add_argument("--disable-web-security")
            driver = webdriver.Chrome(options=opts)

            driver.get(LOGIN_URL)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )

            driver.find_element(By.NAME, "email").send_keys(EMAIL)
            driver.find_element(By.NAME, "password").send_keys(PASSWORD)
            time.sleep(1)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()

            WebDriverWait(driver, timeout).until(
                lambda d: "/login" not in d.current_url
            )

            cookies = driver.get_cookies()
            driver.quit()

            sid_value = None
            for c in cookies:
                if c.get("name") == "connect.sid":
                    sid_value = c.get("value")
                    break
            if not sid_value:
                raise RuntimeError("Login succeeded but no connect.sid found.")

            ConnectSID.objects.all().delete()
            ConnectSID.objects.create(sid=sid_value)
            return sid_value

        except (WebDriverException, TimeoutException, RuntimeError) as e:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            if attempt == max_retries:
                raise RuntimeError(
                    f"Selenium login failed after {max_retries} attempts: {e}"
                )
            time.sleep(2)

    raise RuntimeError("Unreachable code in _selenium_login_and_store_sid()")


def _get_authenticated_session():
    """
    Return a requests.Session() with a valid connect.sid (reusing or refreshing).
    """
    sid = _get_or_create_connect_sid()
    if not sid:
        sid = _selenium_login_and_store_sid()

    sess = requests.Session()
    sess.verify = False
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    sess.cookies.set("connect.sid", sid, domain="info.studyfans.com", path="/")
    return sess


@shared_task(bind=True)
def refresh_universities_and_programs(self):
    """
    Celery task (every 20 minutes) that:
      1) Logs in (or reuses connect.sid).
      2) Fetches /all-universities, parses HTML → stores structured data.
      3) Deletes any stale universities.
      4) Fetches /all-programs, upserts each program.
      5) Deletes any stale programs.
    """
    start_time = time.perf_counter()
    try:
        session = _get_authenticated_session()

        # ─────────── STEP A: FETCH & SYNC UNIVERSITIES ──────────────────────
        fetched_uni_ids = set()
        limit = 7000
        chunk_size = 1000

        for start in range(0, limit, chunk_size):
            payload = {**UNI_PAYLOAD_TEMPLATE}
            payload["start"] = str(start)
            payload["length"] = str(chunk_size)

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://info.studyfans.com",
                "Referer": UNIVERSITIES_URL,
            }

            r = session.post(
                ALL_UNI_POST_URL,
                data=payload,
                headers=headers,
                allow_redirects=False,
                verify=False,
                timeout=15
            )
            if r.status_code == 302:
                raise RuntimeError(
                    "Redirected to login when fetching universities—session expired."
                )
            if r.status_code != 200:
                raise RuntimeError(
                    f"Fetch universities chunk {start} failed: HTTP {r.status_code}"
                )

            data_list = r.json().get("data", [])
            if not data_list:
                break

            for row in data_list:
                # ─────── Extract country & city external IDs ───────
                country_ext_id = int(row.get("country.id") or 0)
                city_ext_id = int(row.get("city.id") or 0)

                uni_ext_id = int(row.get("id") or 0)
                fetched_uni_ids.add(uni_ext_id)

                country_name = (row.get("country.name") or "").strip()
                city_name = (row.get("city.name") or "").strip()
                uni_name = (row.get("name") or "").strip()
                website = (row.get("website") or "").strip()
                address = (row.get("campus_address") or "").strip()

                # ─── Upsert Country by external_id → name‐match → create ───
                if country_ext_id:
                    try:
                        country_obj = Country.objects.get(external_id=country_ext_id)
                        created_country = False
                    except Country.DoesNotExist:
                        try:
                            country_obj = Country.objects.get(name__iexact=country_name)
                            country_obj.external_id = country_ext_id
                            country_obj.save()
                            created_country = False
                        except Country.DoesNotExist:
                            country_obj = Country.objects.create(
                                external_id=country_ext_id,
                                name=country_name,
                            )
                            created_country = True
                else:
                    country_obj, created_country = Country.objects.get_or_create(
                        name__iexact=country_name,
                        defaults={"name": country_name}
                    )

                # ─── Upsert City by external_id → name+country → create ───
                if city_ext_id:
                    try:
                        city_obj = City.objects.get(external_id=city_ext_id)
                        created_city = False
                    except City.DoesNotExist:
                        # Try to match an existing city by (country, name)
                        try:
                            city_obj = City.objects.get(
                                country=country_obj,
                                name=city_name
                            )
                            # Assign external_id if not already set
                            if city_obj.external_id is None:
                                city_obj.external_id = city_ext_id
                                city_obj.save()
                            created_city = False
                        except City.DoesNotExist:
                            # Create new—catch IntegrityError if a (country, name) row was added in the meantime
                            try:
                                city_obj = City.objects.create(
                                    external_id=city_ext_id,
                                    country=country_obj,
                                    name=city_name,
                                )
                                created_city = True
                            except IntegrityError:
                                # Another process must have created it, so fetch by (country, name)
                                city_obj = City.objects.get(
                                    country=country_obj,
                                    name=city_name
                                )
                                if city_obj.external_id is None:
                                    city_obj.external_id = city_ext_id
                                    city_obj.save()
                                created_city = False
                else:
                    city_obj, created_city = City.objects.get_or_create(
                        country=country_obj,
                        name=city_name,
                        defaults={"name": city_name}
                    )

                # ─── Parse all HTML fragments ───
                imp_dates_html = (row.get("important_dates") or "").strip()
                exams_dates_html = (row.get("exams_dates") or "").strip()
                exams_score_html = (row.get("exams_score") or "").strip()
                req_docs_html = (row.get("required_documents") or "").strip()
                deposit_html = (row.get("deposit") or "").strip()
                bros_disc_html = (row.get("brothers_discount") or "").strip()
                cash_disc_html = (row.get("cash_discount") or "").strip()
                inst_html = (row.get("installment_payment") or "").strip()
                prep_year_html = (row.get("preparatory_year") or "").strip()

                extra_fields_list = row.get("fields", []) or []

                important_dates_parsed = parse_html_table(imp_dates_html)
                exams_dates_parsed = parse_html_table(exams_dates_html)
                exams_score_parsed = parse_html_table(exams_score_html)
                required_documents_parsed = parse_required_documents(req_docs_html)
                deposit_info_parsed = parse_deposit_info(deposit_html)
                brothers_discount_parsed = parse_discount(bros_disc_html)
                cash_discount_parsed = parse_discount(cash_disc_html)
                installment_parsed = parse_installment(inst_html)
                preparatory_year_parsed = parse_preparatory_year(prep_year_html)

                parsed_data = {
                    "important_dates": important_dates_parsed,
                    "exams_dates": exams_dates_parsed,
                    "exams_scores": exams_score_parsed,
                    "required_documents": required_documents_parsed,
                    "deposit_info": deposit_info_parsed,
                    "brothers_discount": brothers_discount_parsed,
                    "cash_discount": cash_discount_parsed,
                    "installment_payment": installment_parsed,
                    "preparatory_year": preparatory_year_parsed,
                    "fields_array": extra_fields_list,
                }

                # ─── Upsert University by external_id → name → create ───
                try:
                    uni_obj = University.objects.get(external_id=uni_ext_id)
                    created_uni = False
                except University.DoesNotExist:
                    try:
                        uni_obj = University.objects.get(name__iexact=uni_name)
                        uni_obj.external_id = uni_ext_id
                        created_uni = False
                    except University.DoesNotExist:
                        uni_obj = University.objects.create(
                            external_id=uni_ext_id,
                            name=uni_name,
                            country=country_obj,
                            city=city_obj,
                            website=website,
                            address=address,
                            parsed_data=parsed_data,
                        )
                        created_uni = True

                if not created_uni and uni_obj.external_id != uni_ext_id:
                    uni_obj.external_id = uni_ext_id

                fields_to_update = {
                    "country": country_obj,
                    "city": city_obj,
                    "website": website,
                    "address": address,
                    "parsed_data": parsed_data,
                }
                changed = False
                for field_name, new_val in fields_to_update.items():
                    old_val = getattr(uni_obj, field_name)
                    if old_val != new_val:
                        setattr(uni_obj, field_name, new_val)
                        changed = True

                if created_uni or changed:
                    uni_obj.save()

            if len(data_list) < chunk_size:
                break

        # Delete any universities not returned upstream
        University.objects.exclude(external_id__in=fetched_uni_ids).delete()

        # ─────────── STEP B: FETCH & SYNC PROGRAMS ──────────────────────────
        fetched_prog_ids = set()
        limit = 7000
        chunk_size = 1000

        for start in range(0, limit, chunk_size):
            payload = {**PROG_PAYLOAD_TEMPLATE}
            payload["start"] = str(start)
            payload["length"] = str(chunk_size)

            cookies_dict = session.cookies.get_dict()
            csrf_token = None
            for name, val in cookies_dict.items():
                if "csrf" in name.lower():
                    csrf_token = val
                    break

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://info.studyfans.com",
                "Referer": PROGRAMS_URL,
            }
            if csrf_token:
                headers["X-XSRF-TOKEN"] = csrf_token

            r = session.post(
                ALL_PROGS_POST_URL,
                data=payload,
                headers=headers,
                allow_redirects=False,
                verify=False,
                timeout=15
            )
            if r.status_code == 302:
                raise RuntimeError(
                    "Redirected to login when fetching programs—session expired."
                )
            if r.status_code != 200:
                raise RuntimeError(
                    f"Fetch programs chunk {start} failed: HTTP {r.status_code}"
                )

            data_list = r.json().get("data", [])
            if not data_list:
                break

            for row in data_list:
                ext_id = int(row.get("id") or 0)
                fetched_prog_ids.add(ext_id)

                prog_name = (row.get("program_name") or "").strip()
                uni_id = int(row.get("university_id") or 0)
                status_str = (row.get("status") or "").strip().lower()
                faculty_name = (row.get("faculty_name") or "").strip()
                degree_name = (row.get("degree_name") or "").strip().lower()
                years_value = (row.get("years") or "").strip()
                deposit_fee = (row.get("deposit_fee") or "0").strip()
                prep_fee = (row.get("prep_school_fee") or "0").strip()
                cash_fees = (row.get("cash_fees") or "0").strip()
                semester_fee = (row.get("semester_fee") or "0").strip()
                deposit = (row.get("deposit") or "0").strip()
                offer = (row.get("offer") or "0").strip()

                fees_list = row.get("programs_fees", []) or []
                term_label = None
                if fees_list:
                    term_label = (fees_list[0].get("semester") or "").strip()

                status_map = {
                    'available': Program.StatusChoices.AVAILABLE,
                    'near_to_close': Program.StatusChoices.NEAR_TO_CLOSE,
                    'quota_full': Program.StatusChoices.QUOTA_FULL,
                    'closed': Program.StatusChoices.CLOSED,
                }
                prog_status = status_map.get(status_str, Program.StatusChoices.AVAILABLE)

                try:
                    uni_obj = University.objects.get(external_id=uni_id)
                except University.DoesNotExist:
                    continue

                fac_obj, _ = Faculty.objects.get_or_create(
                    name__iexact=faculty_name,
                    defaults={"name": faculty_name}
                )

                year_obj, _ = YearOption.objects.get_or_create(value=years_value)
                if year_obj not in fac_obj.year_options.all():
                    fac_obj.year_options.add(year_obj)

                deg_map = {
                    'associate': 'associate',
                    'bachelor': 'bachelor',
                    'master': 'master',
                    'phd': 'phd',
                    'integrated_phd': 'integrated_phd',
                }
                degree_key = deg_map.get(degree_name, 'bachelor')

                term_obj = None
                if term_label:
                    term_obj, _ = TermOption.objects.get_or_create(label=term_label)

                try:
                    prog_obj = Program.objects.get(external_id=ext_id)
                    created_prog = False
                except Program.DoesNotExist:
                    try:
                        prog_obj = Program.objects.get(
                            name__iexact=prog_name,
                            university=uni_obj
                        )
                        prog_obj.external_id = ext_id
                        prog_obj.status = prog_status
                        prog_obj.faculty = fac_obj
                        prog_obj.degree = degree_key
                        prog_obj.duration = years_value
                        prog_obj.deposit_fee = parse_decimal(deposit_fee)
                        prog_obj.prep_school_fee = parse_decimal(prep_fee)
                        prog_obj.cash_fees = parse_decimal(cash_fees)
                        prog_obj.semester_fee = parse_decimal(semester_fee)
                        prog_obj.deposit = parse_decimal(deposit)
                        prog_obj.offer = parse_decimal(offer)
                        prog_obj.term = term_obj
                        prog_obj.save()
                        created_prog = False
                    except Program.DoesNotExist:
                        prog_obj = Program.objects.create(
                            external_id=ext_id,
                            name=prog_name,
                            university=uni_obj,
                            status=prog_status,
                            faculty=fac_obj,
                            degree=degree_key,
                            duration=years_value,
                            deposit_fee=parse_decimal(deposit_fee),
                            prep_school_fee=parse_decimal(prep_fee),
                            cash_fees=parse_decimal(cash_fees),
                            semester_fee=parse_decimal(semester_fee),
                            deposit=parse_decimal(deposit),
                            offer=parse_decimal(offer),
                            term=term_obj,
                        )
                        created_prog = True

            if len(data_list) < chunk_size:
                break

        Program.objects.exclude(external_id__in=fetched_prog_ids).delete()

        elapsed = time.perf_counter() - start_time
        return {
            "status": "success",
            "universities_fetched": len(fetched_uni_ids),
            "programs_fetched": len(fetched_prog_ids),
            "elapsed_seconds": round(elapsed, 2),
        }

    except Exception as exc:
        # Retry up to 2 more times if something goes wrong
        raise self.retry(exc=exc, countdown=60, max_retries=2)
