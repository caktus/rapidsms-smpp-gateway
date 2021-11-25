# Generated by Django 2.2.24 on 2021-11-25 00:57

import django.contrib.postgres.fields.jsonb

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MOMessage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("create_time", models.DateTimeField()),
                ("modify_time", models.DateTimeField()),
                ("channel", models.CharField(max_length=32)),
                ("short_message", models.BinaryField()),
                ("params", django.contrib.postgres.fields.jsonb.JSONField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("processing", "Processing"),
                            ("done", "Done"),
                            ("error", "Error"),
                        ],
                        max_length=32,
                    ),
                ),
            ],
        ),
    ]