from django.contrib import admin

from data_fetch.models import ConnectSID


@admin.register(ConnectSID)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("sid", "fetched_at")
    search_fields = ("sid", "fetched_at")
    ordering = ("fetched_at",)
