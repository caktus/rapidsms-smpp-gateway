import json
import logging

from django.db import connection as db_conn
from rapidsms.models import Backend

from smpp_gateway.client import PgSmppClient, PgSmppSequenceGenerator

logger = logging.getLogger(__name__)


def get_smpplib_client(
    notify_mo_channel, backend, host, port, submit_sm_params
) -> PgSmppClient:
    sequence_generator = PgSmppSequenceGenerator(db_conn, backend.name)
    client = PgSmppClient(
        notify_mo_channel,
        host,
        port,
        allow_unknown_opt_params=True,
        sequence_generator=sequence_generator,
        backend=backend,
        submit_sm_params=submit_sm_params,
    )
    return client


def smpplib_main_loop(client: PgSmppClient, system_id: str, password: str):
    client.connect()
    client.bind_transceiver(system_id=system_id, password=password)
    client.listen()


def start_smpp_client(options):
    backend, _ = Backend.objects.get_or_create(name=options["backend_name"])
    client = get_smpplib_client(
        options["notify_mo_channel"],
        backend,
        options["host"],
        options["port"],
        json.loads(options["submit_sm_params"]),
    )
    smpplib_main_loop(client, options["system_id"], options["password"])
