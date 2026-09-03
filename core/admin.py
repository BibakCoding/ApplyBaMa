from django.contrib import admin

from modeltranslation.admin import TranslationAdmin
from solo.admin import SingletonModelAdmin

from .models import (
    Country, City, TermOption, YearOption, Faculty,
    University, Program,
    User, CompanyProfile, AgentProfile, StudentProfile,
    Application,
    SiteSettings, HowItWorksStep, DocumentRequirement, SuccessStory,
)


# ------------------------------------------------------------------
# Lookup tables
# ------------------------------------------------------------------
@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "language", "nationality", "created_at", "updated_at")
    search_fields = ("name", "language", "nationality")
    ordering = ("name",)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "created_at", "updated_at")
    search_fields = ("name", "country__name")
    list_filter = ("country",)
    ordering = ("country__name", "name")


@admin.register(TermOption)
class TermOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "created_at", "updated_at")
    search_fields = ("label",)
    ordering = ("label",)


@admin.register(YearOption)
class YearOptionAdmin(admin.ModelAdmin):
    list_display = ("value", "created_at", "updated_at")
    search_fields = ("value",)
    ordering = ("value",)


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    filter_horizontal = ("year_options",)
    ordering = ("name",)


# ------------------------------------------------------------------
# University & Program
# ------------------------------------------------------------------
@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "city", "sector", "show_on_homepage", "founded_in", "updated_at")
    search_fields = ("name", "country__name", "city__name")
    list_filter = ("sector", "country", "show_on_homepage")   # ← homepage toggle filter
    filter_horizontal = ("faculties",)
    ordering = ("name",)

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "university", "faculty", "degree", "duration", "status", "updated_at")
    search_fields = ("name", "university__name", "faculty__name")
    list_filter = ("status", "is_active", "degree", "university")
    autocomplete_fields = ("university", "faculty", "term")
    ordering = ("name",)


# ------------------------------------------------------------------
# Users & Profiles
# ------------------------------------------------------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "user_type", "is_active", "date_joined")
    search_fields = ("username", "email")
    list_filter = ("user_type", "is_active")
    ordering = ("-date_joined",)
    raw_id_fields = ('country', 'city', 'citizenship')


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "company_email", "phone", "updated_at")
    search_fields = ("company_name", "user__username", "company_email")
    ordering = ("company_name",)


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "agency", "updated_at")
    search_fields = ("user__username", "agency__company_name")
    list_filter = ("agency",)
    ordering = ("user__username",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "passport", "stage", "language", "updated_at")
    search_fields = ("user__username", "passport", "stage")
    list_filter = ("stage", "language")
    ordering = ("user__username",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_name", "agent", "student", "program", "status", "step", "created_at", "updated_at")
    search_fields = ("application_name", "agent__username", "student__username", "program__name")
    list_filter = ("status", "step", "student_type")
    autocomplete_fields = ("agent", "student", "program")
    ordering = ("-created_at",)


# ==================================================================
# HOMEPAGE MANAGEMENT (all translatable, admin-controlled)
# ==================================================================

@admin.register(SiteSettings)
class SiteSettingsAdmin(TranslationAdmin, SingletonModelAdmin):
    """
    Singleton = only ONE settings object ever exists (admin can only edit,
    never create/delete). TranslationAdmin = language tabs (EN/AR/FA/TR).
    If this combination ever errors on your Django version, simply use:
        class SiteSettingsAdmin(SingletonModelAdmin):
    """
    fieldsets = (
        ("Hero Section", {"fields": ("hero_title", "hero_subtitle", "hero_background_image")}),
        ("Contact & Social", {"fields": ("whatsapp_number", "email", "address", "instagram_url", "telegram_url")}),
    )


@admin.register(HowItWorksStep)
class HowItWorksStepAdmin(TranslationAdmin):
    list_display = ("order", "title", "icon_class", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title",)
    ordering = ("order",)


@admin.register(DocumentRequirement)
class DocumentRequirementAdmin(TranslationAdmin):
    list_display = ("title", "level", "order")
    list_filter = ("level",)
    search_fields = ("title",)
    ordering = ("level", "order")


@admin.register(SuccessStory)
class SuccessStoryAdmin(TranslationAdmin):
    list_display = ("name", "origin_country", "destination_university", "degree_level", "is_published")
    list_filter = ("is_published", "destination_university")
    search_fields = ("name", "quote")
    ordering = ("-id",)
