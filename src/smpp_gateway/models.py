from django.contrib.postgres.fields import JSONField
from django.db import models


class MOMessage(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("error", "Error"),
    )

    create_time = models.DateTimeField()
    modify_time = models.DateTimeField()
    channel = models.CharField(max_length=32)
    short_message = models.BinaryField()
    params = JSONField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)

    class Meta:
        managed = False
        db_table = "mo_sms"

    def __str__(self):
        return f"{self.params['short_message']} ({self.id})"
