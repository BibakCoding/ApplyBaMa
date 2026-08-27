from django import template
from django.urls import translate_url
from django.utils.translation import gettext_lazy as _

register = template.Library()

@register.filter
def translate_path(path, lang_code):
    return translate_url(path, lang_code)

@register.filter
def translate_doc_level(value):
    """Maps DocumentRequirement level values to their translated display text."""
    level_map = {
        "associate_bachelor": _("Associate & Bachelor"),
        "master": _("Master"),
        "phd": _("PhD"),
    }
    return level_map.get(value, value)
