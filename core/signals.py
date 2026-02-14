# core/signals.py
import os

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import User, Application


@receiver(pre_save, sender=User)
def delete_old_profile_image(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        old_user = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return False

    old_file = old_user.profile_image
    new_file = instance.profile_image

    # Delete old file if it's being replaced
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


@receiver(pre_save, sender=Application)
def delete_old_application_document(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        old_app = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return False

    old_file = old_app.documents
    new_file = instance.documents

    # Delete old file if it's being replaced
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)
