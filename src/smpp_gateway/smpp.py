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
from psycopg2.extras import Json

from smpp_gateway.client import ThreadSafeClient

logger = logging.getLogger(__name__)

ASCII_PRINTABLE_BYTES = {ord(c) for c in string.printable}

INSERT_MO_SMS_SQL = """
INSERT INTO smpp_gateway_momessage (
    create_time
    , modify_time
    , channel
    , short_message
    , params
    , status
)
VALUES (
    current_timestamp
    , current_timestamp
    , %s
    , %s
    , %s
    , 'new'
)
"""

TEST_MESSAGES = {
    "short": "هذه رسالة قصيرة.",
    "long": "هذه رسالة أطول لا يمكن احتواؤها في رسالة SMS واحدة. لا يزال ينبغي إعادة تجميعها في رسالة واحدة بواسطة هاتفك.",  # noqa: E501
}

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


def send_message(client, message, **kwargs):
    # Two parts, UCS2, SMS with UDH
    parts, data_coding, esm_class = smpplib.gsm.make_parts(message)
    for short_message in parts:
        client.send_message(
            short_message=short_message,
            data_coding=data_coding,
            esm_class=esm_class,
            **kwargs,
        )


def send_test_replies(client, **kwargs):
    destination_addr = kwargs["destination_addr"]
    if REPLY_COUNTS[destination_addr] >= 3:
        logger.warning(f"Hit reply limit for {destination_addr}; sending no response.")
        return
    REPLY_COUNTS[destination_addr] += 1
    for message in TEST_MESSAGES.values():
        send_message(client, message, **kwargs)


def message_received_handler(smsc_name, system_id, submit_sm_params, pdu):
    mo_params = decoded_params(pdu)
    with db_conn.cursor() as cursor:
        # channel, short_message, params
        args = (f"{smsc_name}_{system_id}", pdu.short_message, Json(mo_params))
        cursor.execute(INSERT_MO_SMS_SQL, args)
        cursor.execute("NOTIFY new_mo_msg;")
    if getattr(pdu, "receipted_message_id") is not None:
        # Don't send replies to delivery receipts. There's probably a better
        # way to tell if this is such a PDU.
        return
    mt_params = submit_sm_params.copy()
    mt_params["source_addr"] = system_id
    mt_params["destination_addr"] = mo_params["source_addr"]
    send_test_replies(pdu.client, **mt_params)


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


def get_smpplib_client(host, port):
    client = ThreadSafeClient(host, port, allow_unknown_opt_params=True)
    # Print when obtain message_id
    client.set_message_sent_handler(
        lambda pdu: sys.stdout.write(
            "sent {} {}\n".format(pdu.sequence, pdu.message_id)
        )
    )
    return client


def send_test_bulksms(client, source_addr, count):
    for x in range(count):
        send_message(
            client, f"Test {x}", source_addr=source_addr, destination_addr="99999"
        )


def smpplib_main_loop(client, system_id, password):
    client.connect()
    client.bind_transceiver(system_id=system_id, password=password)
    client.listen()


def start_smpp_client(options):
    client = get_smpplib_client(options["host"], options["port"])
    client.set_message_received_handler(
        functools.partial(
            message_received_handler,
            options["smsc_name"],
            options["system_id"],
            json.loads(options["submit_sm_params"]),
        )
    )
    client.set_error_pdu_handler(functools.partial(error_pdu_handler, client))
    if options["send_bulksms"]:
        t = Thread(
            target=functools.partial(
                send_test_bulksms, client, options["system_id"], options["send_bulksms"]
            )
        )
        t.start()
    smpplib_main_loop(client, options["system_id"], options["password"])
