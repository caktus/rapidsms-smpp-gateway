import logging
import select

import psycopg2.extensions

from django.db import connection, transaction
from rapidsms.router import lookup_connections, receive

from smpp_gateway.models import MOMessage

logger = logging.getLogger(__name__)


def handle_mo_message(cursor):
    with transaction.atomic():
        sms = (
            MOMessage.objects.filter(status="new")
            .select_for_update(skip_locked=True)
            .first()
        )
        MOMessage.objects.filter(pk=sms.pk).update(status="processing")
    connections = lookup_connections(
        backend="sms_gateway", identities=[sms.params["source_addr"]]
    )
    for conn in connections:
        receive(sms.params["short_message"], conn)


def listen_mo_messages(channel):
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
