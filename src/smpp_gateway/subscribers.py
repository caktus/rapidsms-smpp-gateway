import logging
import select

import psycopg2.extensions

from django.db import connection, transaction
from rapidsms.router import lookup_connections, receive

from smpp_gateway.models import MOMessage, MTMessage

logger = logging.getLogger(__name__)


def handle_mo_message(notify):
    with transaction.atomic():
        sms = (
            MOMessage.objects.filter(status="new")
            .select_for_update(skip_locked=True)
            .first()
        )
        if sms is not None:
            MOMessage.objects.filter(pk=sms.pk).update(status="processing")
    if sms is not None:
        backend_name = sms.channel.split("_")[0]
        connections = lookup_connections(
            backend=backend_name, identities=[sms.params["source_addr"]]
        )
        for conn in connections:
            receive(sms.params["short_message"], conn)


def pg_listen(channel, handler):
    with connection.cursor() as cursor:
        pg_conn = connection.connection
        pg_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        # https://gist.github.com/pkese/2790749
        cursor.execute(f"LISTEN {channel};")
        logger.info(f"Waiting for notifications on channel '{channel}'")
        while True:
            if select.select([pg_conn], [], [], 5) == ([], [], []):
                logger.debug(f"{channel} .")
            else:
                pg_conn.poll()
                while pg_conn.notifies:
                    notify = pg_conn.notifies.pop()
                    logger.info(f"Got NOTIFY:{notify}")
                    handler(notify)


def listen_mo_messages(channel):
    pg_listen(channel, handle_mo_message)


def get_mt_messages(channel, limit):
    with transaction.atomic():
        smses = (
            MTMessage.objects.filter(status="new")
            .select_for_update(skip_locked=True)
            .values("id", "short_message", "params")[:limit]
        )
        if smses:
            pks = [sms["pk"] for sms in smses]
            MTMessage.objects.filter(pk__in=pks).update(status="processing")
    return smses
