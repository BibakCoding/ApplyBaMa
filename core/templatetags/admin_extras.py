"""Template helpers for the Apply BM admin dashboard.

The dashboard used to be one hardcoded ``{% if model.object_name == "..." %}``
chain per card, which had two real consequences:

* every model that was not in the hardcoded list silently disappeared from the
  admin index (``ConnectSID`` and ``VerificationCode`` were unreachable), and
* each card re-scanned the whole ``app_list``, so the markup grew with
  cards × models.

Everything is data-driven here instead: cards are declared once, an "Other
models" card catches anything new, and the KPI tiles are computed from the
database instead of being decorative numbers.
"""

from django.apps import apps
from django.template import Library
from django.urls import NoReverseMatch, reverse
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

register = Library()

# ---------------------------------------------------------------------------
# Dashboard cards: title, icon, and the models that belong to them.
# Order inside each tuple is the order shown in the card.
#
# Icons are Font Awesome class names, not emoji: the vendored Font Awesome set
# (static/vendor/fontawesome) draws them as a font, so they inherit the card's
# tint colour, stay crisp at any DPI and look the same on Windows, macOS and
# Linux — emoji do none of the three.
# ---------------------------------------------------------------------------
CARD_GROUPS = (
    (
        _("Homepage content"),
        "fa-solid fa-house",
        ("SiteSettings", "SuccessStory", "HowItWorksStep", "DocumentRequirement"),
    ),
    (
        _("Universities & programs"),
        "fa-solid fa-building-columns",
        ("University", "Faculty", "Program", "Country", "City", "TermOption", "YearOption"),
    ),
    (
        _("People & access"),
        "fa-solid fa-users",
        ("User", "StudentProfile", "AgentProfile", "CompanyProfile"),
    ),
    (
        _("Applications"),
        "fa-solid fa-folder-open",
        ("Application",),
    ),
    (
        _("Notifications"),
        "fa-solid fa-bell",
        ("Notification", "NotificationRecipient"),
    ),
    (
        _("Security & verification"),
        "fa-solid fa-user-shield",
        ("VerificationCode",),
    ),
)

OTHER_CARD_TITLE = _("System & other models")
OTHER_CARD_ICON = "fa-solid fa-gears"

# Cards with a tinted header icon, cycled by position so the dashboard keeps a
# stable visual rhythm without extra data.
_TINTS = ("blue", "violet", "teal", "amber", "rose", "slate")


def _model_count(app_label, object_name):
    """Row count for a registered model, or ``None`` when it cannot be read.

    Never let a diagnostic number break the dashboard: a model whose table is
    missing (unapplied migration) or that raises on count simply shows no badge.
    """
    try:
        model = apps.get_model(app_label, object_name)
    except LookupError:
        return None
    if model is None:
        return None
    try:
        return model._default_manager.count()
    except Exception:  # pragma: no cover - defensive, depends on the database
        return None


@register.simple_tag
def admin_dashboard_cards(app_list):
    """Group ``app_list`` (the admin index context) into dashboard cards.

    Every model the user may see shows up exactly once — explicitly grouped
    models first, then an "Other models" card for anything newly registered.
    """
    index = []
    by_name = {}
    for app in app_list or []:
        for model in app.get("models", []):
            entry = dict(model)
            entry["app_label"] = app.get("app_label", "")
            index.append(entry)
            by_name.setdefault(model.get("object_name"), entry)

    grouped = set()
    cards = []
    for position, (title, icon, object_names) in enumerate(CARD_GROUPS):
        models = []
        for object_name in object_names:
            entry = by_name.get(object_name)
            if entry is None:
                continue
            grouped.add(object_name)
            entry["count"] = _model_count(entry.get("app_label", ""), object_name)
            models.append(entry)
        if models:
            cards.append(
                {
                    "title": title,
                    "icon": icon,
                    "tint": _TINTS[position % len(_TINTS)],
                    "models": models,
                }
            )

    leftovers = []
    for entry in index:
        if entry.get("object_name") in grouped:
            continue
        grouped.add(entry.get("object_name"))
        entry["count"] = _model_count(entry.get("app_label", ""), entry.get("object_name"))
        leftovers.append(entry)
    if leftovers:
        cards.append(
            {
                "title": OTHER_CARD_TITLE,
                "icon": OTHER_CARD_ICON,
                "tint": "slate",
                "models": leftovers,
            }
        )
    return cards


def _changelist_url(app_label, model_name, query="", perm=None, user=None):
    """Reverse a changelist URL, honouring the user's view permission."""
    if perm and user is not None and not user.has_perm(perm):
        return ""
    try:
        url = reverse(f"admin:{app_label}_{model_name}_changelist")
    except NoReverseMatch:
        return ""
    return f"{url}?{query}" if query else url


def _tile(label, value, hint, url, icon, tone):
    return {"label": label, "value": value, "hint": hint, "url": url, "icon": icon, "tone": tone}


@register.simple_tag(takes_context=True)
def admin_dashboard_stats(context):
    """Live KPI tiles plus a "needs attention" list for the admin index.

    Each figure is a single ``COUNT`` — cheap, and always in agreement with the
    database, which is the point of putting them on the dashboard at all.
    """
    request = context.get("request")
    if request is None or not request.user.is_staff:
        return {"tiles": [], "attention": []}

    user = request.user
    User = apps.get_model("core", "User")
    Application = apps.get_model("core", "Application")
    Program = apps.get_model("core", "Program")
    University = apps.get_model("core", "University")
    SuccessStory = apps.get_model("core", "SuccessStory")
    VerificationCode = apps.get_model("authentication", "VerificationCode")

    users = User.objects
    students = users.filter(user_type="default").count()
    agents = users.filter(user_type="agent").count()
    companies = users.filter(user_type="company").count()

    programs = Program.objects
    programs_total = programs.count()
    programs_active = programs.filter(is_active=True).count()

    universities_total = University.objects.count()
    universities_homepage = University.objects.filter(show_on_homepage=True).count()

    applications = Application.objects
    applications_total = applications.count()
    applications_open = applications.filter(status="in_progress").count()

    tiles = [
        _tile(
            _("Students"),
            students,
            format_lazy(
                _("{count} with a student profile"),
                count=apps.get_model("core", "StudentProfile").objects.count(),
            ),
            _changelist_url("core", "user", "user_type__exact=default", "core.view_user", user),
            "fa-solid fa-graduation-cap",
            "blue",
        ),
        _tile(
            _("Agents"),
            agents,
            _("Agencies managing students"),
            _changelist_url("core", "user", "user_type__exact=agent", "core.view_user", user),
            "fa-solid fa-user-tie",
            "violet",
        ),
        _tile(
            _("Companies"),
            companies,
            format_lazy(
                _("{count} company profiles"),
                count=apps.get_model("core", "CompanyProfile").objects.count(),
            ),
            _changelist_url("core", "user", "user_type__exact=company", "core.view_user", user),
            "fa-solid fa-building",
            "teal",
        ),
        _tile(
            _("Applications"),
            applications_total,
            format_lazy(_("{count} still in progress"), count=applications_open),
            _changelist_url("core", "application", "", "core.view_application", user),
            "fa-solid fa-folder-open",
            "amber",
        ),
        _tile(
            _("Programs"),
            programs_total,
            format_lazy(_("{count} active"), count=programs_active),
            _changelist_url("core", "program", "", "core.view_program", user),
            "fa-solid fa-book-open",
            "rose",
        ),
        _tile(
            _("Universities"),
            universities_total,
            format_lazy(_("{count} on the homepage"), count=universities_homepage),
            _changelist_url("core", "university", "", "core.view_university", user),
            "fa-solid fa-building-columns",
            "slate",
        ),
    ]

    attention = []
    stories_hidden = SuccessStory.objects.filter(is_published=False).count()
    if stories_hidden:
        attention.append(
            {
                "label": _("Success stories not published"),
                "count": stories_hidden,
                "url": _changelist_url(
                    "core", "successstory", "is_published__exact=0", "core.view_successstory", user
                ),
                "tone": "warning",
            }
        )
    programs_full = programs.filter(status="quota_full").count()
    if programs_full:
        attention.append(
            {
                "label": _("Programs with a full quota"),
                "count": programs_full,
                "url": _changelist_url(
                    "core", "program", "status__exact=quota_full", "core.view_program", user
                ),
                "tone": "warning",
            }
        )
    codes_unused = VerificationCode.objects.filter(used=False).count()
    if codes_unused:
        attention.append(
            {
                "label": _("Unused verification codes"),
                "count": codes_unused,
                "url": _changelist_url(
                    "authentication",
                    "verificationcode",
                    "used__exact=0",
                    "authentication.view_verificationcode",
                    user,
                ),
                "tone": "info",
            }
        )
    if applications_open:
        attention.append(
            {
                "label": _("Applications waiting on a decision"),
                "count": applications_open,
                "url": _changelist_url(
                    "core", "application", "status__exact=in_progress", "core.view_application", user
                ),
                "tone": "info",
            }
        )

    return {"tiles": tiles, "attention": attention}
