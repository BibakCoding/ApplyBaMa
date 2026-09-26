"""Admin for the studyfans session id used by the data fetcher.

The previous registration was a copy/paste of the Country admin: the class was
even called ``CountryAdmin`` while registering ``ConnectSID``, and it offered a
free-text search on a timestamp. The SID is written by the fetcher itself, so
here it is read-only and auditable.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin_utils import CsvExportMixin

from .models import ConnectSID


@admin.register(ConnectSID)
class ConnectSIDAdmin(CsvExportMixin, admin.ModelAdmin):
    """Read-only history of fetched ``connect.sid`` cookie values."""

    list_display = ("id", "sid_preview", "fetched_at")
    search_fields = ("sid",)
    ordering = ("-fetched_at",)
    date_hierarchy = "fetched_at"
    list_per_page = 50
    readonly_fields = ("sid", "fetched_at")
    actions = ("export_as_csv", "delete_selected")
    csv_fields = ("id", "sid", "fetched_at")

    @admin.display(description=_("Session id"))
    def sid_preview(self, obj):
        return f"{obj.sid[:40]}…" if len(obj.sid) > 40 else obj.sid
