from django.contrib import admin

from smpp_gateway.models import MOMessage, MTMessage


@admin.register(MOMessage)
class MOMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "decoded_short_message",
        "backend",
        "status",
        "create_time",
    )
    list_filter = ("status", "backend")
    ordering = ("-create_time",)


@admin.register(MTMessage)
class MTMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_message",
        "backend",
        "status",
        "create_time",
    )
    list_filter = ("status", "backend")
    ordering = ("-create_time",)
