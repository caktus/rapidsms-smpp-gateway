from django.contrib import admin

from smpp_gateway.models import MOMessage, MTMessage, MTMessageStatus


@admin.register(MOMessage)
class MOMessageAdmin(admin.ModelAdmin):
    list_display = (
        "decoded_short_message",
        "backend",
        "status",
        "create_time",
    )
    list_filter = ("status", "backend")
    ordering = ("-create_time",)


class MTMessageStatusInline(admin.TabularInline):
    model = MTMessageStatus
    readonly_fields = (
        "backend",
        "sequence_number",
        "command_status",
        "message_id",
        "delivery_report_as_bytes",
    )
    can_delete = False
    extra = 0


@admin.register(MTMessage)
class MTMessageAdmin(admin.ModelAdmin):
    list_display = (
        "short_message",
        "backend",
        "status",
        "create_time",
    )
    list_filter = ("status", "backend")
    ordering = ("-create_time",)
    inlines = (MTMessageStatusInline,)
