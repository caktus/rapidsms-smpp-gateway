import logging
import select

import psycopg2.extensions

from django.db.models import QuerySet
from rapidsms.router import lookup_connections, receive

from smpp_gateway.models import MOMessage
from smpp_gateway.queries import get_mo_messages_to_process, pg_listen
from smpp_gateway.utils import set_exit_signals

logger = logging.getLogger(__name__)


def handle_mo_messages(smses: QuerySet[MOMessage]):
    received_smses = []
    try:
        for sms in smses:
            connection = lookup_connections(
                backend=sms.backend, identities=[sms.params["source_addr"]]
            )[0]
            fields = {
                "to_addr": sms.params["destination_addr"],
                "from_addr": sms.params["source_addr"],
            }
            receive(sms.decoded_short_message, connection, fields=fields)
            received_smses.append(sms)
    finally:
        if received_smses:
            MOMessage.objects.filter(pk__in=[sms.pk for sms in received_smses]).update(
                status=MOMessage.Status.DONE
            )


def listen_mo_messages(channel: str):
    """Batch process any queued incoming messages, then listen to be notified
    of new arrivals.
    """
    exit_signal_received = set_exit_signals()
    smses = get_mo_messages_to_process(limit=100)
    while smses:
        handle_mo_messages(smses)
        # If an exit was triggered, do so before retrieving more messages to process...
        if exit_signal_received():
            logger.info("Received exit signal, leaving processing loop...")
            return
        smses = get_mo_messages_to_process(limit=100)

    pg_conn = pg_listen(channel)

    while True:
        if select.select([pg_conn], [], [], 5) == ([], [], []):
            logger.debug(f"{channel} .")
        else:
            pg_conn.poll()
            while pg_conn.notifies:
                notify = pg_conn.notifies.pop()  # type: psycopg2.extensions.Notify
                logger.info(f"Got NOTIFY:{notify}")
                smses = get_mo_messages_to_process(limit=1)
                handle_mo_messages(smses)
        if exit_signal_received():
            logger.info("Received exit signal, leaving listen loop...")
            return
