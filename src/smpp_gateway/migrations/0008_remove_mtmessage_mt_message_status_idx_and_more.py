# Generated by Django 4.2.16 on 2024-11-14 09:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("smpp_gateway", "0007_momessage_error_alter_momessage_status"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="mtmessage",
            name="mt_message_status_idx",
        ),
        migrations.AddField(
            model_name="mtmessage",
            name="priority_flag",
            field=models.IntegerField(
                choices=[
                    (0, "Level 0 (lowest) priority"),
                    (1, "Level 1 priority"),
                    (2, "Level 2 priority"),
                    (3, "Level 3 (highest) priority"),
                ],
                null=True,
                verbose_name="priority flag",
            ),
        ),
        migrations.AddIndex(
            model_name="mtmessage",
            index=models.Index(
                models.F("status"),
                models.OrderBy(
                    models.F("priority_flag"), descending=True, nulls_last=True
                ),
                condition=models.Q(("status", "new")),
                name="mt_message_status_idx",
            ),
        ),
    ]
