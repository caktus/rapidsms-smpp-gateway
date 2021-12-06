import json
import logging

from django.db import connection as db_conn
from rapidsms.models import Backend

from smpp_gateway.client import PgSmppClient, PgSmppSequenceGenerator

logger = logging.getLogger(__name__)


def get_smpplib_client(backend, host, port, submit_sm_params):
    sequence_generator = PgSmppSequenceGenerator(db_conn, backend.name)
    client = PgSmppClient(
        host,
        port,
        allow_unknown_opt_params=True,
        sequence_generator=sequence_generator,
        backend=backend,
        submit_sm_params=submit_sm_params,
    )
    return client


def smpplib_main_loop(client, system_id, password):
    client.connect()
    client.bind_transceiver(system_id=system_id, password=password)
    client.listen()


def start_smpp_client(options):
    backend, _ = Backend.objects.get_or_create(name=options["backend_name"])
    client = get_smpplib_client(
        backend,
        options["host"],
        options["port"],
        json.loads(options["submit_sm_params"]),
    )
    smpplib_main_loop(client, options["system_id"], options["password"])
