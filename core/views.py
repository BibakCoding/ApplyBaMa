from django.http import JsonResponse
from django.shortcuts import render
from django.urls import translate_url
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.csrf import csrf_failure as default_csrf_failure

from .models import *


def main(request):
    settings = SiteSettings.objects.first()  # Assuming singleton
    context = {
        'settings': settings,
        'homepage_universities': University.objects.filter(show_on_homepage=True),
        'steps': HowItWorksStep.objects.filter(is_active=True),
        'documents': DocumentRequirement.objects.all(),
        'stories': SuccessStory.objects.filter(is_published=True),
    }
    return render(request, 'core/main.html', context)


def csrf_failure(request, reason=""):
    """CSRF failure: JSON for AJAX callers, the usual HTML page otherwise.

    The HTML failure page is a *page*, and handing it to a caller that parses
    the response with ``r.json()`` is the ``Unexpected token '<'`` bug class
    (AGENTS.md §4.6). The token can expire while the SPA stays open, so the
    caller needs a JSON answer it can act on.
    """
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Existing catalog entry, so every locale already has it (see
        # core.middleware.ajax_auth for the same reasoning).
        message = _("Please try again or contact support")
        return JsonResponse(
            {"success": False, "error": "csrf", "message": message, "errors": [message]},
            status=403,
        )
    return default_csrf_failure(request, reason)


def get_cities(request):
    country_id = request.GET.get('country_id')
    if not country_id:
        return JsonResponse([], safe=False)

    cities = City.objects.filter(country_id=country_id).order_by('name').values('id', 'name')
    return JsonResponse(list(cities), safe=False)
