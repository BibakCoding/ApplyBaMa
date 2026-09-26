"""Admin for the verification codes used by registration and password reset.

The model was previously registered with a bare ``admin.site.register``, which
gave a maintainer a wall of codes with no type, no state and no expiry. Support
work needs the opposite: is this code still live, has it been used, and how do I
clear out the expired ones.
"""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from core.admin_utils import CsvExportMixin, pill

from .models import VerificationCode


@admin.register(VerificationCode)
class VerificationCodeAdmin(CsvExportMixin, admin.ModelAdmin):
    """Read-only audit of verification codes.

    The fields are read-only on purpose: codes are generated and invalidated by
    the authentication flow, so editing one by hand could only break a live
    registration or password reset.
    """

    list_display = (
        "user",
        "code_type_badge",
        "code_display",
        "state_badge",
        "created_at",
        "expires_at",
    )
    list_filter = ("code_type", "used")
    search_fields = ("user__username", "user__email", "code")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 50
    readonly_fields = ("user", "code", "code_type", "token", "created_at", "expires_at", "used")
    fieldsets = (
        (None, {"fields": ("user", "code_type", "code", "token")}),
        (_("Lifetime"), {"fields": ("created_at", "expires_at", "used")}),
    )
    actions = ("mark_used", "delete_expired", "export_as_csv", "delete_selected")
    csv_fields = ("user", "code_type", "code", "used", "created_at", "expires_at")

    TYPE_TONES = {
        VerificationCode.CodeType.REGISTRATION: "info",
        VerificationCode.CodeType.RESET: "accent",
    }

    @admin.display(description=_("Type"), ordering="code_type")
    def code_type_badge(self, obj):
        return pill(obj.get_code_type_display(), self.TYPE_TONES.get(obj.code_type, "neutral"))

    @admin.display(description=_("Code"), ordering="code")
    def code_display(self, obj):
        return format_html("<code>{}</code>", obj.code)

    @admin.display(description=_("State"), ordering="used")
    def state_badge(self, obj):
        if obj.used:
            return pill(_("Used"), "neutral")
        if obj.expires_at and obj.expires_at < timezone.now():
            return pill(_("Expired"), "danger")
        return pill(_("Active"), "success")

    @admin.action(description=_("Mark selected codes as used"), permissions=["change"])
    def mark_used(self, request, queryset):
        updated = queryset.update(used=True)
        self.message_user(
            request,
            ngettext("%(count)d code invalidated.", "%(count)d codes invalidated.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Delete expired codes"), permissions=["delete"])
    def delete_expired(self, request, queryset):
        expired = queryset.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        self.message_user(
            request,
            ngettext("%(count)d expired code deleted.", "%(count)d expired codes deleted.", count)
            % {"count": count},
            messages.SUCCESS,
        )
