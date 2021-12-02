import logging
import select
import socket

import psycopg2.extensions
import smpplib

from django.db import connection, transaction

from smpp_gateway.models import MTMessage

logger = logging.getLogger(__name__)


class PgSequenceGenerator(smpplib.client.SimpleSequenceGenerator):
    """
    smpplib sequence generator that uses a Postgres sequence to persist
    sequence numbers across restarts and client instances. See:
    https://www.postgresql.org/docs/10/sql-createsequence.html
    """

    def __init__(self, conn, backend_name):
        self.conn = conn
        self.sequence_name = f"smpp_gateway_sequence_{backend_name}"
        with conn.cursor() as curs:
            curs.execute(
                f"""
                CREATE SEQUENCE IF NOT EXISTS {self.sequence_name}
                    MINVALUE {self.MIN_SEQUENCE}
                    MAXVALUE {self.MAX_SEQUENCE}
                    CYCLE
                """
            )

    def _fetchone(self, query):
        with self.conn.cursor() as curs:
            curs.execute(query)
            return curs.fetchone()[0]

    @property
    def sequence(self):
        "Current (last) value of the sequence."
        return self._fetchone(f"SELECT last_value from {self.sequence_name}")

    def next_sequence(self):
        "Increments and returns the next value of the sequence."
        return self._fetchone(f"SELECT nextval('{self.sequence_name}')")


class ThreadSafeClient(smpplib.client.Client):
    """
    Thread-safe smpplib Client, adapted from:
    https://stackoverflow.com/a/51105047/166053
    """

    def __init__(self, *args, **kwargs):
        self.backend = kwargs.pop("backend")
        super().__init__(*args, **kwargs)
        # Any data received by this queue will be sent
        # self._send_queue = collections.deque()
        # # Any data sent to ssock shows up on rsock
        # self._rsock, self._ssock = socket.socketpair()

        with connection.cursor() as cursor:
            self._pg_conn = connection.connection
            self._pg_conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
            )
            # https://gist.github.com/pkese/2790749
            cursor.execute(f"LISTEN {self.backend.name};")
            logger.info(f"Waiting for notifications on channel '{self.backend.name}'")

    def smpplib_send_message(self, message, **kwargs):
        # Two parts, UCS2, SMS with UDH
        parts, data_coding, esm_class = smpplib.gsm.make_parts(message)
        for short_message in parts:
            self.send_message(
                short_message=short_message,
                data_coding=data_coding,
                esm_class=esm_class,
                **kwargs,
            )

    def get_mt_messages(self, limit):
        with transaction.atomic():
            smses = (
                MTMessage.objects.filter(status="new")
                .select_for_update(skip_locked=True)
                .values("id", "short_message", "params")[:limit]
            )
            if smses:
                pks = [sms["id"] for sms in smses]
                MTMessage.objects.filter(pk__in=pks).update(status="sending")
        return smses

    def send_mt_messages(self, notify):
        smses = self.get_mt_messages(limit=100)
        while smses:
            for sms in smses:
                self.smpplib_send_message(sms["short_message"], **sms["params"])
            MTMessage.objects.filter(pk__in=[sms["id"] for sms in smses]).update(
                status="sent"
            )
            smses = self.get_mt_messages(limit=100)

    def receive_pg_notifies(self):
        self._pg_conn.poll()
        while self._pg_conn.notifies:
            notify = self._pg_conn.notifies.pop()
            logger.info(f"Got NOTIFY:{notify}")
            self.send_mt_messages(notify)

    def listen(self, ignore_error_codes=None, auto_send_enquire_link=True):
        while True:
            # When either main socket has data or rsock has data, select.select will return
            rlist, _, _ = select.select(
                [self._socket, self._pg_conn], [], [], self.timeout
            )
            if not rlist and auto_send_enquire_link:
                self.logger.debug("Socket timeout, listening again")
                pdu = smpplib.smpp.make_pdu("enquire_link", client=self)
                self.send_pdu(pdu)
                continue
            elif not rlist:
                # backwards-compatible with existing behavior
                raise socket.timeout()
            for ready_socket in rlist:
                if ready_socket is self._socket:
                    self.read_once(ignore_error_codes, auto_send_enquire_link)
                else:
                    self.receive_pg_notifies()
