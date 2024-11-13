from django.db import connection, models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from rapidsms.models import Backend
from smpplib.consts import DESCRIPTIONS


class AbstractTimestampModel(models.Model):
    create_time = models.DateTimeField(_("create time"))
    modify_time = models.DateTimeField(_("modify time"))

    class Meta:
        abstract = True


class MOMessage(AbstractTimestampModel, models.Model):
    """Mobile-originated, or inbound, message."""

    class Status(models.TextChoices):
        NEW = "new", _("New")
        PROCESSING = "processing", _("Processing")
        ERROR = "error", _("Error")
        DONE = "done", _("Done")

    backend = models.ForeignKey(
        Backend, on_delete=models.PROTECT, verbose_name=_("backend")
    )
    # Save the raw bytes, in case they're needed later
    short_message = models.BinaryField(_("short message"))
    params = models.JSONField(_("params"))
    status = models.CharField(_("status"), max_length=32, choices=Status.choices)
    error = models.TextField(_("error"), blank=True)

    def get_decoded_short_message(self) -> str:
        data_coding = self.params.get("data_coding", 0)
        short_message = self.short_message.tobytes()  # type: bytes
        # Support the 3 most common data_coding values
        # https://stackoverflow.com/a/11986844/166053
        if data_coding == 0:
            # data_coding 0 means the message is encoded in ASCII, but sometimes
            # we get values values outside the ASCII range, such as b'\xa4' ('¤').
            # Fall back to iso-8859-1 in this case.
            try:
                return short_message.decode("ascii")
            except UnicodeDecodeError:
                return short_message.decode("iso-8859-1")
        if data_coding == 3:
            return short_message.decode("iso-8859-1")
        if data_coding == 8:
            return short_message.decode("utf-16-be")
        raise ValueError(
            f"Unsupported data_coding {data_coding}. Short message: {short_message}"
        )

    @cached_property
    def safe_decoded_short_message(self) -> str:
        try:
            return self.get_decoded_short_message()
        except Exception as err:
            return str(err)

    def __str__(self):
        return f"{self.params['short_message']} ({self.id})"

    class Meta:
        verbose_name = _("mobile-originated message")
        indexes = (
            models.Index(
                # Allow for quick filtering of messages that need to be processed
                fields=["status"],
                name="mo_message_status_idx",
                condition=models.Q(status="new"),  # No way to access Status.NEW here?
            ),
        )


class MTMessage(AbstractTimestampModel, models.Model):
    """Mobile-terminated, or outbound, message."""

    class Status(models.TextChoices):
        NEW = "new", _("New")
        SENDING = "sending", _("Sending")
        SENT = "sent", _("Sent")
        DELIVERED = "delivered", _("Delivered")
        ERROR = "error", _("Error")

    class PriorityFlag(models.IntegerChoices):
        # Based on the priority_flag values in the SMPP Spec
        # https://smpp.org/SMPP_v3_4_Issue1_2.pdf
        LEVEL_0 = 0, _("Level 0 (lowest) priority")
        LEVEL_1 = 1, _("Level 1 priority")
        LEVEL_2 = 2, _("Level 2 priority")
        LEVEL_3 = 3, _("Level 3 (highest) priority")

    backend = models.ForeignKey(
        Backend, on_delete=models.PROTECT, verbose_name=_("backend")
    )
    # SMPP client will decide how to encode it
    short_message = models.TextField(_("short message"))
    params = models.JSONField(_("params"))
    status = models.CharField(_("status"), max_length=32, choices=Status.choices)
    priority_flag = models.IntegerField(
        _("priority flag"), choices=PriorityFlag.choices, null=True
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == MTMessage.Status.NEW:
            with connection.cursor() as curs:
                curs.execute(f"NOTIFY {self.backend.name}")

    def __str__(self):
        return f"{self.short_message} ({self.id})"

    class Meta:
        verbose_name = _("mobile-terminated message")
        indexes = (
            models.Index(
                # Allow for quick filtering of messages that need to be processed
                "status",
                models.F("priority_flag").desc(nulls_last=True),
                name="mt_message_status_idx",
                condition=models.Q(status="new"),  # No way to access Status.NEW here?
            ),
        )


class MTMessageStatus(AbstractTimestampModel, models.Model):
    """Metadata and status information about outbound messages."""

    COMMAND_STATUS_CHOICES = list(DESCRIPTIONS.items())
    mt_message = models.ForeignKey(
        MTMessage, on_delete=models.CASCADE, verbose_name=_("mt message")
    )
    backend = models.ForeignKey(
        Backend, on_delete=models.PROTECT, verbose_name=_("backend")
    )
    sequence_number = models.IntegerField(
        _("sequence number"),
        help_text=_(
            "The initial sequence_number established by us when the message was sent."
        ),
    )
    command_status = models.IntegerField(
        _("command status"), null=True, choices=COMMAND_STATUS_CHOICES
    )
    message_id = models.CharField(
        _("message id"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("The message_id we receive from the MC (via its submit_sm_resp)."),
    )
    delivery_report = models.BinaryField(
        _("delivery report"),
        null=True,
        help_text=_("The delivery_report we receive from the MC (via its deliver_sm)."),
    )

    @cached_property
    def delivery_report_as_bytes(self) -> bytes:
        return self.delivery_report.tobytes()

    def __str__(self):
        return f"{self.backend} ({self.sequence_number})"

    class Meta:
        verbose_name = _("mobile-terminated message status")
        verbose_name_plural = _("mobile-terminated message statuses")
        constraints = [
            models.UniqueConstraint(
                fields=["backend", "sequence_number"], name="unique_seq_num"
            )
        ]
