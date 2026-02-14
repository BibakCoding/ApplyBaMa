from django.http import JsonResponse
from django.shortcuts import render
from django.urls import translate_url
from django.utils import timezone

from .models import City


def main(request):
    context = {
        "current_date": timezone.now().date(),
        "en_url": translate_url(request.path, "en"),
        "fa_url": translate_url(request.path, "fa"),
        "tr_url": translate_url(request.path, "tr"),
        "ar_url": translate_url(request.path, "ar"),
    }
    return render(request, "core/main.html", context)


def get_cities(request):
    country_id = request.GET.get('country_id')
    if not country_id:
        return JsonResponse([], safe=False)

    cities = City.objects.filter(country_id=country_id).order_by('name').values('id', 'name')
    return JsonResponse(list(cities), safe=False)
