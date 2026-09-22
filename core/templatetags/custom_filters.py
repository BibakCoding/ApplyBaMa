from django import template
from django.urls import translate_url
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _

register = template.Library()


@register.simple_tag
def filter_params(filters, **overrides):
    """Serializes a fragment's active filters for use in a query string.

    Pagination and cross-page links used to hand-write the same parameter list
    on every button, so a single renamed filter meant editing a dozen template
    lines. Fragments now render it once::

        {% filter_params filters as filters_qs %}
        <button data-page="programs" data-page-params="page={{ i }}{{ filters_qs }}">

    The result already carries a leading "&" and is empty when nothing is
    filtered, so it can be appended without a condition. Empty values are
    dropped, and any key passed as a keyword argument overrides the filter of
    the same name.
    """
    params = {
        key: value
        for key, value in (filters or {}).items()
        if value not in (None, "")
    }
    params.pop("page", None)
    params.update(
        {
            key: value
            for key, value in overrides.items()
            if value not in (None, "")
        }
    )
    encoded = urlencode(params)
    return f"&{encoded}" if encoded else ""

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
