"""Tests for the customised control center.

They cover the four things that regressed before and would regress silently
again:

1. the dashboard must render **every** registered model (the old template
   dropped whatever was not in its hardcoded list),
2. the theme must stay variable-driven and cover light **and** dark,
3. passwords typed into the user admin must be hashed,
4. the bulk actions must actually change data (and export real CSV),
   not just appear in the drop-down.
"""

import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import VerificationCode

from .models import (
    Application,
    City,
    Country,
    Notification,
    NotificationRecipient,
    Program,
    SuccessStory,
    University,
    User,
)

THEME_CSS = Path(settings.BASE_DIR) / "static" / "css" / "admin" / "admin-theme.css"
DASHBOARD_CSS = Path(settings.BASE_DIR) / "static" / "css" / "admin" / "admin-dashboard.css"


class AdminBaseTestCase(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="pass12345"
        )
        self.client.force_login(self.superuser)

    def post_action(self, url_name, action, pks, **extra):
        data = {
            "action": action,
            "_selected_action": [str(pk) for pk in pks],
            "index": "0",
            "select_across": "0",
        }
        data.update(extra)
        return self.client.post(reverse(url_name), data)


class AdminDashboardTests(AdminBaseTestCase):
    def test_dashboard_renders_for_a_superuser(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin-dashboard")
        self.assertContains(response, "admin-kpis")
        self.assertContains(response, "dashboard-grid")

    def test_anonymous_visitors_are_sent_to_the_admin_login(self):
        self.client.logout()
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_dashboard_links_every_model_the_user_may_view(self):
        """Regression: models outside the hardcoded list used to disappear."""
        response = self.client.get(reverse("admin:index"))
        content = response.content.decode()

        app_list = response.context["app_list"]
        expected = [
            model["admin_url"]
            for app in app_list
            for model in app["models"]
            if model.get("admin_url")
        ]
        self.assertGreater(len(expected), 10)
        for url in expected:
            self.assertIn(url, content, msg=f"{url} is missing from the dashboard")

    def test_every_registered_model_gets_exactly_one_row(self):
        response = self.client.get(reverse("admin:index"))
        content = response.content.decode()
        app_list = response.context["app_list"]
        expected = sum(len(app["models"]) for app in app_list)

        self.assertEqual(content.count('class="model-item"'), expected)
        for model in admin.site._registry:
            opts = model._meta
            try:
                url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
            except Exception:  # pragma: no cover - defensive for third-party admins
                continue
            self.assertIn(url, content, msg=f"{opts.label} is not reachable from the dashboard")

    def test_kpi_tiles_show_live_database_counts(self):
        University.objects.create(name="One")
        University.objects.create(name="Two")
        University.objects.create(name="Three")

        response = self.client.get(reverse("admin:index"))
        html = response.content.decode()

        self.assertRegex(
            html,
            r'admin-kpi__value">3</span>\s*<span class="admin-kpi__label">Universities</span>',
        )

    def test_attention_strip_only_lists_real_problems(self):
        quiet = self.client.get(reverse("admin:index"))
        self.assertNotContains(quiet, "admin-attention")

        SuccessStory.objects.create(
            name="Hidden story",
            origin_country="Iran",
            destination_university=University.objects.create(name="A"),
            degree_level="Master",
            quote="…",
            is_published=False,
        )

        loud = self.client.get(reverse("admin:index"))
        self.assertContains(loud, "admin-attention")
        self.assertContains(loud, "Success stories not published")
        self.assertNotContains(loud, "Unused verification codes")


class AdminThemeTests(AdminBaseTestCase):
    def test_admin_assets_are_linked(self):
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "css/admin/admin-theme.css")
        self.assertContains(response, "css/admin/admin-dashboard.css")
        self.assertContains(response, "js/admin/admin.js")

    def test_theme_loads_after_djangos_own_stylesheets(self):
        """The override depends on source order, so pin it down."""
        program = self._create_program()
        response = self.client.get(reverse("admin:core_program_change", args=[program.pk]))
        html = response.content.decode()

        self.assertLess(html.index("admin/css/forms.css"), html.index("css/admin/admin-theme.css"))

    def test_theme_defines_light_dark_and_auto_states(self):
        css = THEME_CSS.read_text(encoding="utf-8")

        self.assertIn('html[data-theme="light"]', css)
        self.assertIn('html[data-theme="dark"]', css)
        self.assertIn("@media (prefers-color-scheme: dark)", css)
        # Both dark paths must remap Django's own variables, not just ours.
        self.assertEqual(css.count("--body-bg: var(--admin-canvas);"), 3)

    def test_theme_has_no_legacy_hardcoded_overrides(self):
        """The old file forced white inputs with !important and broke dark mode."""
        raw = THEME_CSS.read_text(encoding="utf-8")
        # Comments describe the old hacks on purpose; only declarations matter.
        css = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)

        self.assertNotIn("#container input", css)
        self.assertNotIn("background-color: #1e293b", css)
        self.assertNotIn("background-color: #fff", css)
        # !important is allowed only in the reduced-motion and print blocks,
        # which are the final two sections of the file.
        head, _, tail = css.partition("@media (prefers-reduced-motion")
        self.assertNotIn("!important", head)
        self.assertIn("!important", tail)

    def test_dashboard_css_is_token_driven(self):
        css = DASHBOARD_CSS.read_text(encoding="utf-8")

        self.assertNotIn("!important", css)
        self.assertIn("var(--admin-surface)", css)
        self.assertNotIn("#F8FAFC", css)

    def _create_program(self):
        return Program.objects.create(
            name="Computer Science",
            university=University.objects.create(name="Example"),
            degree="bachelor",
        )


class AdminUserAdminTests(AdminBaseTestCase):
    def test_user_admin_extends_djangos_own(self):
        model_admin = admin.site._registry[User]

        self.assertIsInstance(model_admin, DjangoUserAdmin)
        self.assertIs(model_admin.add_form, AdminUserCreationForm)

    def test_password_created_through_the_admin_is_hashed(self):
        response = self.client.post(
            reverse("admin:core_user_add"),
            {
                "username": "newcomer",
                "password1": "very-secret-123",
                "password2": "very-secret-123",
                "usable_password": "true",
            },
        )
        self.assertEqual(response.status_code, 302)

        created = User.objects.get(username="newcomer")
        self.assertNotEqual(created.password, "very-secret-123")
        self.assertTrue(created.password.startswith("pbkdf2_"))
        self.assertTrue(created.check_password("very-secret-123"))

    def test_user_changelist_renders_pills_and_stays_sortable(self):
        User.objects.create_user(username="anagent", password="pass12345", user_type="agent")

        response = self.client.get(reverse("admin:core_user_changelist"))
        self.assertContains(response, "admin-pill")

        sorted_response = self.client.get(reverse("admin:core_user_changelist"), {"o": "2"})
        self.assertEqual(sorted_response.status_code, 200)


class AdminActionTests(AdminBaseTestCase):
    def test_publish_and_unpublish_success_stories(self):
        story = SuccessStory.objects.create(
            name="Story",
            origin_country="Iran",
            destination_university=University.objects.create(name="Example"),
            degree_level="Master",
            quote="…",
            is_published=False,
        )

        self.post_action("admin:core_successstory_changelist", "publish", [story.pk])
        story.refresh_from_db()
        self.assertTrue(story.is_published)

        self.post_action("admin:core_successstory_changelist", "unpublish", [story.pk])
        story.refresh_from_db()
        self.assertFalse(story.is_published)

    def test_activate_and_deactivate_programs(self):
        program = Program.objects.create(
            name="Business",
            university=University.objects.create(name="Example"),
            degree="master",
            is_active=True,
        )

        self.post_action("admin:core_program_changelist", "deactivate", [program.pk])
        program.refresh_from_db()
        self.assertFalse(program.is_active)

        self.post_action("admin:core_program_changelist", "activate", [program.pk])
        program.refresh_from_db()
        self.assertTrue(program.is_active)

    def test_application_status_actions(self):
        agent = User.objects.create_user(username="ag", password="pass12345", user_type="agent")
        student = User.objects.create_user(username="st", password="pass12345")
        application = Application.objects.create(agent=agent, student=student)

        self.post_action("admin:core_application_changelist", "mark_finished", [application.pk])
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.FINISHED)

        self.post_action("admin:core_application_changelist", "reopen", [application.pk])
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.IN_PROGRESS)

    def test_csv_export_is_utf8_with_a_bom(self):
        university = University.objects.create(name="دانشگاه تهران", sector="public")

        response = self.post_action(
            "admin:core_university_changelist", "export_as_csv", [university.pk]
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        body = response.content
        # Excel only detects UTF-8 when the file starts with a BOM.
        self.assertTrue(body.startswith("\ufeff".encode("utf-8")))
        self.assertIn("دانشگاه تهران".encode("utf-8"), body)
        self.assertIn(b"name", body)

    def test_deliver_action_creates_recipient_rows(self):
        User.objects.create_user(username="u1", password="pass12345")
        User.objects.create_user(username="u2", password="pass12345")
        notification = Notification.objects.create(
            title="Maintenance", message="…", recipient_type="all", sender=self.superuser
        )

        self.post_action("admin:core_notification_changelist", "deliver", [notification.pk])

        self.assertEqual(
            NotificationRecipient.objects.filter(notification=notification).count(),
            User.objects.filter(is_active=True).count(),
        )

        # Running it twice must not duplicate deliveries.
        self.post_action("admin:core_notification_changelist", "deliver", [notification.pk])
        self.assertEqual(
            NotificationRecipient.objects.filter(notification=notification).count(),
            User.objects.filter(is_active=True).count(),
        )

    def test_verification_codes_can_be_invalidated_and_pruned(self):
        user = User.objects.create_user(username="coder", password="pass12345")
        expired = VerificationCode.objects.create(user=user, code="111111", code_type="registration")
        VerificationCode.objects.filter(pk=expired.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        self.post_action("admin:authentication_verificationcode_changelist", "delete_expired", [expired.pk])
        self.assertFalse(VerificationCode.objects.filter(pk=expired.pk).exists())


class AdminPermissionTests(AdminBaseTestCase):
    def test_models_the_staff_user_cannot_view_are_not_shown(self):
        staff = User.objects.create_user(
            username="limited", password="pass12345", is_staff=True
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="view_program"),
            Permission.objects.get(codename="change_program"),
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("admin:core_program_changelist"), html)
        self.assertNotIn(reverse("admin:core_successstory_changelist"), html)
        # A KPI tile for a model they cannot open must not become a link.
        self.assertNotIn(f'href="{reverse("admin:core_university_changelist")}"', html)

    def test_limited_staff_get_a_working_changelist(self):
        staff = User.objects.create_user(username="watch", password="pass12345", is_staff=True)
        Program.objects.create(
            name="Medicine",
            university=University.objects.create(name="Example"),
            degree="master",
            status="quota_full",
        )
        staff.user_permissions.add(Permission.objects.get(codename="view_program"))
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:core_program_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Medicine")
        # The status column is a pill, and it stays sortable through it.
        self.assertContains(response, "admin-pill")
        self.assertEqual(
            self.client.get(reverse("admin:core_program_changelist"), {"o": "1"}).status_code,
            200,
        )


class AdminFormHardeningTests(AdminBaseTestCase):
    """Guards for two defects found while auditing the real pages."""

    def test_university_form_does_not_render_every_city(self):
        """Regression: City has ~32,000 rows and the plain <select> made this form
        a 1.7 MB page that took ~13 s to render. It must use autocomplete."""
        turkey = Country.objects.create(name="Turkey")
        Country.objects.create(name="Germany")
        for name in ("Ankara", "Berlin", "Cairo"):
            City.objects.create(name=name, country=turkey)

        response = self.client.get(reverse("admin:core_university_add"))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)

        self.assertIn("admin-autocomplete", html)
        # One option per linked object (plus the empty label), never one per row.
        country_select = html.split('id="id_country"', 1)[1].split("</select>", 1)[0]
        self.assertLess(country_select.count("<option"), 10)
        self.assertLess(len(response.content), 200_000)

    def test_login_page_footer_does_not_claim_a_signed_in_user(self):
        """The footer used to print "Signed in as" (with an empty name) and a
        Change-password link to anonymous visitors."""
        self.client.logout()
        response = self.client.get(reverse("admin:login"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Signed in as", html)
        self.assertNotIn(reverse("admin:password_change"), html)
        self.assertIn("admin-footer-row", html)
