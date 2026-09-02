# AGENTS.md

This document provides architectural context and operational guidelines for AI coding agents working on the **ApplyBaMa** Django repository.

## 1. REPOSITORY CONTEXT

This is a Django 5.2 web application for international student applications, university discovery, and agent management.
The dashboard functions as a custom **Single Page Application (SPA)** powered by vanilla JavaScript, dynamically loading HTML fragments without full page reloads.

### Key Technologies
- **Backend:** Django 5.2, Python 3.10+
- **Frontend:** Vanilla JS, Tailwind CSS (CDN), Select2, intlTelInput, Notyf (toasts)
- **Database:** SQLite (dev), PostgreSQL/MySQL (prod)
- **Background Tasks:** Celery, Selenium, BeautifulSoup (for data scraping)
- **i18n:** `modeltranslation`, `rosetta`, `LocaleMiddleware` (Languages: en, ar, fa, tr)

## 2. PROJECT MAP

```text
ApplyBaMa/
├── ApplyBaMa/               # Project settings and configuration
│   ├── settings/            # Split settings (base.py, dev.py, prod.py)
│   ├── urls.py              # Root URLs with i18n_patterns
│   └── celery.py            # Celery app configuration
├── authentication/          # Custom auth flows (OTP, password reset, registration)
├── core/                    # Core models (User, University, Program, Application)
│   ├── utils/               # Image processing, email helpers
│   └── translation.py       # modeltranslation configurations
├── dashboard/               # Dashboard SPA fragments and views
├── data_fetch/              # Celery tasks for scraping external university data
├── api/                     # API endpoints
├── templates/
│   ├── base.html            # Global base template (loads Tailwind CDN)
│   ├── dashboard/
│   │   ├── main.html        # SPA wrapper template
│   │   └── fragments/       # HTML fragments loaded via AJAX
│   └── ...
├── static/
│   ├── css/                 # Custom CSS (base.css, pages/)
│   └── js/
│       ├── base.js          # Global utilities (CSRF, API calls)
│       └── pages/           # Page-specific JS (dashboard.js, login.js, etc.)
└── locale/                  # i18n translation files (en, ar, fa, tr)
