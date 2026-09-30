from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_chat_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="messageattachment",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="messageattachment",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
