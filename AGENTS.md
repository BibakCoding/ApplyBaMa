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


## 3. DEVELOPMENT RULES

- Preserve existing architecture and conventions.
- Prefer reusing existing functionality over creating duplicates.
- Avoid unrelated refactoring.
- Do not introduce new dependencies without justification.
- Keep business logic out of templates.
- Follow existing authentication and permission patterns.
- Follow existing frontend patterns for the dashboard SPA.
- Keep page-specific JavaScript in static/js/pages/.
- Use existing global utilities from static/js/base.js when applicable.

## 4. VALIDATION

Before considering a task complete:

- Run `python manage.py check`
- Run relevant tests.
- Validate affected frontend JavaScript where practical.
- Review the final git diff.

Never claim a task is complete without verification.

## 5. CODE COMMENTS

Do not add comments describing changes made by the AI.

Do not write comments such as:
- "Added..."
- "Changed..."
- "Updated..."
- "New..."
- "Modified..."

Comments should explain non-obvious logic, business rules, or important technical decisions.

## 6. WORKFLOW

For each task:

1. Inspect the repository and identify relevant files.
2. Read the relevant files and trace dependencies as needed.
3. Make the smallest correct set of changes.
4. Run appropriate validation.
5. Review the final git diff.
6. Report all completed, incomplete, or blocked tasks.

Do not scan the entire repository unless the task genuinely requires it.
