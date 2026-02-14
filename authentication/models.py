# authentication/models.py

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class VerificationCode(models.Model):
    class CodeType(models.TextChoices):
        REGISTRATION = "registration", _("Registration")
        RESET = "reset", _("Password Reset")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_codes",
    )
    code = models.CharField(max_length=6)
    code_type = models.CharField(max_length=12, choices=CodeType.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    token = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "code_type", "code"]),
            models.Index(fields=["token"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} [{self.code_type}] → {self.code}"

    def save(self, *args, **kwargs):
        # On first save, set expiration
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=15)
            if self.code_type == self.CodeType.RESET and not self.token:
                # 192 bits of URL-safe entropy
                self.token = get_random_string(length=43)  # ~258 bits base64
        super().save(*args, **kwargs)

    @classmethod
    def create_registration(cls, user):
        """
        Invalidate old registration codes and issue a fresh 6-digit code.
        """
        # Invalidate
        cls.objects.filter(
            user=user, code_type=cls.CodeType.REGISTRATION, used=False
        ).update(used=True)

        # Create new
        code = f"{secrets.randbelow(10 ** 6):06d}"
        return cls.objects.create(
            user=user,
            code=code,
            code_type=cls.CodeType.REGISTRATION,
        )

    @classmethod
    def create_reset(cls, user):
        """
        Invalidate old reset codes and issue a fresh reset code + token.
        """
        cls.objects.filter(
            user=user, code_type=cls.CodeType.RESET, used=False
        ).update(used=True)

        code = f"{secrets.randbelow(10 ** 6):06d}"
        vc = cls(
            user=user,
            code=code,
            code_type=cls.CodeType.RESET,
        )
        # Will auto-generate expires_at and token via save()
        vc.save()
        return vc
