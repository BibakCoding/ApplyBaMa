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

from realtime.routing import WS_CHAT_PATH, WS_NOTIFY_PATH


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

    # The grant dialog's pre-filled value (SiteSettings.chat_default_file_mb).
    from core.models import SiteSettings

    chat_default_file_mb = SiteSettings.objects.get_or_create(pk=1)[0].chat_default_file_mb

    return {
        "chat_default_file_mb": chat_default_file_mb,
        "AB_APP_CONFIG": {
            "staticUrl": settings.STATIC_URL,
            "isLoggedIn": bool(user and user.is_authenticated),
            "userId": user.pk if user and user.is_authenticated else None,
            "chatDefaultFileMb": chat_default_file_mb,
            "urls": {
                # Public site
                "register": _url("register"),
                "dashboard": _url("dashboard"),
                # Support chat entry points: the footer link and the floating
                # button both land on the chat page (or on the login form that
                # carries ?next=...?page=chat back to it).
                "login": _url("login"),
                # Dashboard shell
                "dashboardContent": _url("dashboard_content", "PAGE_PLACEHOLDER"),
                "logout": _url("logout"),
                "generatePassword": _url("generate_password"),
                "programApplyRequest": _url("program_apply_request"),
                "programsSearch": _url("programs_search"),
                "universitiesSearch": _url("universities_search"),
                "getCities": _url("get_cities_by_country"),
                "notificationDetail": _detail_url("notification_detail"),
                "markRead": _detail_url("mark_notification_read"),
                # Email verification (read-only mode escape hatches)
                "resendEmailVerification": _url("resend_email_verification"),
                "cancelEmailChange": _url("cancel_email_change"),
                # Notifications
                "notifySocket": "/" + WS_NOTIFY_PATH,
                # Chat
                "chatSocket": "/" + WS_CHAT_PATH,
                "chatConversations": _url("chat_conversations"),
                "chatThread": _detail_url("chat_thread"),
                "chatSend": _url("chat_send"),
                "chatUpload": _detail_url("chat_upload"),
                "chatEdit": _detail_url("chat_edit"),
                "chatDelete": _detail_url("chat_delete"),
                "chatPin": _detail_url("chat_pin"),
                "chatForward": _detail_url("chat_forward"),
                "chatRead": _detail_url("chat_read"),
                "chatGrant": _detail_url("chat_grant"),
                # Representation requests (Requests page + "Add by ID" dialog)
                "agentRequestSearch": _url("agent_request_search"),
                "agentRequestSend": _url("agent_request_send"),
                "agentRequestRespond": _detail_url("agent_request_respond"),
                "agentRequestCancel": _detail_url("agent_request_cancel"),
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
                "supportChatTitle": _("Contact Support"),
                "supportChatHint": _(
                    "Chat with the Apply BM team — log in if asked."
                ),
                "newsletterSuccess": _(
                    "Thank you! You are on the scholarship alerts list."
                ),
                "loadingContent": _("Loading content..."),
                "loadingError": _("Loading Error"),
                "errorSupport": _("Please try again or contact support"),
                "reloadPage": _("Reload Page"),
                "emailVerifiedReload": _(
                    "Email verified! Your account is fully active again."
                ),
                # Chat
                "chatConnected": _("Chat connected"),
            },
        }
    }
