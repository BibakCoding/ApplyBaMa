# ApplyBaMa

[![Django CI](https://github.com/BibakCoding/ApplyBaMa/actions/workflows/django.yml/badge.svg)](https://github.com/BibakCoding/ApplyBaMa/actions/workflows/django.yml)

ApplyBaMa is a Django web application for international student applications, university and program discovery, and education-agent management. The dashboard is a single-page application built from Django HTML fragments and vanilla JavaScript, styled with Tailwind CSS compiled through PostCSS.

The site is fully translatable (English, Persian, Turkish, Arabic) with RTL support, exposes a JWT-authenticated JSON API, and ships a custom-branded Django admin panel.

## Technology

- Python 3.10, 3.11, or 3.12 (3.12 recommended — the pinned dependencies are captured from a 3.12 environment)
- Django 5.2
- SQLite for local development
- MySQL or PostgreSQL for production
- Celery (in-memory/eager locally, Redis in production) and django-celery-beat for scheduled tasks
- Selenium and BeautifulSoup for university data collection
- Tailwind CSS compiled with PostCSS; Notyf, Font Awesome, and intl-tel-input self-hosted under `static/vendor/` (no CDN requests)
- django-rosetta and django-modeltranslation for translations
- PyJWT for API token authentication

## Project Structure

```text
ApplyBaMa/
├── ApplyBaMa/          # Django project settings (base/dev/prod), URLs, ASGI, WSGI, Celery
├── api/                # JWT-authenticated JSON API endpoints
├── authentication/     # Registration, verification codes, and authentication flows
├── core/               # Shared models, forms, signals, admin, and utilities
├── dashboard/          # Dashboard SPA views, forms, and models
├── data_fetch/         # University and program synchronization from the external source
├── locale/             # Translation catalogs (en, fa, tr, ar)
├── static/             # CSS, JavaScript, images, and vendored libraries
├── templates/          # Django templates and dashboard fragments
├── requirements/       # Shared, development, and production dependencies
├── manage.py
└── package.json        # Frontend build scripts
```

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/BibakCoding/ApplyBaMa.git
cd ApplyBaMa
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements/dev.txt
```

The development requirements include `requirements/base.txt`. Development settings use SQLite, so a separate database server is not required.

### 4. Configure environment variables

Create a `.env` file in the project root. `manage.py` loads it automatically via python-dotenv.

`SECRET_KEY` is required — development settings read it from the environment and provide no fallback:

```env
SECRET_KEY=replace-this-with-a-local-secret-key
```

Optional variables used by specific features:

```env
# Email sending (registration codes, password reset)
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=

# External data synchronization (studyfans.com) — only needed for the data fetch tasks
SF_EMAIL=
SF_PASSWORD=
```

Never commit real credentials or production secrets. See [Environment Variables](#environment-variables) for the full list.

### 5. Prepare the database and seed data

```bash
python manage.py migrate
```

For a usable local site, seed the reference and homepage data:

```bash
python manage.py seed_countries    # all countries
python manage.py seed_cities       # ~32k cities via geonamescache (run after seed_countries)
python manage.py seed_homepage     # homepage content: settings, journey steps, success stories
```

`seed_homepage` marks a set of universities for the homepage, creating them if they do not exist yet. Real university/program data comes from the synchronization tasks in `data_fetch`, which sign in to the external source with `SF_EMAIL`/`SF_PASSWORD` and use Selenium (a local Chrome or Chromium installation is required). To remove the seeded homepage content again:

```bash
python manage.py clear_homepage
```

### 6. Create an admin user

```bash
python manage.py createsuperuser
```

The admin panel is served at `/admin/`.

### 7. Start Django

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in a browser. `manage.py` selects `ApplyBaMa.settings.dev` by default. Locally, Celery runs tasks eagerly in-process (`memory://` broker), so no separate worker process is needed.

## Frontend Assets

Install the Node.js dependencies:

```bash
npm install
```

Build the CSS once:

```bash
npm run build:css
```

Watch and rebuild CSS while developing:

```bash
npm run watch:css
```

The compiled `static/css/output.css` is committed. After changing any template or JavaScript that adds or removes Tailwind utility classes, re-run `npm run build:css` — otherwise the new classes are absent from the served stylesheet. All third-party assets (Font Awesome, intl-tel-input, Notyf) are vendored under `static/vendor/`; pages make no external CDN requests.

## Translations

The interface ships in English, Persian, Turkish, and Arabic. Wrap user-facing strings (`{% trans %}` in templates, `gettext` in Python), then regenerate the catalogs for all four locales:

```bash
python manage.py makemessages -a
python manage.py compilemessages
```

Staff and superusers can edit translations in the browser at `/rosetta/`. Persian and Arabic render right-to-left automatically.

## Tests and Checks

Run Django's system checks and test suite with the development settings:

```bash
python manage.py check
python manage.py test --settings=ApplyBaMa.settings.dev
```

The project's GitHub Actions workflow runs these checks on Python 3.10, 3.11, and 3.12.

## API

JSON endpoints live under `/api/` and authenticate with JWT (HS256; access tokens last 24 hours, refresh tokens 7 days):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/token/` | POST | Obtain an access/refresh token pair |
| `/api/token/refresh/` | POST | Refresh an access token |
| `/api/token/verify/` | POST | Verify a token |
| `/api/register/` | POST | Register a user |
| `/api/logout/` | POST | Invalidate tokens |
| `/api/user/profile/` | GET | Current user profile |
| `/api/user/profile/update/` | POST | Update the current user profile |
| `/api/dashboard/stats/` | GET | Dashboard statistics for the current user |
| `/api/applications/` | GET | The current user's applications |
| `/api/notifications/` | GET | The current user's notifications |
| `/api/cities/` | GET | City lookup for forms |

## Production Dependencies

Install the production dependency set with:

```bash
pip install -r requirements/prod.txt
```

This includes the shared dependencies plus MySQL/PostgreSQL drivers, Gunicorn, and WhiteNoise. Run application code behind a real WSGI server such as Gunicorn — never Django's development server.

Production also needs:

- A MySQL or PostgreSQL database (configured through `DB_*` variables)
- Memcached for the cache (`CACHE_LOCATION`)
- Redis plus running Celery worker and beat processes for background and scheduled tasks
- The environment variables required by `ApplyBaMa/settings/prod.py`, including `SECRET_KEY` and email settings

## Environment Variables

| Variable | Settings file | Required | Purpose |
|---|---|---|---|
| `SECRET_KEY` | dev, prod | Yes | Django signing key; no development fallback |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | dev, prod | For email | SMTP credentials for verification and reset emails |
| `DEFAULT_FROM_EMAIL` | dev, prod | No | Sender address (has a default) |
| `SF_EMAIL` / `SF_PASSWORD` | base | For data sync | studyfans.com sign-in used by the Selenium data-fetch tasks |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | prod | Yes | Database connection (defaults to MySQL on localhost) |
| `CACHE_LOCATION` | prod | No | Memcached address (default `127.0.0.1:11211`) |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | prod | No | Redis addresses (default `redis://localhost:6379/0`) |

## Dependency Notes

The requirement files pin exact versions captured from the development environment. After installing them on a new machine, run:

```bash
python -m pip check
```

Browser automation requires a locally available Chrome or Chromium installation for the Selenium-based data-fetch tasks.

## License

No license file is currently included in this repository.
