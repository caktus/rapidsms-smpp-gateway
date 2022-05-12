import logging

from django.db.models import QuerySet
from rapidsms.router import lookup_connections, receive

from smpp_gateway.models import MOMessage
from smpp_gateway.queries import get_mo_messages_to_process, pg_listen, pg_poll

logger = logging.getLogger(__name__)


def handle_mo_messages(smses: QuerySet[MOMessage]):
    for sms in smses:
        connection = lookup_connections(
            backend=sms.backend, identities=[sms.params["source_addr"]]
        )[0]
        fields = {
            "to_addr": sms.params["destination_addr"],
            "from_addr": sms.params["source_addr"],
        }
        receive(sms.decoded_short_message, connection, fields=fields)
    MOMessage.objects.filter(pk__in=[sms.pk for sms in smses]).update(
        status=MOMessage.Status.DONE
    )


def fetch_and_handle_mo_messages(notify):
    """In response to a notification, fetch one incoming message and
    process it.
    """
    smses = get_mo_messages_to_process(limit=1)
    handle_mo_messages(smses)


def listen_mo_messages(channel):
    """Batch process any queued incoming messages, then listen to be notified
    of new arrivals.
    """
    smses = get_mo_messages_to_process(limit=100)
    while smses:
        handle_mo_messages(smses)
        smses = get_mo_messages_to_process(limit=100)

    pg_conn = pg_listen(channel)
    pg_poll(channel, pg_conn, fetch_and_handle_mo_messages)
