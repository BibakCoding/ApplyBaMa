from django.http import JsonResponse
from django.shortcuts import render
from django.urls import translate_url
from django.utils import timezone

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


def get_cities(request):
    country_id = request.GET.get('country_id')
    if not country_id:
        return JsonResponse([], safe=False)

    cities = City.objects.filter(country_id=country_id).order_by('name').values('id', 'name')
    return JsonResponse(list(cities), safe=False)
