import base64
import functools
import json
import logging
import string
import sys

from collections import defaultdict
from threading import Thread

import smpplib.client
import smpplib.consts
import smpplib.gsm

from django.db import connection as db_conn
from django.utils import timezone
from rapidsms.models import Backend

from smpp_gateway.client import PgSequenceGenerator, ThreadSafeClient
from smpp_gateway.models import MOMessage
from smpp_gateway.subscribers import get_mt_messages, pg_listen

logger = logging.getLogger(__name__)

ASCII_PRINTABLE_BYTES = {ord(c) for c in string.printable}


REPLY_COUNTS = defaultdict(int)


def maybe_decode(value):
    if isinstance(value, bytes):
        if all(b in ASCII_PRINTABLE_BYTES for b in value):
            return value.decode("ascii")
        else:
            return base64.b64encode(value).decode("utf-8")
    return value


def decoded_params(pdu):
    return {key: maybe_decode(getattr(pdu, key)) for key in pdu.params.keys()}


def smpplib_send_message(client, message, **kwargs):
    # Two parts, UCS2, SMS with UDH
    parts, data_coding, esm_class = smpplib.gsm.make_parts(message)
    for short_message in parts:
        client.send_message(
            short_message=short_message,
            data_coding=data_coding,
            esm_class=esm_class,
            **kwargs,
        )


def message_received_handler(backend, system_id, submit_sm_params, pdu):
    now = timezone.now()
    mo_params = decoded_params(pdu)
    MOMessage.objects.create(
        create_time=now,
        modify_time=now,
        backend=backend,
        short_message=pdu.short_message,
        params=mo_params,
        status=MOMessage.NEW,
    )
    with db_conn.cursor() as cursor:
        cursor.execute("NOTIFY new_mo_msg;")


def error_pdu_handler(client, pdu):
    params = decoded_params(pdu)
    logger.debug(str(params))
    raise smpplib.exceptions.PDUError(
        "({}) {}: {}".format(
            pdu.status,
            pdu.command,
            smpplib.consts.DESCRIPTIONS.get(pdu.status, "Unknown status"),
        ),
        int(pdu.status),
    )


def get_smpplib_client(backend_name, host, port):
    sequence_generator = PgSequenceGenerator(db_conn, backend_name)
    client = ThreadSafeClient(
        host, port, allow_unknown_opt_params=True, sequence_generator=sequence_generator
    )
    # Print when obtain message_id
    client.set_message_sent_handler(
        lambda pdu: sys.stdout.write(
            "sent {} {}\n".format(pdu.sequence, pdu.message_id)
        )
    )
    return client


def send_test_bulksms(client, source_addr, count):
    for x in range(count):
        smpplib_send_message(
            client, f"Test {x}", source_addr=source_addr, destination_addr="99999"
        )


def smpplib_main_loop(client, system_id, password):
    client.connect()
    client.bind_transceiver(system_id=system_id, password=password)
    client.listen()


def send_mt_messages(client, channel, notify):
    smses = get_mt_messages(channel, limit=100)
    while smses:
        for sms in smses:
            smpplib_send_message(client, sms["short_message"], **sms["params"])
        smses = get_mt_messages(channel, limit=100)


def listen_mt_messages(client, channel):
    # Send any queued messages on startup
    send_mt_messages(client, channel, None)
    # Listen for more messages to send
    pg_listen(channel, functools.partial(send_mt_messages, client, channel))


def start_smpp_client(options):
    backend, _ = Backend.objects.get_or_create(name=options["backend_name"])
    client = get_smpplib_client(backend.name, options["host"], options["port"])
    client.set_message_received_handler(
        functools.partial(
            message_received_handler,
            backend,
            options["system_id"],
            json.loads(options["submit_sm_params"]),
        )
    )
    client.set_error_pdu_handler(functools.partial(error_pdu_handler, client))
    if options["send_bulksms"]:
        t_bulk = Thread(
            target=functools.partial(
                send_test_bulksms, client, options["system_id"], options["send_bulksms"]
            )
        )
        t_bulk.start()
    t_mt = Thread(target=functools.partial(listen_mt_messages, client, backend))
    # FIXME: The whole program should die if this thread dies, otherwise no SMS will be sent...
    t_mt.start()
    smpplib_main_loop(client, options["system_id"], options["password"])
