# data_fetch/tasks.py

import decimal
import json
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
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
    Strips commas and currency symbols that would cause InvalidOperation.
    """
    try:
        if not value_str:
            return default
        # Remove commas and currency symbols which cause InvalidOperation
        clean_str = str(value_str).replace(",", "").replace("$", "").strip()
        if not clean_str:
            return default
        return decimal.Decimal(clean_str)
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
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })
    sess.cookies["connect.sid"] = sid
    try:
        # Visiting the main page or dashboard to check session validity
        r = sess.get(UNIVERSITIES_URL, allow_redirects=False, timeout=10, verify=False)
        if r.status_code == 200:
            return sid
        else:
            existing.delete()
            return None
    except requests.RequestException:
        existing.delete()
        return None

def _selenium_login_and_store_sid(timeout=45, max_retries=2):
    """
    Use Selenium to log in, capture connect.sid, store in DB, and return it.
    Includes diagnostic fallbacks if the server rejects the login attempt.
    """
    for attempt in range(1, max_retries + 1):
        driver = None
        try:
            opts = ChromeOptions()

            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--disable-background-networking")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--force-device-scale-factor=1")
            opts.add_argument("--ignore-certificate-errors")
            opts.add_argument("--ignore-ssl-errors")
            opts.add_argument("--disable-web-security")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=opts)

            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                      get: () => undefined
                    })
                """
            })

            driver.get(LOGIN_URL)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "email")))

            # Capture initial state
            initial_url = driver.current_url
            initial_sid = None
            for c in driver.get_cookies():
                if c['name'] == 'connect.sid':
                    initial_sid = c['value']
                    break

            time.sleep(2) # Hydrate

            email_elem = driver.find_element(By.NAME, "email")
            pwd_elem = driver.find_element(By.NAME, "password")

            email_elem.clear()
            email_elem.send_keys(EMAIL)
            pwd_elem.clear()
            pwd_elem.send_keys(PASSWORD)

            time.sleep(1)

            # Strategy 1: JS Click
            try:
                submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                driver.execute_script("arguments[0].click();", submit_btn)
            except Exception:
                pass

            time.sleep(2)

            # Strategy 2: If nothing changed, press ENTER on the password field
            current_url = driver.current_url
            current_sid = None
            for c in driver.get_cookies():
                if c['name'] == 'connect.sid':
                    current_sid = c['value']
                    break

            if current_url == initial_url and current_sid == initial_sid:
                print("[Selenium] JS Click didn't trigger login. Trying ENTER key...")
                pwd_elem.send_keys(Keys.RETURN)
                time.sleep(2)

            # Wait for successful login
            def login_successful(d):
                if "/login" not in d.current_url:
                    return True
                for c in d.get_cookies():
                    if c['name'] == 'connect.sid' and c['value'] != initial_sid:
                        return True
                return False

            try:
                WebDriverWait(driver, timeout).until(login_successful)
                time.sleep(3) # Wait for dashboard XSRF tokens
            except TimeoutException:
                # Login failed. Diagnose why.
                screenshot_path = "login_failed_diagnostic.png"
                driver.save_screenshot(screenshot_path)
                print(f"\n[!] Selenium Login FAILED. Screenshot saved to: {screenshot_path}")

                # Extract visible error messages
                error_msgs = []
                try:
                    for selector in [".alert-danger", ".error-message", "[role='alert']", ".invalid-feedback", ".text-red-500", ".text-danger"]:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            text = el.text.strip()
                            if text:
                                error_msgs.append(text)
                except Exception:
                    pass

                if error_msgs:
                    print(f"[!] Server returned errors: {error_msgs}")
                else:
                    print("[!] No visible error text found. Check the screenshot for CAPTCHAs or Cloudflare blocks.")

                raise RuntimeError("Login rejected by server. Check diagnostic screenshot.")

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
                raise RuntimeError(f"Selenium login failed after {max_retries} attempts: {e}")
            time.sleep(5)

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
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest"
    })
    # Use simple dictionary assignment for the cookie to avoid domain matching quirks in requests
    sess.cookies["connect.sid"] = sid

    return sess

def _export_data_to_file():
    """
    Exports all active universities and programs to a JSON file
    located at BASE_DIR / 'data' / 'export.json'.
    Safely handles Decimal types and missing ForeignKey relationships.
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, 'export.json')

    universities = University.objects.filter(is_active=True).select_related('country', 'city')
    programs = Program.objects.filter(is_active=True).select_related('university', 'faculty', 'term')

    export_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "universities_count": universities.count(),
        "programs_count": programs.count(),
        "universities": [],
        "programs": []
    }

    for uni in universities:
        export_data["universities"].append({
            "id": uni.id,
            "external_id": uni.external_id,
            "name": uni.name,
            "country": uni.country.name if uni.country else None,
            "city": uni.city.name if uni.city else None,
            "website": uni.website,
            "address": uni.address,
            "logo": uni.logo.url if uni.logo else None,
            "parsed_data": uni.parsed_data,
            "sector": uni.sector,
            "founded_in": uni.founded_in,
        })

    for prog in programs:
        export_data["programs"].append({
            "id": prog.id,
            "external_id": prog.external_id,
            "name": prog.name,
            "university_id": prog.university.id,
            "university_name": prog.university.name,
            "faculty": prog.faculty.name if prog.faculty else None,
            "degree": prog.degree,
            "duration": prog.duration,
            "status": prog.status,
            "deposit_fee": str(prog.deposit_fee),
            "prep_school_fee": str(prog.prep_school_fee),
            "cash_fees": str(prog.cash_fees),
            "semester_fee": str(prog.semester_fee) if prog.semester_fee else None,
            "deposit": str(prog.deposit),
            "offer": str(prog.offer) if prog.offer else None,
            "term": prog.term.label if prog.term else None,
            "language": prog.language,
            "currency": prog.currency,
        })

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=4)

    return file_path

@shared_task(bind=True)
def refresh_universities_and_programs(self):
    start_time = time.perf_counter()

    try:
        session = _get_authenticated_session()

        # ─────────── STEP 1: DOWNLOAD ALL DATA INTO MEMORY ──────────────────
        # We do ALL network requests first, so we don't hold DB locks while waiting for the internet.
        all_uni_data = []
        limit, chunk_size = 7000, 1000

        for start in range(0, limit, chunk_size):
            payload = {**UNI_PAYLOAD_TEMPLATE, "start": str(start), "length": str(chunk_size)}
            r = session.post(ALL_UNI_POST_URL, data=payload, headers={"X-Requested-With": "XMLHttpRequest"}, allow_redirects=False, verify=False, timeout=15)
            if r.status_code != 200: break
            data_list = r.json().get("data", [])
            if not data_list: break
            all_uni_data.extend(data_list)
            if len(data_list) < chunk_size: break

        all_prog_data = []
        for start in range(0, limit, chunk_size):
            payload = {**PROG_PAYLOAD_TEMPLATE, "start": str(start), "length": str(chunk_size)}
            r = session.post(ALL_PROGS_POST_URL, data=payload, headers={"X-Requested-With": "XMLHttpRequest"}, allow_redirects=False, verify=False, timeout=15)
            if r.status_code != 200: break
            data_list = r.json().get("data", [])
            if not data_list: break
            all_prog_data.extend(data_list)
            if len(data_list) < chunk_size: break

        # ─────────── STEP 2: BULK DATABASE WRITES (FAST & ATOMIC) ───────────
        fetched_uni_ids = set()
        fetched_prog_ids = set()

        # Cache related models in memory to avoid thousands of DB lookups
        country_cache = {c.name.lower(): c for c in Country.objects.all()}
        city_cache = {(c.country_id, c.name.lower()): c for c in City.objects.select_related('country').all()}
        faculty_cache = {f.name.lower(): f for f in Faculty.objects.all()}
        year_cache = {y.value: y for y in YearOption.objects.all()}
        term_cache = {t.label: t for t in TermOption.objects.all()}
        uni_cache = {u.external_id: u for u in University.objects.all() if u.external_id}
        prog_cache = {p.external_id: p for p in Program.objects.all() if p.external_id}

        unis_to_update = []
        progs_to_update = []
        unis_to_create = []
        progs_to_create = []

        # Process Universities
        for row in all_uni_data:
            uni_ext_id = int(row.get("id") or 0)
            if not uni_ext_id: continue
            fetched_uni_ids.add(uni_ext_id)

            c_name = str(row.get("country.name") or "").strip()
            ci_name = str(row.get("city.name") or "").strip()

            country_obj = country_cache.get(c_name.lower())
            if not country_obj:
                country_obj, _ = Country.objects.get_or_create(name__iexact=c_name, defaults={"name": c_name})
                country_cache[c_name.lower()] = country_obj

            city_key = (country_obj.id, ci_name.lower())
            city_obj = city_cache.get(city_key)
            if not city_obj:
                city_obj, _ = City.objects.get_or_create(country=country_obj, name__iexact=ci_name, defaults={"name": ci_name})
                city_cache[city_key] = city_obj

            parsed_data = {
                "important_dates": parse_html_table(str(row.get("important_dates") or "")),
                "exams_dates": parse_html_table(str(row.get("exams_dates") or "")),
                "exams_scores": parse_html_table(str(row.get("exams_score") or "")),
                "required_documents": parse_required_documents(str(row.get("required_documents") or "")),
                "deposit_info": parse_deposit_info(str(row.get("deposit") or "")),
                "brothers_discount": parse_discount(str(row.get("brothers_discount") or "")),
                "cash_discount": parse_discount(str(row.get("cash_discount") or "")),
                "installment_payment": parse_installment(str(row.get("installment_payment") or "")),
                "preparatory_year": parse_preparatory_year(str(row.get("preparatory_year") or "")),
                "fields_array": row.get("fields", []) or [],
            }

            uni_obj = uni_cache.get(uni_ext_id)
            if uni_obj:
                changed = False
                if uni_obj.country_id != country_obj.id: uni_obj.country = country_obj; changed = True
                if uni_obj.city_id != city_obj.id: uni_obj.city = city_obj; changed = True
                if uni_obj.website != str(row.get("website") or ""): uni_obj.website = str(row.get("website") or ""); changed = True
                if uni_obj.address != str(row.get("campus_address") or ""): uni_obj.address = str(row.get("campus_address") or ""); changed = True
                if uni_obj.parsed_data != parsed_data: uni_obj.parsed_data = parsed_data; changed = True
                if not uni_obj.is_active: uni_obj.is_active = True; changed = True
                if changed: unis_to_update.append(uni_obj)
            else:
                unis_to_create.append(University(
                    external_id=uni_ext_id, name=str(row.get("name") or "").strip(),
                    country=country_obj, city=city_obj, website=str(row.get("website") or "").strip(),
                    address=str(row.get("campus_address") or "").strip(), parsed_data=parsed_data, is_active=True
                ))

        # Process Programs
        for row in all_prog_data:
            ext_id = int(row.get("id") or 0)
            if not ext_id: continue
            fetched_prog_ids.add(ext_id)

            uni_id = int(row.get("university_id") or 0)
            uni_obj = uni_cache.get(uni_id) or University.objects.filter(external_id=uni_id).first()
            if not uni_obj: continue

            fac_name = str(row.get("faculty_name") or "").strip()
            faculty_obj = faculty_cache.get(fac_name.lower())
            if not faculty_obj:
                faculty_obj, _ = Faculty.objects.get_or_create(name__iexact=fac_name, defaults={"name": fac_name})
                faculty_cache[fac_name.lower()] = faculty_obj

            years_value = str(row.get("years") or "").strip()
            language_name = str(row.get("language_name") or "").strip()
            currency_name = str(row.get("currency_name") or "").strip().upper()

            year_obj = year_cache.get(years_value)
            if not year_obj:
                year_obj, _ = YearOption.objects.get_or_create(value=years_value)
                year_cache[years_value] = year_obj
            if year_obj not in faculty_obj.year_options.all():
                faculty_obj.year_options.add(year_obj)

            deg_map = {'associate': 'associate', 'bachelor': 'bachelor', 'master': 'master', 'phd': 'phd', 'integrated_phd': 'integrated_phd'}
            degree_key = deg_map.get(str(row.get("degree_name") or "").strip().lower(), 'bachelor')

            fees_list = row.get("programs_fees", []) or []
            term_obj = None
            if fees_list:
                term_label = str(fees_list[0].get("semester") or "").strip()
                if term_label:
                    term_obj = term_cache.get(term_label)
                    if not term_obj:
                        term_obj, _ = TermOption.objects.get_or_create(label=term_label)
                        term_cache[term_label] = term_obj

            status_map = {'available': Program.StatusChoices.AVAILABLE, 'near_to_close': Program.StatusChoices.NEAR_TO_CLOSE, 'quota_full': Program.StatusChoices.QUOTA_FULL, 'closed': Program.StatusChoices.CLOSED}
            prog_status = status_map.get(str(row.get("status") or "").strip().lower(), Program.StatusChoices.AVAILABLE)

            prog_obj = prog_cache.get(ext_id)
            if prog_obj:
                changed = False
                if prog_obj.university_id != uni_obj.id: prog_obj.university = uni_obj; changed = True
                if prog_obj.status != prog_status: prog_obj.status = prog_status; changed = True
                if prog_obj.faculty_id != faculty_obj.id: prog_obj.faculty = faculty_obj; changed = True
                if prog_obj.degree != degree_key: prog_obj.degree = degree_key; changed = True
                if prog_obj.duration != years_value: prog_obj.duration = years_value; changed = True
                if prog_obj.deposit_fee != parse_decimal(row.get("deposit_fee", "0")): prog_obj.deposit_fee = parse_decimal(row.get("deposit_fee", "0")); changed = True
                if prog_obj.prep_school_fee != parse_decimal(row.get("prep_school_fee", "0")): prog_obj.prep_school_fee = parse_decimal(row.get("prep_school_fee", "0")); changed = True
                if prog_obj.cash_fees != parse_decimal(row.get("cash_fees", "0")): prog_obj.cash_fees = parse_decimal(row.get("cash_fees", "0")); changed = True
                if prog_obj.semester_fee != parse_decimal(row.get("semester_fee", "0")): prog_obj.semester_fee = parse_decimal(row.get("semester_fee", "0")); changed = True
                if prog_obj.deposit != parse_decimal(row.get("deposit", "0")): prog_obj.deposit = parse_decimal(row.get("deposit", "0")); changed = True
                if prog_obj.offer != parse_decimal(row.get("offer", "0")): prog_obj.offer = parse_decimal(row.get("offer", "0")); changed = True
                if prog_obj.term_id != (term_obj.id if term_obj else None): prog_obj.term = term_obj; changed = True
                if prog_obj.language != language_name: prog_obj.language = language_name; changed = True
                if prog_obj.currency != currency_name: prog_obj.currency = currency_name; changed = True
                if not prog_obj.is_active: prog_obj.is_active = True; changed = True
                if changed: progs_to_update.append(prog_obj)
            else:
                progs_to_create.append(Program(
                    external_id=ext_id, name=str(row.get("program_name") or "").strip(),
                    university=uni_obj, status=prog_status, faculty=faculty_obj, degree=degree_key,
                    duration=years_value, deposit_fee=parse_decimal(row.get("deposit_fee", "0")),
                    prep_school_fee=parse_decimal(row.get("prep_school_fee", "0")), cash_fees=parse_decimal(row.get("cash_fees", "0")),
                    semester_fee=parse_decimal(row.get("semester_fee", "0")), deposit=parse_decimal(row.get("deposit", "0")),
                    offer=parse_decimal(row.get("offer", "0")), term=term_obj, language=language_name, currency=currency_name, is_active=True
                ))

        # ─────────── STEP 3: EXECUTE BULK WRITES ────────────────────────────
        if unis_to_create:
            University.objects.bulk_create(unis_to_create, ignore_conflicts=True)
        if unis_to_update:
            University.objects.bulk_update(unis_to_update, ['country', 'city', 'website', 'address', 'parsed_data', 'is_active'])

        if progs_to_create:
            Program.objects.bulk_create(progs_to_create, ignore_conflicts=True)
        if progs_to_update:
            Program.objects.bulk_update(progs_to_update, ['university', 'status', 'faculty', 'degree', 'duration', 'deposit_fee', 'prep_school_fee', 'cash_fees', 'semester_fee', 'deposit', 'offer', 'term', 'language', 'currency', 'is_active'])

        # ─────────── STEP 4: SOFT DELETE (MARK INACTIVE) ────────────────────
        # Instead of deleting, we mark anything NOT in the fetched lists as inactive.
        University.objects.exclude(external_id__in=fetched_uni_ids).filter(is_active=True).update(is_active=False)
        Program.objects.exclude(external_id__in=fetched_prog_ids).filter(is_active=True).update(is_active=False)

        # ─────────── STEP 5: EXPORT TO FILE ─────────────────────────────────
        # Save a clean JSON dump of all active data to BASE_DIR / 'data' / export.json
        file_path = _export_data_to_file()

        elapsed = time.perf_counter() - start_time
        return {
            "status": "success",
            "universities_fetched": len(fetched_uni_ids),
            "programs_fetched": len(fetched_prog_ids),
            "exported_to": file_path,
            "elapsed_seconds": round(elapsed, 2),
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60, max_retries=2)
