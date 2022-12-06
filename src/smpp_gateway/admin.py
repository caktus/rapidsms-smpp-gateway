from django.contrib import admin
from smpplib.consts import DESCRIPTIONS

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


class CommandListListFilter(admin.SimpleListFilter):
    title = "command status"
    parameter_name = "command_status"

    def lookups(self, request, model_admin):
        """
        Only show the lookups for command_status values that exist in the database.
        """
        statuses = MTMessageStatus.objects.values_list(
            "command_status", flat=True
        ).distinct()
        return [(status, DESCRIPTIONS.get(status, '')) for status in statuses]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset by mtmessagestatus.command_status
        """
        return queryset.filter(mtmessagestatus__command_status=self.value())


@admin.register(MTMessage)
class MTMessageAdmin(admin.ModelAdmin):
    list_display = (
        "short_message",
        "backend",
        "status",
        "create_time",
    )
    list_filter = (
        "status",
        "backend",
        CommandListListFilter,
    )
    ordering = ("-create_time",)
    inlines = (MTMessageStatusInline,)
