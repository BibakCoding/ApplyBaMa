import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_public_ids(apps, schema_editor):
    """Give every existing account a unique 16-digit ID.

    Random rather than derived from the primary key: the ID is shared between
    strangers, so it must not be guessable. Users created after this migration
    get theirs from the model's save() hook.
    """
    User = apps.get_model("core", "User")
    for user in User.objects.filter(public_id__isnull=True):
        while True:
            candidate = f"{secrets.randbelow(10**16):016d}"
            if not User.objects.filter(public_id=candidate).exists():
                break
        user.public_id = candidate
        user.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_messageattachment_timestamps"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="action_url",
            field=models.CharField(blank=True, max_length=200, verbose_name="Action URL"),
        ),
        migrations.AddField(
            model_name="user",
            name="public_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Shareable 16-digit ID. Give it to an agent so they can find "
                    "you and request to represent you."
                ),
                max_length=16,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="AgentLinkRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("declined", "Declined"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=10,
                        verbose_name="Status",
                    ),
                ),
                (
                    "message",
                    models.TextField(
                        blank=True,
                        help_text="A short note from the requester to the target.",
                        max_length=500,
                        verbose_name="Message",
                    ),
                ),
                (
                    "responded_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Responded At"),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_requests_sent",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Requester",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_requests_received",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Target",
                    ),
                ),
            ],
            options={
                "verbose_name": "Agent Link Request",
                "verbose_name_plural": "Agent Link Requests",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["target", "status"], name="core_agentl_target__16cd98_idx"),
                    models.Index(
                        fields=["requester", "status"], name="core_agentl_request_df6646_idx"
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "pending")),
                        fields=("requester", "target"),
                        name="agent_request_pending_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("requester", models.F("target")), _negated=True),
                        name="agent_request_not_self",
                    ),
                ],
            },
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
    ]
