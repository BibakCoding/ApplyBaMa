"""
Tests for notification utility functions.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.utils.notifications import send_notification, send_welcome_notification
from core.models import Notification, NotificationRecipient

User = get_user_model()


class NotificationUtilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_active=True,
        )

    def test_send_notification_creates_notification(self):
        """Test that send_notification creates a notification and recipient."""
        # Send notification
        result = send_notification(
            user=self.user,
            title="Test Notification",
            message="This is a test notification.",
            notification_type='info',
        )

        # Verify notification was created
        self.assertIsInstance(result, NotificationRecipient)
        self.assertEqual(result.user, self.user)
        self.assertFalse(result.is_read)

        # Verify notification details
        notification = result.notification
        self.assertEqual(notification.title, "Test Notification")
        self.assertEqual(notification.message, "This is a test notification.")
        self.assertEqual(notification.notification_type, 'info')
        self.assertEqual(notification.recipient_type, 'specific')

    def test_send_notification_with_user_id(self):
        """Test that send_notification accepts user ID as parameter."""
        result = send_notification(
            user=self.user.id,
            title="Test Notification",
            message="This is a test notification.",
        )

        self.assertEqual(result.user, self.user)
        self.assertEqual(result.notification.title, "Test Notification")

    def test_send_notification_with_invalid_type(self):
        """Test that invalid notification type defaults to 'info'."""
        result = send_notification(
            user=self.user,
            title="Test Notification",
            message="This is a test notification.",
            notification_type='invalid_type',  # Invalid type
        )

        self.assertEqual(result.notification.notification_type, 'info')

    def test_send_notification_with_sender(self):
        """Test that sender is recorded correctly."""
        sender = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_active=True,
        )

        result = send_notification(
            user=self.user,
            title="Test Notification",
            message="This is a test notification.",
            sender=sender,
        )

        self.assertEqual(result.notification.sender, sender)

    def test_send_notification_with_different_types(self):
        """Test sending different notification types."""
        types = ['info', 'warning', 'success', 'error', 'reminder']

        for notification_type in types:
            result = send_notification(
                user=self.user,
                title=f"{notification_type.capitalize()} Test",
                message=f"This is a {notification_type} notification.",
                notification_type=notification_type,
            )
            self.assertEqual(result.notification.notification_type, notification_type)

    def test_send_welcome_notification(self):
        """Test that send_welcome_notification creates welcome notification."""
        result = send_welcome_notification(self.user)

        # Verify notification was created
        self.assertIsInstance(result, NotificationRecipient)
        self.assertEqual(result.user, self.user)

        # Verify welcome notification content
        notification = result.notification
        self.assertEqual(notification.title, _("Welcome to ApplyBaMa!"))
        self.assertIn("Thank you for registering", notification.message)
        self.assertEqual(notification.notification_type, 'success')

    def test_send_welcome_notification_creates_one_per_user(self):
        """Test that multiple welcome notifications can be sent to same user."""
        # Send first welcome notification
        result1 = send_welcome_notification(self.user)
        # Send second welcome notification
        result2 = send_welcome_notification(self.user)

        self.assertNotEqual(result1, result2)
        self.assertEqual(result1.user, result2.user)
        self.assertEqual(result1.user, self.user)

        # Should have 2 notification recipients for the same user
        notification_recipients = NotificationRecipient.objects.filter(user=self.user)
        self.assertEqual(notification_recipients.count(), 2)

    def test_notification_recipient_count_increases(self):
        """Test that notification count increases when sending notifications."""
        initial_count = NotificationRecipient.objects.count()

        # Send multiple notifications
        send_notification(self.user, "Test 1", "Message 1")
        send_notification(self.user, "Test 2", "Message 2")
        send_notification(self.user, "Test 3", "Message 3")

        final_count = NotificationRecipient.objects.count()
        self.assertEqual(final_count, initial_count + 3)

    def test_notification_model_relationship(self):
        """Test the relationship between Notification and NotificationRecipient."""
        # Create notification
        result = send_notification(self.user, "Test", "Message")

        # Verify relationship
        self.assertEqual(result.notification.title, "Test")
        self.assertEqual(result.user, self.user)

        # Verify related queries work
        notification = Notification.objects.get(id=result.notification.id)
        recipients = notification.recipients.all()
        self.assertIn(self.user, recipients)

        user = User.objects.get(id=self.user.id)
        user_notifications = user.received_notifications.all()
        self.assertIn(notification, user_notifications)