from django.apps import AppConfig


class SmppGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smpp_gateway"
    verbose_name = "SMPP gateway"
