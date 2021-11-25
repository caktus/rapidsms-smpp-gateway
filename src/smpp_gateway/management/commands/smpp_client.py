import os

from django.core.management.base import BaseCommand

from smpp_gateway.smpp import start_smpp_client


def default_port():
    port = os.environ.get("SMPPLIB_PORT", 2775)
    return int(port) if port else None


class Command(BaseCommand):
    help = "Start an SMPP client instance."

    def add_arguments(self, parser):
        parser.add_argument("smsc_name")
        parser.add_argument(
            "--host",
            default=os.environ.get("SMPPLIB_HOST"),
        )
        parser.add_argument(
            "--port",
            default=default_port(),
        )
        parser.add_argument(
            "--system-id",
            default=os.environ.get("SMPPLIB_SYSTEM_ID"),
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("SMPPLIB_PASSWORD"),
        )
        parser.add_argument(
            "--submit-sm-params",
            default=os.environ.get("SMPPLIB_SUBMIT_SM_PARAMS"),
        )
        parser.add_argument(
            "--database-url",
            default=os.environ.get("DATABASE_URL"),
        )
        parser.add_argument("--log-file")
        parser.add_argument(
            "--send-bulksms",
            type=int,
            help="Sends the specified number of SMSes in bulk on startup. "
            "Not intended for use with a real MNO.",
        )

    def handle(self, *args, **options):
        start_smpp_client(options)