import logging
import select
import socket

from typing import Dict

import smpplib
import smpplib.client
import smpplib.consts
import smpplib.exceptions
import smpplib.gsm

from django.utils import timezone
from rapidsms.models import Backend
from smpplib.command import Command, DeliverSM, SubmitSMResp

from smpp_gateway.models import MOMessage, MTMessage, MTMessageStatus
from smpp_gateway.queries import get_mt_messages_to_send, pg_listen, pg_notify
from smpp_gateway.utils import decoded_params, set_exit_signals

logger = logging.getLogger(__name__)


class PgSmppSequenceGenerator(smpplib.client.SimpleSequenceGenerator):
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


class PgSmppClient(smpplib.client.Client):
    """
    Thread-safe smpplib Client that waits for messages to send via
    Postgres' LISTEN statement. Loosely adapted from:
    https://stackoverflow.com/a/51105047/166053 and
    https://gist.github.com/pkese/2790749
    """

    def __init__(
        self,
        notify_mo_channel: str,
        backend: Backend,
        submit_sm_params: Dict,
        *args,
        **kwargs,
    ):
        self.exit_signal_received = set_exit_signals()
        self.notify_mo_channel = notify_mo_channel
        self.backend = backend
        self.submit_sm_params = submit_sm_params
        super().__init__(*args, **kwargs)
        self._pg_conn = pg_listen(self.backend.name)

    # ############### Handlers ################

    def message_received_handler(self, pdu: DeliverSM):
        """Called by smpplib base Client."""
        mo_params = decoded_params(pdu)
        if mo_params.get("receipted_message_id"):
            self._save_delivery_receipt(pdu, mo_params)
        else:
            self._create_mo_message(pdu, mo_params)

    def _save_delivery_receipt(self, pdu: DeliverSM, params):
        """We received an update that an outbound message was delivered.
        Mark it as delivered.
        """
        count = MTMessageStatus.objects.filter(
            backend=self.backend,
            message_id=params["receipted_message_id"],
        ).update(
            modify_time=timezone.now(),
            delivery_report=pdu.short_message,
        )
        if count == 0:
            logger.warning(
                f"Found no MTMessageStatus for backend={self.backend}, "
                f"message_id={params['receipted_message_id']}. "
                f"delivery_report={pdu.short_message}"
            )
        count = MTMessage.objects.filter(
            backend=self.backend,
            mtmessagestatus__message_id=params["receipted_message_id"],
        ).update(
            modify_time=timezone.now(),
            status=MTMessage.Status.DELIVERED,
        )

    def _create_mo_message(self, pdu: DeliverSM, params):
        """We received a message. Insert into DB and notify the
        listen_mo_messages process.
        """
        now = timezone.now()
        MOMessage.objects.create(
            create_time=now,
            modify_time=now,
            backend=self.backend,
            short_message=pdu.short_message,
            params=params,
            status=MOMessage.Status.NEW,
        )
        pg_notify(self.notify_mo_channel)

    def message_sent_handler(self, pdu: SubmitSMResp):
        """Called by smpplib base Client."""
        params = decoded_params(pdu)
        count = MTMessageStatus.objects.filter(
            backend=self.backend,
            sequence_number=pdu.sequence,
        ).update(
            modify_time=timezone.now(),
            command_status=pdu.status,
            message_id=params["message_id"] or "",
        )
        if count == 0:
            logger.warning(
                f"Found no MTMessageStatus for {self.backend}, {pdu.sequence}. "
                f"status={pdu.status}, message_id={params['message_id']}"
            )

    def error_pdu_handler(self, pdu: Command):
        """Called by smpplib base Client when incoming PDU has status set to
        anything other than OK.
        """
        if pdu.command == "submit_sm_resp":
            # update MTMessageStatus record with the error
            self.message_sent_handler(pdu)
        logger.warning(
            "({}) {}: {}".format(
                pdu.status,
                pdu.command,
                smpplib.consts.DESCRIPTIONS.get(pdu.status, "Unknown status"),
            ),
        )

    # ############### Listen for and send MT Messages ################

    def receive_pg_notifies(self):
        self._pg_conn.poll()
        while self._pg_conn.notifies:
            notify = self._pg_conn.notifies.pop()
            logger.info(f"Got NOTIFY:{notify}")
            self.send_mt_messages()

    def send_mt_messages(self):
        smses = get_mt_messages_to_send(limit=100, backend=self.backend)
        submit_sm_resps = []
        for sms in smses:
            params = {**self.submit_sm_params, **sms["params"]}
            pdus = self.split_and_send_message(sms["short_message"], **params)
            # Create placeholder MTMessageStatus objects in the DB, which
            # the message_sent handler will later update with the actual command_status
            # and message_id (and eventually maybe a delivery report).
            now = timezone.now()
            submit_sm_resps.extend(
                [
                    MTMessageStatus(
                        create_time=now,
                        modify_time=now,
                        mt_message_id=sms["id"],
                        backend=self.backend,
                        sequence_number=pdu.sequence,
                    )
                    for pdu in pdus
                ]
            )
        pks = [sms["id"] for sms in smses]
        MTMessage.objects.filter(pk__in=pks).update(
            status=MTMessage.Status.SENT,
            modify_time=timezone.now(),
        )
        MTMessageStatus.objects.bulk_create(submit_sm_resps)

    def split_and_send_message(self, message, **kwargs):
        """
        Splits and sends the given message, returning the underlying PDUs.
        The "source_addr" and "destination_addr" keyword arguments are required
        by python-smpplib.
        """
        # Two parts, UCS2, SMS with UDH
        parts, data_coding, esm_class = smpplib.gsm.make_parts(message)
        return [
            self.send_message(
                short_message=short_message,
                data_coding=data_coding,
                esm_class=esm_class,
                **kwargs,
            )
            for short_message in parts
        ]

    # ############### Main loop ################

    def listen(self, ignore_error_codes=None, auto_send_enquire_link=True):
        self.logger.info("Entering main listen loop")
        # Look for and send up to 100 messages on start up
        self.send_mt_messages()
        while True:
            # When either main socket has data or _pg_conn has data, select.select will return
            rlist, _, _ = select.select(
                [self._socket, self._pg_conn], [], [], self.timeout
            )
            if not rlist and auto_send_enquire_link:
                self.logger.debug("Socket timeout, listening again")
                pdu = smpplib.smpp.make_pdu("enquire_link", client=self)
                self.send_pdu(pdu)
                # Look for and send up to 100 messages every 5 seconds
                self.send_mt_messages()
                continue
            elif not rlist:
                # backwards-compatible with existing behavior
                raise socket.timeout()
            for ready_socket in rlist:
                if ready_socket is self._socket:
                    self.read_once(ignore_error_codes, auto_send_enquire_link)
                else:
                    self.receive_pg_notifies()
            if self.exit_signal_received():
                self.logger.info("Got exit signal, leaving listen loop")
                self.safe_disconnect()
                return

    def safe_disconnect(self):
        if self._socket is not None:
            try:
                self.logger.info("Unbinding...")
                self.unbind()
            except:
                self.logger.exception("Ignoring exception during unbind")
            try:
                # Disconnect writes its own "Disconnecting..." message
                self.disconnect()
            except:
                self.logger.exception("Ignoring exception during disconnect")
