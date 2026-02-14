# ApplyBaMa/api/views.py

import json

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from core.models import City  # adjust the import path if your City model is elsewhere


@require_GET
def city_list_api(request):
    country_id = request.GET.get("country_id")
    if not country_id:
        return HttpResponseBadRequest(
            json.dumps({"error": "Missing country_id"}),
            content_type="application/json",
        )
    try:
        cid = int(country_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid country_id"}, status=400)

    cities = City.objects.filter(country_id=cid).order_by("name")
    data = [{"id": c.id, "name": c.name} for c in cities]
    return JsonResponse(data, safe=False)
