import logging

from typing import Any, Dict, List

import psycopg2.extensions

from django.db import connection, transaction
from django.db.models import QuerySet
from rapidsms.models import Backend

from smpp_gateway.models import MOMessage, MTMessage

logger = logging.getLogger(__name__)


def pg_listen(channel: str) -> psycopg2.extensions.connection:
    """Return a new connection listening for notifications on `channel`.

    Can be used like:
    >>> conn = pg_listen("my_channel")
    >>> conn.poll()
    >>> for notify in conn.notifies:
    >>>    print(f"I got a notification: {notify}")
    """
    with connection.cursor() as cursor:
        pg_conn = connection.connection
        pg_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        # https://gist.github.com/pkese/2790749
        cursor.execute(f"LISTEN {channel};")
        logger.info(f"Waiting for notifications on channel '{channel}'")

    return pg_conn


def pg_notify(channel: str):
    """Send a notification on `channel` with empty payload."""
    with connection.cursor() as cursor:
        cursor.execute(f"NOTIFY {channel};")


def get_mt_messages_to_send(limit: int, backend: Backend) -> List[Dict[str, Any]]:
    """Fetches up to `limit` messages intended for `backend`, updates their
    status to SENDING, and returns select fields from the model.
    """
    with transaction.atomic():
        smses = list(
            MTMessage.objects.filter(status=MTMessage.Status.NEW, backend=backend)
            .select_for_update(skip_locked=True)
            .values("id", "short_message", "params")[:limit]
        )
        if smses:
            pks = [sms["id"] for sms in smses]
            logger.debug(
                f"get_mt_messages_to_send: Marking {pks} as {MTMessage.Status.SENDING.label}"
            )
            MTMessage.objects.filter(pk__in=pks).update(status=MTMessage.Status.SENDING)
    return smses


def get_mo_messages_to_process(limit: int = 1) -> QuerySet[MOMessage]:
    """Fetches up to `limit` incoming messages while updating their
    status to PROCESSING.
    """
    with transaction.atomic():
        smses = (
            MOMessage.objects.filter(status=MOMessage.Status.NEW)
            .select_related("backend")
            .select_for_update(skip_locked=True, of=("self",))[:limit]
        )
        pks = [sms.pk for sms in smses]
        logger.debug(
            f"get_mo_messages_to_process: Marking {pks} as {MOMessage.Status.PROCESSING.label}"
        )
        MOMessage.objects.filter(pk__in=pks).update(status=MOMessage.Status.PROCESSING)
    return smses
