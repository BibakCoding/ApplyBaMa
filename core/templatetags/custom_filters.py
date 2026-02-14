from django import template
from django.urls import translate_url

register = template.Library()


@register.filter
def translate_path(path, lang_code):
    return translate_url(path, lang_code)
