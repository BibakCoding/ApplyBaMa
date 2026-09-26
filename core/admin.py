"""Admin configuration for the Apply BM Control Center.

Three principles are applied consistently here:

* **Never lose an edit box.** Anything a maintainer needs frequently gets a
  changelist toggle (``list_editable``), so a routine "publish this / activate
  that" no longer requires opening a form and pressing save.
* **Never show a bare enum.** Status/step/type columns are rendered as coloured
  pills, and every pill column stays sortable through
  ``@admin.display(ordering=...)``.
* **Never make the maintainer repeat themselves.** Repetitive jobs (publishing,
  activating, reopening applications, exporting a filtered list) are bulk
  actions; the CSV export writes a UTF-8 BOM so Excel opens Persian, Arabic and
  Turkish text correctly.

The ``User`` registration deserves a special mention: it used to be a plain
``ModelAdmin``, which silently stores the *raw* password typed into the admin
form. It now extends Django's own ``UserAdmin``, so passwords are hashed and
the "change password" flow works.
"""

from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from modeltranslation.admin import TranslationAdmin
from solo.admin import SingletonModelAdmin

from .admin_utils import CsvExportMixin, pill, thumb
from .models import (
    Application,
    AgentProfile,
    City,
    CompanyProfile,
    Country,
    DocumentRequirement,
    Faculty,
    HowItWorksStep,
    Notification,
    NotificationRecipient,
    Program,
    SiteSettings,
    StudentProfile,
    SuccessStory,
    TermOption,
    University,
    User,
    YearOption,
)

# ---------------------------------------------------------------------------
# Site chrome
# ---------------------------------------------------------------------------
admin.site.site_header = _("Apply BM Control Center")
admin.site.site_title = _("Apply BM Admin")
admin.site.index_title = ""
admin.site.empty_value_display = "—"


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------
@admin.register(Country)
class CountryAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("name", "language", "nationality", "external_id", "created_at", "updated_at")
    search_fields = ("name", "language", "nationality")
    ordering = ("name",)
    list_per_page = 50
    actions = ("export_as_csv", "delete_selected")


@admin.register(City)
class CityAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("name", "country", "external_id", "created_at", "updated_at")
    search_fields = ("name", "country__name")
    list_filter = ("country",)
    list_select_related = ("country",)
    ordering = ("country__name", "name")
    actions = ("export_as_csv", "delete_selected")


@admin.register(TermOption)
class TermOptionAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("label", "program_count", "created_at", "updated_at")
    search_fields = ("label",)
    ordering = ("label",)
    actions = ("export_as_csv", "delete_selected")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_programs=Count("program", distinct=True))

    @admin.display(description=_("Programs"), ordering="_programs")
    def program_count(self, obj):
        return obj._programs


@admin.register(YearOption)
class YearOptionAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("value", "faculty_count", "created_at", "updated_at")
    search_fields = ("value",)
    ordering = ("value",)
    actions = ("export_as_csv", "delete_selected")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_faculties=Count("faculties", distinct=True))

    @admin.display(description=_("Faculties"), ordering="_faculties")
    def faculty_count(self, obj):
        return obj._faculties


@admin.register(Faculty)
class FacultyAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("name", "university_count", "program_count", "updated_at")
    search_fields = ("name",)
    filter_horizontal = ("year_options",)
    ordering = ("name",)
    actions = ("export_as_csv", "delete_selected")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _universities=Count("universities", distinct=True),
                _programs=Count("programs", distinct=True),
            )
        )

    @admin.display(description=_("Universities"), ordering="_universities")
    def university_count(self, obj):
        return obj._universities

    @admin.display(description=_("Programs"), ordering="_programs")
    def program_count(self, obj):
        return obj._programs


# ---------------------------------------------------------------------------
# University & Program
# ---------------------------------------------------------------------------
@admin.register(University)
class UniversityAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "logo_preview",
        "country",
        "city",
        "sector",
        "program_count",
        "show_on_homepage",
        "is_active",
        "founded_in",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = ("show_on_homepage", "is_active")
    search_fields = ("name", "country__name", "city__name")
    list_filter = ("sector", "is_active", "show_on_homepage", "country")
    # NOTE: "available_languages" cannot be listed here. The M2M of that name is
    # removed by migration 0013 and is shadowed by the `University.available_
    # languages` property (the languages actually offered by the university's
    # programs), so it is not an editable field any more.
    filter_horizontal = ("faculties",)
    # Both are autocomplete fields on purpose. Country has ~200 rows and City
    # has ~32,000, and a plain <select> renders every one of them: the add/
    # change form was a 1.7 MB page that took ~13 s to render on the dev
    # server. Autocomplete searches on demand instead ("name" only, so a city
    # query stays fast on a table that large).
    autocomplete_fields = ("country", "city")
    list_select_related = ("country", "city")
    ordering = ("name",)
    date_hierarchy = "created_at"
    save_on_top = True
    # external_id drives the studyfans synchronisation: never edit it by hand.
    readonly_fields = ("external_id",)
    actions = (
        "mark_homepage",
        "unmark_homepage",
        "activate",
        "deactivate",
        "export_as_csv",
        "delete_selected",
    )
    csv_fields = (
        "name",
        "country",
        "city",
        "sector",
        "founded_in",
        "website",
        "show_on_homepage",
        "is_active",
        "external_id",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_programs=Count("programs", distinct=True))
        )

    @admin.display(description=_("Logo"))
    def logo_preview(self, obj):
        return thumb(obj.logo, str(obj.name))

    @admin.display(description=_("Programs"), ordering="_programs")
    def program_count(self, obj):
        return obj._programs

    @admin.action(description=_("Show selected universities on the homepage"), permissions=["change"])
    def mark_homepage(self, request, queryset):
        updated = queryset.update(show_on_homepage=True)
        self.message_user(
            request,
            ngettext(
                "%(count)d university is now on the homepage.",
                "%(count)d universities are now on the homepage.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Hide selected universities from the homepage"), permissions=["change"])
    def unmark_homepage(self, request, queryset):
        updated = queryset.update(show_on_homepage=False)
        self.message_user(
            request,
            ngettext(
                "%(count)d university was removed from the homepage.",
                "%(count)d universities were removed from the homepage.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Activate selected universities"), permissions=["change"])
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext("%(count)d university activated.", "%(count)d universities activated.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Deactivate selected universities"), permissions=["change"])
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                "%(count)d university deactivated.", "%(count)d universities deactivated.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )


class DiscountFilter(admin.SimpleListFilter):
    """Filters programs by whether they carry a live discount."""

    title = _("discount")
    parameter_name = "discount"

    def lookups(self, request, model_admin):
        return (("yes", _("Has an offer")), ("no", _("No offer")))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(offer__gt=0)
        if self.value() == "no":
            return queryset.filter(Q(offer__isnull=True) | Q(offer=0))
        return queryset


@admin.register(Program)
class ProgramAdmin(CsvExportMixin, admin.ModelAdmin):
    STATUS_TONES = {
        Program.StatusChoices.AVAILABLE: "success",
        Program.StatusChoices.NEAR_TO_CLOSE: "warning",
        Program.StatusChoices.QUOTA_FULL: "danger",
        Program.StatusChoices.CLOSED: "neutral",
    }

    list_display = (
        "name",
        "status_badge",
        "university",
        "faculty",
        "degree",
        "duration",
        "price",
        "is_active",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = ("is_active",)
    search_fields = ("name", "university__name", "faculty__name")
    list_filter = ("status", "is_active", "degree", "university", DiscountFilter)
    autocomplete_fields = ("university", "faculty", "term")
    list_select_related = ("university", "faculty")
    ordering = ("name",)
    date_hierarchy = "created_at"
    save_on_top = True
    readonly_fields = ("external_id",)
    actions = (
        "mark_available",
        "mark_quota_full",
        "activate",
        "deactivate",
        "export_as_csv",
        "delete_selected",
    )
    csv_fields = (
        "name",
        "university",
        "faculty",
        "degree",
        "duration",
        "status",
        "language",
        "currency",
        "deposit_fee",
        "prep_school_fee",
        "cash_fees",
        "semester_fee",
        "offer",
        "is_active",
        "external_id",
        "updated_at",
    )

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        tone = self.STATUS_TONES.get(obj.status, "neutral")
        return pill(obj.get_status_display(), tone)

    @admin.display(description=_("Price"), ordering="offer")
    def price(self, obj):
        if not obj.original_price:
            return admin.site.empty_value_display
        if obj.is_discounted:
            return format_html(
                '{} <span class="admin-cell-muted">({} → {})</span>',
                pill(f"{obj.display_price} {obj.currency}".strip(), "accent"),
                f"{obj.original_price}",
                _("offer"),
            )
        return format_html("{}", f"{obj.display_price} {obj.currency}".strip())

    @admin.action(description=_("Mark selected programs as available"), permissions=["change"])
    def mark_available(self, request, queryset):
        updated = queryset.update(status=Program.StatusChoices.AVAILABLE)
        self.message_user(
            request,
            ngettext(
                "%(count)d program is now available.", "%(count)d programs are now available.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Mark selected programs as quota full"), permissions=["change"])
    def mark_quota_full(self, request, queryset):
        updated = queryset.update(status=Program.StatusChoices.QUOTA_FULL)
        self.message_user(
            request,
            ngettext(
                "%(count)d program marked as quota full.",
                "%(count)d programs marked as quota full.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Activate selected programs"), permissions=["change"])
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext("%(count)d program activated.", "%(count)d programs activated.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Deactivate selected programs"), permissions=["change"])
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext("%(count)d program deactivated.", "%(count)d programs deactivated.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Users & profiles
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Extends Django's ``UserAdmin`` so passwords are hashed properly.

    The previous registration used a plain ``ModelAdmin``, which saved the
    password field verbatim — a user created that way could never log in and
    the database held a plaintext password.
    """

    list_display = (
        "username",
        "email",
        "user_type_badge",
        "is_staff",
        "is_active",
        "is_representative",
        "application_count",
        "date_joined",
    )
    list_display_links = ("username",)
    list_editable = ("is_active",)
    list_filter = ("user_type", "is_active", "is_staff", "is_representative", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name", "mobile")
    ordering = ("-date_joined",)
    date_hierarchy = "date_joined"
    list_select_related = ()
    autocomplete_fields = ("country", "city", "citizenship")
    actions = (
        "activate_users",
        "deactivate_users",
        "export_as_csv",
        "delete_selected",
    )
    # Extra profile columns appended to Django's own fieldsets.
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            _("Profile"),
            {
                "fields": (
                    "user_type",
                    "gender",
                    "date_of_birth",
                    "father_name",
                    "mother_name",
                    "mobile",
                    "profile_image",
                    "country",
                    "city",
                    "citizenship",
                    "is_representative",
                )
            },
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets
    csv_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "user_type",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_representative",
        "country",
        "city",
        "date_joined",
        "last_login",
    )

    USER_TYPE_TONES = {
        User.UserType.DEFAULT: "info",
        User.UserType.AGENT: "violet",
        User.UserType.COMPANY: "teal",
    }

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _student_apps=Count("student_applications", distinct=True),
                _agent_apps=Count("agent_applications", distinct=True),
            )
        )

    @admin.display(description=_("Type"), ordering="user_type")
    def user_type_badge(self, obj):
        tone = self.USER_TYPE_TONES.get(obj.user_type, "neutral")
        return pill(obj.get_user_type_display(), tone)

    @admin.display(description=_("Applications"), ordering="_student_apps")
    def application_count(self, obj):
        return obj._student_apps + obj._agent_apps

    @admin.action(description=_("Activate selected users"), permissions=["change"])
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext("%(count)d user activated.", "%(count)d users activated.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Deactivate selected users"), permissions=["change"])
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext("%(count)d user deactivated.", "%(count)d users deactivated.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )


@admin.register(CompanyProfile)
class CompanyProfileAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("company_name", "user", "company_email", "phone", "agent_count", "updated_at")
    search_fields = ("company_name", "user__username", "company_email")
    list_select_related = ("user",)
    ordering = ("company_name",)
    autocomplete_fields = ("user",)
    actions = ("export_as_csv", "delete_selected")
    csv_fields = (
        "company_name",
        "user",
        "company_email",
        "phone",
        "tax_number",
        "website",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_agents=Count("agents", distinct=True))

    @admin.display(description=_("Agents"), ordering="_agents")
    def agent_count(self, obj):
        return obj._agents


@admin.register(AgentProfile)
class AgentProfileAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = ("user", "agency", "application_count", "updated_at")
    search_fields = ("user__username", "user__email", "agency__company_name")
    list_filter = ("agency",)
    list_select_related = ("user", "agency")
    ordering = ("user__username",)
    autocomplete_fields = ("user", "agency")
    actions = ("export_as_csv", "delete_selected")
    csv_fields = ("user", "agency", "created_at", "updated_at")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_apps=Count("user__agent_applications", distinct=True))
        )

    @admin.display(description=_("Applications"), ordering="_apps")
    def application_count(self, obj):
        return obj._apps


@admin.register(StudentProfile)
class StudentProfileAdmin(CsvExportMixin, admin.ModelAdmin):
    STAGE_TONES = {
        "freshman": "info",
        "sophomore": "teal",
        "junior": "violet",
        "senior": "accent",
    }

    list_display = ("user", "passport", "stage_badge", "language", "updated_at")
    search_fields = ("user__username", "user__email", "passport")
    list_filter = ("stage", "language")
    list_select_related = ("user", "language")
    ordering = ("user__username",)
    autocomplete_fields = ("user", "language")
    actions = ("export_as_csv", "delete_selected")
    csv_fields = ("user", "passport", "stage", "language", "created_at", "updated_at")

    @admin.display(description=_("Stage"), ordering="stage")
    def stage_badge(self, obj):
        return pill(obj.get_stage_display(), self.STAGE_TONES.get(obj.stage, "neutral"))


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class ApplicationAttentionFilter(admin.SimpleListFilter):
    """Surfaces the applications that actually need a human decision."""

    title = _("needs attention")
    parameter_name = "attention"

    def lookups(self, request, model_admin):
        return (
            ("open", _("Still in progress")),
            ("stale", _("No update for 30+ days")),
            ("no_program", _("No program chosen yet")),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "open":
            return queryset.filter(status=Application.Status.IN_PROGRESS)
        if value == "stale":
            cutoff = timezone.now() - timedelta(days=30)
            return queryset.filter(status=Application.Status.IN_PROGRESS, updated_at__lt=cutoff)
        if value == "no_program":
            return queryset.filter(program__isnull=True)
        return queryset


@admin.register(Application)
class ApplicationAdmin(CsvExportMixin, admin.ModelAdmin):
    STATUS_TONES = {
        Application.Status.IN_PROGRESS: "info",
        Application.Status.FINISHED: "success",
        Application.Status.FAILED: "danger",
    }

    list_display = (
        "application_name",
        "student_link",
        "agent_link",
        "program",
        "status_badge",
        "progress",
        "student_type",
        "updated_at",
    )
    search_fields = (
        "application_name",
        "student__username",
        "student__email",
        "agent__username",
        "program__name",
        "program__university__name",
    )
    list_filter = ("status", "step", "student_type", ApplicationAttentionFilter)
    autocomplete_fields = ("agent", "student", "program")
    list_select_related = ("student", "agent", "program")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    save_on_top = True
    readonly_fields = ("application_name",)
    fieldsets = (
        (_("Identifiers"), {"fields": ("application_name",)}),
        (_("Parties"), {"fields": ("student", "agent", "student_type")}),
        (_("Progress"), {"fields": ("program", "status", "step")}),
        (_("Documents"), {"fields": ("documents",)}),
    )
    actions = (
        "mark_finished",
        "mark_failed",
        "reopen",
        "export_as_csv",
        "delete_selected",
    )
    csv_fields = (
        "application_name",
        "student",
        "agent",
        "student_type",
        "program",
        "status",
        "step",
        "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("program__university")

    def _user_link(self, user):
        if user is None:
            return admin.site.empty_value_display
        url = reverse("admin:core_user_change", args=[user.pk])
        label = user.get_full_name() or user.get_username()
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(description=_("Student"), ordering="student__username")
    def student_link(self, obj):
        return self._user_link(obj.student)

    @admin.display(description=_("Agent"), ordering="agent__username")
    def agent_link(self, obj):
        return self._user_link(obj.agent)

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):
        return pill(obj.get_status_display(), self.STATUS_TONES.get(obj.status, "neutral"))

    @admin.display(description=_("Progress"), ordering="step")
    def progress(self, obj):
        """`Step 3 of 7` plus a bar.

        The bar width comes from a small set of precomputed step classes
        (``admin-progress--step-N``) rather than an inline style attribute, so
        no per-row CSS is generated.
        """
        total = int(Application.StepChoices.STEP_7)
        current = int(obj.step or 0)
        current = max(0, min(current, total))
        tone = "success" if obj.status == Application.Status.FINISHED else (
            "danger" if obj.status == Application.Status.FAILED else "info"
        )
        return format_html(
            '<span class="admin-progress admin-progress--{}">'
            '<span class="admin-progress__bar admin-progress__bar--step-{}"></span></span>'
            '<span class="admin-cell-muted">{}/{}</span>',
            tone,
            current,
            current,
            total,
        )

    def _apply_status(self, request, queryset, status, singular, plural):
        """Bulk status change with a correctly pluralised confirmation."""
        updated = queryset.update(status=status)
        if updated:
            self.message_user(
                request,
                ngettext(singular, plural, updated) % {"count": updated},
                messages.SUCCESS,
            )
        return updated

    @admin.action(description=_("Mark selected applications as finished"), permissions=["change"])
    def mark_finished(self, request, queryset):
        return self._apply_status(
            request,
            queryset,
            Application.Status.FINISHED,
            _("%(count)d application marked as finished."),
            _("%(count)d applications marked as finished."),
        )

    @admin.action(description=_("Mark selected applications as failed"), permissions=["change"])
    def mark_failed(self, request, queryset):
        return self._apply_status(
            request,
            queryset,
            Application.Status.FAILED,
            _("%(count)d application marked as failed."),
            _("%(count)d applications marked as failed."),
        )

    @admin.action(description=_("Reopen selected applications"), permissions=["change"])
    def reopen(self, request, queryset):
        return self._apply_status(
            request,
            queryset,
            Application.Status.IN_PROGRESS,
            _("%(count)d application reopened."),
            _("%(count)d applications reopened."),
        )


# ---------------------------------------------------------------------------
# Homepage content (translatable, admin-controlled)
# ---------------------------------------------------------------------------
@admin.register(SiteSettings)
class SiteSettingsAdmin(TranslationAdmin, SingletonModelAdmin):
    """Singleton + translation tabs.

    Only one settings object ever exists (the admin can edit it, never create
    or delete it); the language tabs come from modeltranslation.
    """

    fieldsets = (
        (_("Hero section"), {"fields": ("hero_title", "hero_subtitle", "hero_background_image")}),
        (
            _("Contact & social"),
            {
                "fields": (
                    "whatsapp_number",
                    "email",
                    "address",
                    "instagram_url",
                    "telegram_url",
                )
            },
        ),
    )


@admin.register(HowItWorksStep)
class HowItWorksStepAdmin(TranslationAdmin):
    list_display = ("order", "title", "icon_class", "is_active")
    list_editable = ("order", "is_active")
    list_display_links = ("title",)
    list_filter = ("is_active",)
    search_fields = ("title", "description")
    ordering = ("order",)
    actions = ("delete_selected",)


@admin.register(DocumentRequirement)
class DocumentRequirementAdmin(TranslationAdmin):
    list_display = ("title", "level_badge", "order")
    list_editable = ("order",)
    list_display_links = ("title",)
    list_filter = ("level",)
    search_fields = ("title",)
    ordering = ("level", "order")
    actions = ("delete_selected",)

    LEVEL_TONES = {
        "associate_bachelor": "info",
        "master": "violet",
        "phd": "accent",
    }

    @admin.display(description=_("Level"), ordering="level")
    def level_badge(self, obj):
        return pill(obj.get_level_display(), self.LEVEL_TONES.get(obj.level, "neutral"))


@admin.register(SuccessStory)
class SuccessStoryAdmin(CsvExportMixin, TranslationAdmin):
    list_display = (
        "name",
        "image_preview",
        "origin_country",
        "destination_university",
        "degree_level",
        "is_published",
    )
    list_display_links = ("name",)
    list_editable = ("is_published",)
    list_filter = ("is_published", "destination_university")
    search_fields = ("name", "quote", "destination_university__name")
    list_select_related = ("destination_university",)
    ordering = ("-id",)
    actions = ("publish", "unpublish", "export_as_csv", "delete_selected")
    csv_fields = (
        "name",
        "origin_country",
        "destination_university",
        "degree_level",
        "is_published",
    )

    @admin.display(description=_("Photo"))
    def image_preview(self, obj):
        return thumb(obj.image, str(obj.name), wide=True)

    @admin.action(description=_("Publish selected success stories"), permissions=["change"])
    def publish(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(
            request,
            ngettext(
                "%(count)d success story published.",
                "%(count)d success stories published.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Unpublish selected success stories"), permissions=["change"])
    def unpublish(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(
            request,
            ngettext(
                "%(count)d success story hidden from the homepage.",
                "%(count)d success stories hidden from the homepage.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@admin.register(Notification)
class NotificationAdmin(CsvExportMixin, admin.ModelAdmin):
    """Audit and (re)send platform notifications.

    Targeted delivery is composed in the dashboard UI; here a maintainer can
    inspect what was sent, see how many recipients have read it, and push a
    notification out to its audience again after editing the message.
    """

    list_display = (
        "title",
        "type_badge",
        "recipient_type",
        "sender",
        "recipient_count",
        "read_count",
        "created_at",
    )
    list_filter = ("notification_type", "recipient_type", "created_at")
    search_fields = ("title", "message")
    autocomplete_fields = ("sender",)
    list_select_related = ("sender",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "delivery_summary")
    fieldsets = (
        (
            _("Message"),
            {
                "fields": (
                    "title",
                    "message",
                    "notification_type",
                )
            },
        ),
        (
            _("Audience"),
            {
                "fields": ("recipient_type", "sender"),
                "description": _(
                    "Use “Specific users” from the dashboard notification composer: "
                    "the admin cannot edit a through-model recipient list directly."
                ),
            },
        ),
        (_("Delivery"), {"fields": ("delivery_summary", "created_at")}),
    )
    actions = ("deliver", "export_as_csv", "delete_selected")
    csv_fields = (
        "title",
        "notification_type",
        "recipient_type",
        "sender",
        "created_at",
    )

    TYPE_TONES = {
        Notification.NotificationType.INFO: "info",
        Notification.NotificationType.WARNING: "warning",
        Notification.NotificationType.SUCCESS: "success",
        Notification.NotificationType.ERROR: "danger",
        Notification.NotificationType.REMINDER: "accent",
    }

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _recipients=Count("notificationrecipient", distinct=True),
                _reads=Count(
                    "notificationrecipient",
                    filter=Q(notificationrecipient__is_read=True),
                    distinct=True,
                ),
            )
        )

    @admin.display(description=_("Type"), ordering="notification_type")
    def type_badge(self, obj):
        return pill(obj.get_notification_type_display(), self.TYPE_TONES.get(obj.notification_type, "neutral"))

    @admin.display(description=_("Recipients"), ordering="_recipients")
    def recipient_count(self, obj):
        return obj._recipients

    @admin.display(description=_("Read"), ordering="_reads")
    def read_count(self, obj):
        return obj._reads

    @admin.display(description=_("Delivery"))
    def delivery_summary(self, obj):
        if obj is None or not obj.pk:
            return admin.site.empty_value_display
        url = reverse("admin:core_notificationrecipient_changelist")
        return format_html(
            '{} <a href="{}?notification__id__exact={}">{}</a>',
            ngettext(
                "%(count)d recipient,",
                "%(count)d recipients,",
                obj._recipients if hasattr(obj, "_recipients") else 0,
            )
            % {"count": obj._recipients if hasattr(obj, "_recipients") else 0},
            url,
            obj.pk,
            _("open the recipient list"),
        )

    @admin.action(description=_("Deliver to the selected audience"), permissions=["change"])
    def deliver(self, request, queryset):
        created_total = 0
        for notification in queryset:
            recipients = notification.get_recipients_queryset()
            rows = [
                NotificationRecipient(notification=notification, user=user, is_read=False)
                for user in recipients
            ]
            before = NotificationRecipient.objects.filter(notification=notification).count()
            # ignore_conflicts keeps already-delivered recipients untouched. The
            # return value always has one entry per submitted row, so the number
            # of *new* deliveries is measured by the difference instead.
            NotificationRecipient.objects.bulk_create(rows, ignore_conflicts=True)
            after = NotificationRecipient.objects.filter(notification=notification).count()
            created_total += max(after - before, 0)
        self.message_user(
            request,
            ngettext(
                "%(count)d new delivery created.",
                "%(count)d new deliveries created.",
                created_total,
            )
            % {"count": created_total},
            messages.SUCCESS,
        )


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ("notification", "user", "is_read", "read_at")
    list_editable = ("is_read",)
    list_filter = ("is_read",)
    search_fields = ("notification__title", "user__username", "user__email")
    autocomplete_fields = ("notification", "user")
    list_select_related = ("notification", "user")
    ordering = ("-id",)
    actions = ("mark_read", "mark_unread", "delete_selected")

    @admin.action(description=_("Mark selected deliveries as read"), permissions=["change"])
    def mark_read(self, request, queryset):
        updated = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(
            request,
            ngettext("%(count)d delivery marked as read.", "%(count)d deliveries marked as read.", updated)
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Mark selected deliveries as unread"), permissions=["change"])
    def mark_unread(self, request, queryset):
        updated = queryset.update(is_read=False, read_at=None)
        self.message_user(
            request,
            ngettext(
                "%(count)d delivery marked as unread.",
                "%(count)d deliveries marked as unread.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )
