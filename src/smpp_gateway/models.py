from django.contrib.postgres.fields import JSONField
from django.db import models


class MOMessage(models.Model):
    create_time = models.DateTimeField()
    modify_time = models.DateTimeField()
    channel = models.CharField(max_length=32)
    short_message = models.BinaryField()
    params = JSONField()
    status = models.CharField(max_length=32)

    class Meta:
        managed = False
        db_table = "mo_sms"

    def __str__(self):
        return f"{self.params['short_message']} ({self.id})"
