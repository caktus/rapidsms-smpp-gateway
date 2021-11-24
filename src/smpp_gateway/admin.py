from django.contrib import admin
from smpp_gateway.models import MOMessage


@admin.register(MOMessage)
class MOMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_message",
        "channel",
        "status",
        "create_time",
    )
    list_filter = ("status", "channel")
    ordering = ("-create_time",)
