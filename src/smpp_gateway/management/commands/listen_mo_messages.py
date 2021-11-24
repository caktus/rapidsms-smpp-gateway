import logging
import select

import psycopg2.extensions

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from rapidsms.router import lookup_connections, receive

from smpp_gateway.models import MOMessage

logger = logging.getLogger(__name__)


SELECT_NEXT_SMS = """
UPDATE mo_sms SET status='processing'
WHERE id = (
    SELECT id
    FROM mo_sms
    WHERE status='new'
    ORDER BY id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING *;
"""


def handle_mo_message(cursor):
    with transaction.atomic():
        # https://webapp.io/blog/postgres-is-the-answer/
        # TODO: can't return ID?
        # msg_id = (
        #     MOMessage.objects.select_for_update(skip_locked=True)
        #     .filter(status="new")
        #     .order_by("id")
        #     .only("id")
        #     .update(status="processing")
        # )
        cursor.execute(SELECT_NEXT_SMS)
        data = cursor.fetchone()
    msg_id = data[0]
    mo_sms = MOMessage.objects.get(id=msg_id)
    connections = lookup_connections(
        backend="sms_gateway", identities=[mo_sms.params["source_addr"]]
    )
    for conn in connections:
        receive(mo_sms.params["short_message"], conn)


class Command(BaseCommand):
    args = ""
    help = "Listen for MO messages."

    def add_arguments(self, parser):
        parser.add_argument(
            "--channel",
            default="new_mo_msg",
        )

    def handle(self, *args, **options):
        channel = options["channel"]
        with connection.cursor() as cursor:
            pg_conn = connection.connection
            pg_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            # https://gist.github.com/pkese/2790749
            cursor.execute("LISTEN new_mo_msg;")
            logger.info(f"Waiting for notifications on channel '{channel}'")
            while True:
                if select.select([pg_conn], [], [], 5) == ([], [], []):
                    logger.debug(".")
                else:
                    pg_conn.poll()
                    while pg_conn.notifies:
                        notify = pg_conn.notifies.pop()
                        logger.info(f"Got NOTIFY:{notify}")
                        handle_mo_message(cursor)
