"""Small, shared building blocks for the Apply BM control center.

They live outside ``core/admin.py`` so every app's admin module can use the same
pill markup, thumbnail markup and CSV export instead of each inventing its own.
The visual side lives in ``static/css/admin/admin-theme.css``.
"""

import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _, ngettext


def pill(label, tone):
    """A coloured status pill.

    Tones available in the theme: ``info``, ``success``, ``warning``,
    ``danger``, ``neutral``, ``accent``, ``violet``, ``teal``.
    """
    return format_html('<span class="admin-pill admin-pill--{}">{}</span>', tone, label)


def thumb(image, description="", wide=False):
    """A small preview for an ``ImageField``, or the empty value when unset."""
    if not image:
        return admin.site.empty_value_display
    css = "admin-thumb admin-thumb--wide" if wide else "admin-thumb"
    return format_html('<img src="{}" alt="{}" class="{}">', image.url, description, css)


def csv_label(model, field_name):
    """Human-readable CSV header for a model field."""
    try:
        return str(model._meta.get_field(field_name).verbose_name)
    except Exception:
        return field_name.replace("_", " ").title()


def csv_value(value):
    """Flatten a model value for CSV output.

    Related objects become their string representation, booleans become the
    localised yes/no, and dates use ISO format — that is what a spreadsheet
    reader expects to receive.
    """
    if value is None:
        return ""
    if getattr(value, "_meta", None) is not None and hasattr(value, "pk"):
        return str(value)
    if isinstance(value, bool):
        return _("Yes") if value else _("No")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class CsvExportMixin:
    """Adds an "Export selected rows as CSV" action to a ``ModelAdmin``.

    ``csv_fields`` is an optional tuple of model attribute names; without it
    every concrete column is exported. The writer emits a UTF-8 BOM so Excel
    opens Persian, Arabic and Turkish text correctly.
    """

    csv_fields = ()
    csv_filename = ""

    @admin.action(description=_("Export selected rows as CSV"), permissions=["view"])
    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        fields = tuple(self.csv_fields) or tuple(f.name for f in meta.concrete_fields)
        filename = self.csv_filename or f"{meta.app_label}-{meta.model_name}"

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow([csv_label(meta.model, name) for name in fields])
        row_count = 0
        for obj in queryset:
            writer.writerow([csv_value(getattr(obj, name, "")) for name in fields])
            row_count += 1

        self.message_user(
            request,
            ngettext("%(count)d row exported.", "%(count)d rows exported.", row_count)
            % {"count": row_count},
            messages.SUCCESS,
        )
        return response
