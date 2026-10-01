"""Answer AJAX callers with JSON instead of an HTML error page.

Every JSON endpoint in this project is reached with ``fetch()`` / XHR. Two
Django middlewares can still answer such a caller with an HTML *page*:

* ``@login_required`` redirects to the login form (302) when the session has
  expired. The browser follows the redirect transparently, the caller's
  ``r.json()`` then fails on an HTML document and the console shows
  ``Unexpected token '<'``.
* a missing or stale CSRF token produces the HTML 403 failure page, which fails
  the same way.

The redirect and the 403 page are both correct for a *page navigation* and both
wrong for an AJAX call, and the difference is knowable in exactly one place: the
response the caller is about to receive. Doing it here — rather than decorating
every JSON view — keeps the contract true for views that do not exist yet.

See AGENTS.md §4.6 for the contract and §18 V2 for the gate.
"""

from urllib.parse import urlsplit

from django.http import JsonResponse
from django.urls import Resolver404, resolve
from django.utils.translation import gettext as _


class AjaxAuthMiddleware:
    """Return JSON 401 to an AJAX caller that was bounced to the login form."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not self._is_ajax(request):
            return response
        if response.status_code not in (301, 302, 303):
            return response
        if not self._points_at_login(response.get("Location", "")):
            return response

        # The message reuses an existing catalog entry on purpose: the JS sends
        # the visitor to the login form (carrying ?next=) the moment it sees
        # this 401, so the text is a fallback for callers that surface it, and
        # reusing it keeps all four locales complete without new msgids.
        message = _("Please try again or contact support")
        return JsonResponse(
            {"success": False, "error": "auth", "message": message, "errors": [message]},
            status=401,
        )

    @staticmethod
    def _is_ajax(request):
        return request.headers.get("x-requested-with") == "XMLHttpRequest"

    @staticmethod
    def _points_at_login(location):
        """True when ``location`` is the login route, in any language prefix."""
        if not location:
            return False
        try:
            return resolve(urlsplit(location).path).view_name == "login"
        except (Resolver404, ValueError):
            return False
