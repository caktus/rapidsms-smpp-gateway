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
    # Save the raw bytes, in case they're needed later
    short_message = models.BinaryField()
    params = JSONField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.params['short_message']} ({self.id})"


class MTMessage(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("error", "Error"),
    )

    create_time = models.DateTimeField()
    modify_time = models.DateTimeField()
    channel = models.CharField(max_length=32)
    # SMPP client will decide how to encode it
    short_message = models.TextField()
    params = JSONField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.short_message} ({self.id})"
