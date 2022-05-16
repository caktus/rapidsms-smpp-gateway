from django.core.management.base import BaseCommand

from smpp_gateway.subscribers import listen_mo_messages


class Command(BaseCommand):
    help = "Receive inbound MO messages and pass them to RapidSMS."

    def add_arguments(self, parser):
        parser.add_argument("--channel", default="new_mo_msg")

    def handle(self, *args, **options):
        listen_mo_messages(channel=options["channel"])
