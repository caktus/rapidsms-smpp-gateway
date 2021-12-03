from django.contrib.postgres.fields import JSONField
from django.db import connection, models
from django.utils.functional import cached_property
from rapidsms.models import Backend


class MOMessage(models.Model):
    NEW = "new"
    STATUS_CHOICES = (
        (NEW, "New"),
        ("processing", "Processing"),
        ("done", "Done"),
    )

    create_time = models.DateTimeField()
    modify_time = models.DateTimeField()
    backend = models.ForeignKey(Backend, on_delete=models.PROTECT)
    # Save the raw bytes, in case they're needed later
    short_message = models.BinaryField()
    params = JSONField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)

    @cached_property
    def decoded_short_message(self):
        data_coding = self.params.get("data_coding", 0)
        short_message = self.short_message.tobytes()
        if data_coding == 0:
            return short_message.decode("ascii")
        if data_coding == 8:
            return short_message.decode("utf-16-be")
        raise ValueError(
            f"Unsupported data_coding {data_coding}. Short message: {short_message}"
        )

    def __str__(self):
        return f"{self.params['short_message']} ({self.id})"


class MTMessage(models.Model):
    NEW = "new"
    STATUS_CHOICES = (
        (NEW, "New"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("error", "Error"),
    )

    create_time = models.DateTimeField()
    modify_time = models.DateTimeField()
    backend = models.ForeignKey(Backend, on_delete=models.PROTECT)
    # SMPP client will decide how to encode it
    short_message = models.TextField()
    params = JSONField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == "new":
            with connection.cursor() as curs:
                curs.execute(f"NOTIFY {self.backend.name}")

    def __str__(self):
        return f"{self.short_message} ({self.id})"


class MTMessageStatus(models.Model):
    """
    Database table for collecting the various information about MT messages
    we sent, including:
    - The initial sequence_number established by us when the message was sent
    - The message_id we receive from the MC (via its submit_sm_resp)
    - The delivery_report we receive from the MC (via its deliver_sm)
    """

    mt_message = models.ForeignKey(MTMessage, on_delete=models.CASCADE)
    backend = models.ForeignKey(Backend, on_delete=models.PROTECT)
    sequence_number = models.IntegerField()
    command_status = models.IntegerField(null=True)
    message_id = models.CharField(max_length=255, blank=True, default="")
    delivery_report = models.BinaryField(null=True)

    @cached_property
    def delivery_report_as_bytes(self):
        return self.delivery_report.tobytes()

    def __str__(self):
        return f"{self.backend} ({self.sequence_number})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["backend", "sequence_number"], name="unique_seq_num"
            )
        ]
