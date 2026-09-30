"""Support entry point tests: the footer's Contact Us section and the
floating "Contact Support" button.

These are markup contracts, not behaviour: the button must always offer a
route into the support chat — directly for a signed-in visitor, through the
login form carrying ``?next=`` back to the chat page for an anonymous one
(the auth views validate the target, so the link cannot become an open
redirect).
"""

from django.test import TestCase
from django.urls import reverse

from core.models import SiteSettings, User


def make_visitor(username, **extra):
    defaults = {
        "email": "%s@example.com" % username,
        "password": "Password123!",
        "email_verified": True,
    }
    defaults.update(extra)
    return User.objects.create_user(username=username, **defaults)


class SiteSettingsContactFieldsTests(TestCase):
    """The Contact Us block reads SiteSettings, so its fields must exist."""

    def test_settings_carry_the_contact_channels(self):
        settings = SiteSettings.objects.get_or_create(pk=1)[0]

        self.assertTrue(settings.email)
        self.assertTrue(settings.whatsapp_number)
        # The floating button and the footer chat button are hrefs built by
        # the template; nothing here needs JS.

    def test_chat_storage_policy_fields_exist(self):
        settings = SiteSettings.objects.get_or_create(pk=1)[0]

        self.assertGreaterEqual(settings.chat_default_file_mb, 1)
        self.assertGreater(settings.chat_max_total_storage_mb, 0)


class FooterContactSectionTests(TestCase):
    def test_home_page_renders_the_contact_section(self):
        response = self.client.get(reverse("main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact Us")
        self.assertContains(response, "Contact Support")

    def test_footer_button_points_anonymous_visitors_to_login_with_next(self):
        response = self.client.get(reverse("main"))

        # The next target is the dashboard's chat page, URL-encoded inside
        # the login URL — get_next_target() validates it on arrival.
        self.assertContains(
            response,
            reverse("login") + "?next=" + reverse("dashboard") + "%3Fpage%3Dchat",
        )

    def test_footer_button_points_signed_in_users_straight_to_chat(self):
        visitor = make_visitor("footer_student")
        self.client.force_login(visitor)

        response = self.client.get(reverse("main"))

        self.assertContains(response, reverse("dashboard") + "?page=chat")
        self.assertNotContains(response, reverse("login") + "?next=")


class FloatingSupportButtonTests(TestCase):
    def test_the_button_is_included_on_every_page_via_base(self):
        # The home page (a full-page template)...
        home = self.client.get(reverse("main"))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, 'id="abSupportBtn"')

        # ...and the login page (a different block layout) both carry it.
        login = self.client.get(reverse("login"))
        self.assertEqual(login.status_code, 200)
        self.assertContains(login, 'id="abSupportBtn"')

    def test_the_button_carries_the_minimize_control_and_static_script(self):
        response = self.client.get(reverse("main"))

        self.assertContains(response, "ab-support-min")
        self.assertContains(response, "static/js/support.js")
        self.assertContains(response, "static/css/pages/support.css")

    def test_button_href_follows_the_authentication_state(self):
        anonymous = self.client.get(reverse("main"))
        self.assertContains(
            anonymous,
            reverse("login") + "?next=" + reverse("dashboard") + "%3Fpage%3Dchat",
        )

        visitor = make_visitor("float_student")
        self.client.force_login(visitor)
        signed_in = self.client.get(reverse("main"))

        self.assertContains(signed_in, reverse("dashboard") + "?page=chat")

    def test_app_config_publishes_the_login_url_and_support_strings(self):
        response = self.client.get(reverse("main"))

        # json_script emits a raw JSON block (the template file is UTF-8, and
        # Django only escapes &, < and > inside it).
        self.assertContains(response, '"login": "/en/auth/login/"')
        self.assertContains(response, "Chat with the Apply BM team")


class SupportChatRedirectTests(TestCase):
    """The chat page stays behind @login_required — by design.

    The button's anonymous href lands on the login form with the chat page
    as ?next=; this is the flow that makes "log in to chat with support"
    work end to end.
    """

    def test_chat_page_requires_login(self):
        response = self.client.get(reverse("dashboard"), {"page": "chat"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("next=", response.url)

    def test_login_bounce_preserves_the_chat_target(self):
        chat_target = reverse("dashboard") + "?page=chat"

        response = self.client.get(chat_target)

        self.assertEqual(response.status_code, 302)
        self.assertIn("page%3Dchat", response.url)
