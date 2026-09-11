# ApplyBaMa

[![Django CI](https://github.com/BibakCoding/ApplyBaMa/actions/workflows/django.yml/badge.svg)](https://github.com/BibakCoding/ApplyBaMa/actions/workflows/django.yml)

ApplyBaMa is a Django web application for international student applications, university and program discovery, and education-agent management. The dashboard uses Django HTML fragments and vanilla JavaScript, with Tailwind CSS built through PostCSS.

## Technology

- Python 3.10, 3.11, or 3.12
- Django 5.2
- SQLite for local development
- MySQL or PostgreSQL for production
- Celery and Redis for production background tasks
- Selenium and BeautifulSoup for university data collection
- Tailwind CSS, PostCSS, Notyf, and Swiper

## Project Structure

```text
ApplyBaMa/
├── ApplyBaMa/          # Django project settings, URLs, ASGI, and WSGI
├── api/                # API endpoints
├── authentication/     # Registration, verification, and authentication flows
├── core/               # Shared models, forms, signals, and utilities
├── dashboard/          # Dashboard views, forms, and models
├── data_fetch/         # University and program synchronization
├── static/              # CSS, JavaScript, fonts, and images
├── templates/           # Django templates and dashboard fragments
├── requirements/        # Shared, development, and production dependencies
├── manage.py
└── package.json         # Frontend build scripts and packages
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

The development requirements include `requirements/base.txt`. Development settings use SQLite, so a separate database server is not required for the basic local workflow.

### 4. Configure environment variables

Create a `.env` file in the project root. At minimum, set a development secret key:

```env
SECRET_KEY=replace-this-with-a-local-secret-key
```

Optional email variables are used by email-related features:

```env
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
```

Never commit real credentials or production secrets.

### 5. Prepare the database

```bash
python manage.py migrate
```

### 6. Start Django

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in a browser. `manage.py` selects `ApplyBaMa.settings.dev` by default.

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

## Tests and Checks

Run Django’s system checks and test suite with the development settings:

```bash
python manage.py check
python manage.py test --settings=ApplyBaMa.settings.dev
```

The project’s GitHub Actions workflow runs these checks on Python 3.10, 3.11, and 3.12.

## Production Dependencies

Install the production dependency set with:

```bash
pip install -r requirements/prod.txt
```

This includes the shared dependencies plus MySQL/PostgreSQL drivers, Gunicorn, and WhiteNoise. Set the production environment variables required by `ApplyBaMa/settings/prod.py`, including database credentials, `SECRET_KEY`, email settings, and Celery broker/result-backend URLs.

Use a real WSGI server such as Gunicorn in production. Do not use Django’s development server for public traffic.

## Dependency Notes

The requirement files currently contain exact versions captured from the development environment. After installing them on a new machine, run:

```bash
python -m pip check
```

Browser automation may also require a locally available Chrome or Chromium installation for Selenium-based tasks.

## License

No license file is currently included in this repository.
