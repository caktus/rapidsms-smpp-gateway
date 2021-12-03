import logging
import select

import psycopg2.extensions

from django.db import connection, transaction
from rapidsms.router import lookup_connections, receive

from smpp_gateway.models import MOMessage

logger = logging.getLogger(__name__)


def get_mo_messages(limit=1):
    with transaction.atomic():
        smses = (
            MOMessage.objects.filter(status="new")
            .select_related("backend")
            .select_for_update(skip_locked=True, of=("self",))[:limit]
        )
        MOMessage.objects.filter(pk__in=[sms.pk for sms in smses]).update(
            status="processing"
        )
    return smses


def handle_mo_messages(notify, smses=None):
    if smses is None:
        smses = get_mo_messages()
    for sms in smses:
        connection = lookup_connections(
            backend=sms.backend, identities=[sms.params["source_addr"]]
        )[0]
        fields = {
            "to_addr": sms.params["destination_addr"],
            "from_addr": sms.params["source_addr"],
        }
        receive(sms.decoded_short_message, connection, fields=fields)
    MOMessage.objects.filter(pk__in=[sms.pk for sms in smses]).update(status="done")


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
    smses = get_mo_messages(limit=100)
    while smses:
        handle_mo_messages(None, smses=smses)
        smses = get_mo_messages(limit=100)
    pg_listen(channel, handle_mo_messages)
