"""Template context published on every page.

``AB_APP_CONFIG`` is the single source of truth for the JavaScript runtime
configuration: the static prefix, whether the visitor is authenticated, the API
endpoints the page scripts call, and the strings those scripts display.

Templates emit it through ``json_script``, which renders a non-executable
``application/json`` data block. Previously each page wrote its own inline
``<script>`` declaring ``window.AppConfig`` by hand, which had two costs: the
home page and the dashboard declared the same URLs twice (so they could drift,
and one of them already had), and inline script cannot be cached and forces
``'unsafe-inline'`` in any Content-Security-Policy.
"""

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _


def _url(name, *args):
    """Reverse ``name``, returning an empty string when it is not mounted.

    A page script that finds an empty URL falls back to its own default, so a
    missing route degrades the one feature that needs it instead of raising
    during rendering.
    """
    try:
        return reverse(name, args=args) if args else reverse(name)
    except NoReverseMatch:
        return ""


def _detail_url(name, pk=0):
    """Resolve a detail route and drop the placeholder id.

    Callers append the real id themselves, e.g.
    ``AppConfig.urls.updateNotification + id + "/"``. The id is replaced once
    (``str.replace`` with a count) to match the previous behaviour exactly.
    """
    return _url(name, pk).replace("0/", "", 1)


def app_config(request):
    user = getattr(request, "user", None)

    return {
        "AB_APP_CONFIG": {
            "staticUrl": settings.STATIC_URL,
            "isLoggedIn": bool(user and user.is_authenticated),
            "urls": {
                # Public site
                "register": _url("register"),
                "dashboard": _url("dashboard"),
                # Dashboard shell
                "dashboardContent": _url("dashboard_content", "PAGE_PLACEHOLDER"),
                "logout": _url("logout"),
                "generatePassword": _url("generate_password"),
                "programApplyRequest": _url("program_apply_request"),
                "programsSearch": _url("programs_search"),
                "universitiesSearch": _url("universities_search"),
                # Notifications
                "sendNotification": _url("send_notification"),
                "searchUsers": _url("search_users_for_notification"),
                "getGroupUsers": _url("get_group_user_ids"),
                "unreadCount": _url("unread_notification_count"),
                "markAllRead": _url("mark_all_notifications_read"),
                "updateNotification": _detail_url("update_notification"),
                "getNotifRecipients": _detail_url("get_notification_recipients"),
            },
            "translations": {
                "searchInfo": _(
                    "Registration is required to see programs matching your search."
                ),
                "newsletterSuccess": _(
                    "Thank you! You are on the scholarship alerts list."
                ),
                "loadingContent": _("Loading content..."),
                "loadingError": _("Loading Error"),
                "errorSupport": _("Please try again or contact support"),
                "reloadPage": _("Reload Page"),
            },
        }
    }
