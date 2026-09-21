# AGENTS.md

This document provides architectural context and operational guidelines for AI coding agents working on the **ApplyBaMa** Django repository.

The purpose of this file is to help AI agents understand the project's architecture, conventions, dependencies, and critical constraints before modifying code.

**Important:** This document is architectural guidance, not a replacement for reading the source code. When implementing a task, always verify relevant behavior against the actual repository.

---

## 1. REPOSITORY CONTEXT

ApplyBaMa is a Django 5.2 web application for international student applications, university discovery, and educational agent management.

The application contains a highly customized **Single Page Application (SPA) dashboard** powered by Vanilla JavaScript. Dashboard pages are dynamically loaded as HTML fragments without full page reloads.

### Key Technologies

* **Backend:** Django 5.2, Python 3.10+
* **Frontend:** Vanilla JavaScript
* **Styling:** Tailwind CSS via CDN
* **Frontend Libraries:** intlTelInput, Notyf (Select2/jQuery were removed — see §7)
* **Database:** SQLite for development, PostgreSQL/MySQL for production
* **Background Tasks:** Celery
* **Data Collection:** Selenium, Requests, BeautifulSoup
* **Internationalization:** Django i18n, modeltranslation, Rosetta, LocaleMiddleware
* **Languages:** English, Arabic, Persian, Turkish

### Local Development Test Account

A pre-seeded account exists in the local development database for live verification of authenticated flows (dashboard SPA, hero-search redirect, permission-gated UI):

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `adminadmin` |
| Flags | `is_superuser = True`, `is_staff = True` |
| `user_type` | `company` (this account also exercises the company/agent branch) |

Use it to verify changes through the real login flow instead of `force_login()` when a task requires the browser-level experience (SPA fragments, redirects, cookie/session behaviour).

**Scope and safety:** this account belongs to the local SQLite development database only. Never reuse this password anywhere real, never provision it in a production or staging environment, and do not assume it exists after a database reset (`migrate` on an empty DB will not create it). If a task needs credentials outside local development, read them from environment variables — never from this file.

---

## 2. PROJECT MAP

```text
ApplyBaMa/
├── ApplyBaMa/               # Project settings and configuration
│   ├── settings/            # Split settings (base.py, dev.py, prod.py)
│   ├── urls.py              # Root URL configuration with i18n_patterns
│   └── celery.py            # Celery application configuration
│
├── authentication/          # Custom authentication flows
│   └── tasks.py             # Asynchronous email tasks
│
├── core/                    # Core domain models and utilities
│   ├── models.py            # User, University, Program, Application, etc.
│   ├── signals.py           # File cleanup and model signals
│   ├── translation.py       # modeltranslation configuration
│   └── utils/               # Shared utilities
│
├── dashboard/               # Dashboard SPA
│   ├── views.py             # Dashboard views and AJAX handlers
│   └── forms.py             # Dashboard forms and styling
│
├── data_fetch/              # External university/program data synchronization
│   ├── tasks.py             # Data-fetching tasks
│   └── importer.py          # Import/upsert logic
│
├── api/                     # API endpoints
│
├── templates/
│   ├── base.html            # Global base template
│   ├── dashboard/
│   │   ├── main.html        # SPA shell
│   │   └── fragments/       # Dynamically loaded dashboard fragments
│   └── authentication/      # Full-page authentication templates
│
├── static/
│   ├── css/
│   └── js/
│       ├── base.js          # Global JavaScript utilities
│       └── pages/
│           └── dashboard.js # Dashboard SPA logic
│
└── locale/                  # Translation files
```

---

## 3. ARCHITECTURAL OVERVIEW

### 3.1 Backend Responsibilities

#### `core`

Contains the main domain models and shared business logic.

Important models include:

* `User`
* `StudentProfile`
* `AgentProfile`
* `CompanyProfile`
* `University`
* `Program`
* `Application`
* `Country`
* `City`
* `Faculty`
* `YearOption`
* `TermOption`

The app also contains model signals and utilities related to uploaded files, image processing, and shared functionality.

#### `authentication`

Implements the application's custom authentication flows.

The project uses verification codes for flows such as:

* Registration
* Email verification
* Password reset

Do not replace these flows with Django's standard password-reset architecture unless the task explicitly requires such a change.

#### `dashboard`

Contains the application's main user dashboard.

The dashboard is not a traditional multi-page Django application. It uses a custom SPA architecture in which the main page remains loaded while individual content fragments are fetched and injected dynamically.

Permission-sensitive functionality, including determining which students an Agent or Company can manage, is handled here.

#### `data_fetch`

Responsible for synchronizing university and program information from external data sources.

The synchronization system uses external identifiers to associate remote records with local records.

Changes to models participating in this synchronization must be made carefully.

#### `api`

Contains application API endpoints used by the frontend and other parts of the system.

Before changing an API endpoint, inspect both its backend implementation and every frontend caller that depends on it.

---

## 4. DASHBOARD SPA ARCHITECTURE

The dashboard follows a specific request → fragment → injection → initialization flow.

### 4.1 SPA Shell

`dashboard/main.html` acts as the dashboard shell.

It contains the persistent dashboard structure, including:

* Sidebar/navigation
* Main dashboard container
* `#dashboard-content`

The shell should normally remain loaded while dashboard content changes.

### 4.2 Navigation

Dashboard navigation uses JavaScript-controlled navigation.

Navigation state is associated with page identifiers and URL parameters.

When changing dashboard navigation behavior, inspect:

* `dashboard/main.html`
* `static/js/pages/dashboard.js`
* Relevant dashboard views
* Relevant URL patterns

Do not assume navigation is implemented like a normal Django page request.

### 4.3 Fragment Loading

Dashboard content is returned as HTML fragments and injected into:

```text
#dashboard-content
```

Fragment templates must contain only the content required inside the dashboard container.

They must **not** contain:

* `<html>`
* `<head>`
* `<body>`
* The global base template
* The dashboard sidebar
* Duplicate SPA shell markup

Do not add:

```django
{% extends "base.html" %}
```

to a fragment unless the architecture is intentionally changed and all dependent behavior is updated accordingly.

### 4.4 JavaScript Initialization

Because dashboard fragments are dynamically replaced, JavaScript must account for elements that do not exist during the initial page load.

The project therefore relies heavily on:

* Event delegation
* Initialization functions
* Global dashboard JavaScript
* Re-initialization after fragment injection

When modifying a dashboard fragment, inspect the JavaScript responsible for that fragment before changing the HTML.

### 4.5 Form Handling

Dashboard forms may be intercepted globally by JavaScript.

Forms can therefore depend on:

* Specific IDs
* Specific CSS classes
* Event delegation
* Custom fetch requests
* JSON responses
* Fragment replacement
* Toast notifications

Before creating or modifying a dashboard form:

1. Find its JavaScript event handler.
2. Inspect the corresponding Django view.
3. Inspect the form class.
4. Inspect the URL.
5. Inspect the template.
6. Trace the complete request/response flow.

Do not change a form's ID or class casually.

---

## 5. DATA FETCHING ARCHITECTURE

The external data synchronization system is an important part of the application.

### External Identifiers

Entities synchronized from external sources use an `external_id` or equivalent identifier to associate local records with remote records.

Never remove, rename, or bypass these identifiers without understanding and updating the complete synchronization pipeline.

### Synchronization Behavior

The synchronization process can:

* Fetch external records
* Match them against local records
* Create new records
* Update existing records
* Mark records as inactive when appropriate

Before modifying `University`, `Program`, `Country`, or `City`, inspect:

* Their model definitions
* `data_fetch/tasks.py`
* `data_fetch/importer.py`
* Any related queries
* Any frontend code depending on their fields

### Background Tasks

Celery tasks are part of the application's runtime architecture.

Before changing a Celery task, inspect:

* The task implementation
* Its callers
* Celery configuration
* Any scheduled execution
* Any dependent database operations

Do not change task behavior merely to simplify code without understanding its operational consequences.

---

## 6. DATA MODELS & RELATIONSHIPS

Important relationships include:

* `User` → `StudentProfile`
* `User` → `AgentProfile`
* `User` → `CompanyProfile`
* `Application` → Agent/User
* `Application` → Student/User
* `Application` → Program
* `Program` → University
* `City` → Country

`Application` also contains state related to the multi-step application process.

`University` and `Program` contain domain-specific financial and descriptive fields.

Before changing a model:

1. Read the **complete model definition**.
2. Search for all direct references to the changed field/model.
3. Inspect forms using the model.
4. Inspect views using the model.
5. Inspect templates and JavaScript using the affected fields.
6. Inspect signals, utilities, tasks, and APIs that may depend on it.

Never assume a model field is isolated to `models.py`.

---

## 7. FRONTEND CONVENTIONS

### JavaScript

The dashboard frontend uses Vanilla JavaScript.

Do not introduce another frontend framework unless explicitly required.

Existing JavaScript behavior should be reused whenever possible.

Before adding JavaScript:

* Search for existing utilities.
* Search for existing event handlers.
* Search for existing initialization functions.
* Check `base.js`.
* Check `dashboard.js`.
* Check page-specific JavaScript.

### Event Delegation

Because dashboard elements are dynamically inserted, direct event listeners attached only during initial page load may stop working after navigation.

Prefer the project's existing event-delegation approach.

### CSRF

The global base template exposes the CSRF token to JavaScript.

All state-changing AJAX requests must follow the project's existing CSRF mechanism.

Do not introduce a second CSRF strategy.

### Notifications

Use the project's existing notification system rather than introducing another library.

### Select2

Select2 (and jQuery) were **removed** from this project. Dashboard `<select>` filters are native HTML selects styled by the project's own CSS.

Do not reintroduce Select2 or jQuery. If searchable dropdowns become a requirement, evaluate a dependency-free alternative deliberately rather than restoring the old broken Select2 setup (which required jQuery that was never loaded and therefore never initialized).

### Phone Inputs

Phone fields may depend on the existing `intlTelInput` initialization logic.

Before changing a phone input, inspect the initialization code and all assumptions about its ID, classes, and DOM structure.

Do not change these assumptions without updating the corresponding JavaScript.

---

## 8. DJANGO FORMS & TEMPLATES

### Forms

Dashboard forms use shared styling conventions such as `BASE_INPUT_CLASS`.

Before creating a new form:

* Inspect existing forms in `dashboard/forms.py`.
* Reuse existing widgets and styling patterns.
* Preserve existing CSS classes and IDs when JavaScript depends on them.

Do not duplicate existing form logic unnecessarily.

### Templates

Before modifying a template, determine whether it is:

* A full-page template
* The SPA shell
* A dashboard fragment
* A reusable partial
* An authentication template

Never treat all templates as interchangeable.

### Internationalization

User-facing text should follow the project's existing i18n system.

Before adding user-facing strings, inspect how the surrounding code handles translations.

Do not introduce a new translation mechanism.

---

## 9. SIGNALS, FILES & IMAGE PROCESSING

The project contains existing mechanisms for:

* Image compression
* Uploaded-file handling
* Cleanup of replaced files

Before changing upload-related functionality, inspect:

* The model field
* Related utilities
* `core/signals.py`
* Forms
* Views
* Templates
* Any JavaScript upload logic

Do not bypass existing file-processing or cleanup mechanisms.

Be especially careful when changing model fields related to uploaded files, because seemingly simple changes can affect both database records and physical files.

---

## 10. PERMISSIONS & ACCESS CONTROL

Permission behavior is part of the application's business logic.

Before changing access to dashboard data:

1. Identify the user's role/type.
2. Inspect existing permission checks.
3. Inspect helper functions such as `get_managed_students()`.
4. Trace every queryset affected by the permission.
5. Check both backend enforcement and frontend visibility.

Do not implement a second, conflicting permission system when an existing helper or pattern already exists.

Frontend hiding is never a substitute for backend authorization.

---

## 11. CRITICAL DEVELOPMENT RULES

### Rule 1 — Preserve Existing Architecture

Do not replace an existing architecture with a simpler one merely because the alternative is more familiar.

The SPA, authentication system, synchronization pipeline, Celery tasks, signals, and permission system are intentional parts of the application.

### Rule 2 — Read Before Changing

**Never modify a file based only on a matching snippet or search result.**

When a file is relevant to a task, read the **complete file** before modifying it.

This is especially important for:

* `models.py`
* `views.py`
* `forms.py`
* `dashboard.js`
* `base.js`
* Celery tasks
* Complex templates
* Configuration files

### Rule 3 — Trace Dependencies

A task rarely affects only one file.

Before modifying code, determine:

```text
Template
   ↓
JavaScript
   ↓
URL
   ↓
View
   ↓
Form / Model / Service
   ↓
Database / External API
```

The exact flow may differ, but the goal is to understand the complete path affected by the change.

### Rule 4 — Verify, Don't Assume

This document describes architecture that has been identified in the repository, but source code is authoritative.

If the actual repository contradicts this document:

1. Trust the actual code.
2. Re-evaluate the relevant architecture.
3. Avoid blindly following outdated documentation.

### Rule 5 — Minimal Changes

Implement the smallest change that correctly satisfies the task.

Do not perform unrelated:

* Refactoring
* Renaming
* Formatting changes
* Dependency changes
* Architecture changes
* Cleanup

unless they are necessary for the requested task.

### Rule 6 — Preserve Existing Integrations

Before changing a shared component, search for all of its consumers.

Examples:

* Model fields
* Form classes
* JavaScript selectors
* URL names
* API response fields
* Template context variables
* Celery task names
* Utility functions

A shared component must not be changed without considering its consumers.

---

## 12. AI AGENT WORKFLOW

Every coding session must follow this workflow.

### Phase 1 — Read Project Instructions

Read this entire `AGENTS.md` before making changes.

Do not start implementing a task before understanding the architectural constraints documented here.

### Phase 2 — Establish Repository Context

Inspect the repository structure and determine:

* Relevant Django apps
* Relevant templates
* Relevant JavaScript
* Relevant models
* Relevant forms
* Relevant URLs
* Relevant APIs
* Relevant Celery tasks
* Relevant utilities
* Relevant signals
* Relevant configuration

Do not assume the task affects only the file explicitly mentioned by the user.

### Phase 3 — Identify the Change Surface

For each task, determine all files and components that may be affected.

Search for:

* Definitions
* Imports
* Function calls
* Model references
* URL references
* Template references
* JavaScript selectors
* API calls
* Related database queries

Create a mental dependency map before editing.

### Phase 4 — Fully Read Relevant Files

**If a file is identified as relevant, read the complete file before modifying it.**

Do not rely only on:

* Search snippets
* Matching lines
* Function signatures
* Partial file previews
* Previously remembered code

If understanding a dependency is necessary to implement the task correctly, read that dependency as well.

The goal is not to blindly read every file in the repository for every task.

The goal is:

> **Read the entire relevant subsystem before changing it.**

For example, if modifying a dashboard form, understand the complete interaction between:

```text
Template
→ JavaScript
→ URL
→ View
→ Form
→ Model
```

before implementing the change.

### Phase 5 — Implement

Implement all requested tasks while:

* Preserving architecture
* Reusing existing functionality
* Avoiding unnecessary dependencies
* Avoiding unrelated modifications
* Preserving existing APIs and contracts unless the task requires changing them

When multiple tasks interact with the same subsystem, implement them coherently rather than treating them as isolated changes.

### Phase 6 — Review Modified Files

After implementation, re-read every modified or newly created file as a complete file.

Check for:

* Syntax errors
* Missing imports
* Broken references
* Incorrect indentation
* Duplicate logic
* Broken template syntax
* Incorrect JavaScript selectors
* Broken SPA behavior
* Incorrect URL/view relationships
* Permission regressions
* Missing i18n
* Accidental unrelated changes

### Phase 7 — Validate

If command execution is available, run the most relevant validation commands, such as:

```bash
python manage.py check
```

and relevant tests.

If command execution is **not** available, perform static validation only.

Never claim that a command was executed if it was not actually executed.

### Phase 8 — Final Verification

Before reporting completion, verify:

* Every requested task was addressed.
* Every affected file is internally consistent.
* No required dependency was overlooked.
* No unrelated architecture was changed.
* All modified/new files can be provided as complete final files.

If a task could not be completed, explicitly report it as incomplete instead of claiming success.

---

## 13. OUTPUT RULES FOR AI CODING SESSIONS

When the user asks for code changes, the final response must contain the **complete final contents of every modified or newly created file**.

### Required

For every modified/new file:

```text
FILE: path/to/file.py
```

followed by **one complete code block containing the entire final file**.

Example:

```text
FILE: dashboard/views.py
```

```python
# COMPLETE FILE CONTENT
```

### Forbidden

Do **not** return:

* Partial snippets
* Only modified functions
* Only modified sections
* Unified diffs
* Git patches
* `+` / `-` diff output
* "Replace this section with..."
* "Add this function..."
* Placeholder comments such as `# existing code...`
* `...` representing omitted code

The user must be able to copy the complete file directly and replace the existing file.

### Large Files

Large files must still be provided completely.

If the response/output limit prevents all files from being returned in one response:

1. Finish the current file if possible.
2. Stop at a clean file boundary.
3. Do not omit part of a file.
4. Clearly state which files have already been provided.
5. Continue with the remaining files when the user asks to continue.
6. Never repeat files that were already provided.

If a single file is too large to fit in one response, split it only at a safe line boundary and explicitly mark that the file continues. On continuation, resume **exactly where the previous response stopped**.

Never silently truncate a file.

---

## 14. COMMUNICATION & COMPLETION RULES

Do not claim that code was:

* Executed
* Tested
* Committed
* Pushed
* Deployed

unless that action was actually performed and the environment genuinely supports it.

When reporting the result, distinguish between:

* **Implemented**
* **Validated**
* **Not validated**
* **Blocked**

A task is not considered complete merely because code was generated.

The implementation must be internally consistent with the repository architecture.

---

## 15. FINAL PRINCIPLE

The most important rule for working on ApplyBaMa is:

> **Understand the existing system before changing it.**

Do not optimize for the smallest number of files read.

Optimize for understanding the complete dependency chain required to make the requested change safely.

**Read the relevant subsystem completely, trace its dependencies, preserve the architecture, implement the smallest correct change, and return complete final files.**

## 16. CONCISE AGENT RESPONSE TEMPLATE

After completing a coding task, use this concise structure:

```text
## Status
[Completed / Partially Completed / Blocked]

## Summary
- [Short description of what was implemented]
- [Important architectural or behavioral note, if any]

## Files Changed
- `path/to/file.py`
- `path/to/template.html`

## Validation
- `python manage.py check` — [Passed / Failed / Not Run]
- Tests — [Passed / Failed / Not Run]

## Notes
[Any important limitation, unresolved issue, or required follow-up.]
```

When code changes were requested, provide the **complete final contents of every modified or newly created file after this summary**, following the output rules in Section 13.

Keep the response concise. Do not include unnecessary explanations, implementation essays, or a diff unless explicitly requested.
