# core/admin.py
from django.contrib import admin

from .models import (
    Country, City, TermOption, YearOption, Faculty,
    University, Program,
    User, CompanyProfile, AgentProfile, StudentProfile,
    Application,
)


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


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "city", "sector", "founded_in", "updated_at")
    search_fields = ("name", "country__name", "city__name")
    list_filter = ("sector", "country")
    filter_horizontal = ("faculties", "available_languages")
    ordering = ("name",)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "university",
        "faculty",
        "degree",
        "duration",
        "status",
        "updated_at"
    )
    search_fields = (
        "name",
        "university__name",
        "faculty__name",
    )
    list_filter = ("status", "degree", "university")
    autocomplete_fields = ("university", "faculty", "term")
    ordering = ("name",)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "user_type", "is_active", "date_joined")
    search_fields = ("username", "email")
    list_filter = ("user_type", "is_active")
    ordering = ("-date_joined",)


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
    list_display = (
        "application_name",
        "agent",
        "student",
        "program",
        "status",
        "step",
        "created_at", "updated_at"
    )
    search_fields = (
        "application_name",
        "agent__username",
        "student__username",
        "program__name",
    )
    list_filter = ("status", "step", "student_type")
    autocomplete_fields = ("agent", "student", "program")
    ordering = ("-created_at",)
