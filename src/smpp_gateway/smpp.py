import json
import logging

from typing import Dict, Optional

from django.db import connection as db_conn
from rapidsms.models import Backend

from smpp_gateway.client import PgSmppClient, PgSmppSequenceGenerator

logger = logging.getLogger(__name__)


def get_smpplib_client(
    host: str,
    port: int,
    notify_mo_channel: str,
    backend: Backend,
    submit_sm_params: Dict,
) -> PgSmppClient:
    sequence_generator = PgSmppSequenceGenerator(db_conn, backend.name)
    client = PgSmppClient(
        notify_mo_channel,
        backend,
        submit_sm_params,
        host,
        port,
        allow_unknown_opt_params=True,
        sequence_generator=sequence_generator,
    )
    return client


def smpplib_main_loop(
    client: PgSmppClient,
    system_id: str,
    password: str,
    interface_version: Optional[str],
    system_type: Optional[str],
):
    client.connect()
    client.bind_transceiver(
        system_id=system_id,
        password=password,
        interface_version=interface_version,
        system_type=system_type,
    )
    client.listen()


def start_smpp_client(options):
    backend, _ = Backend.objects.get_or_create(name=options["backend_name"])
    client = get_smpplib_client(
        options["host"],
        options["port"],
        options["notify_mo_channel"],
        backend,
        json.loads(options["submit_sm_params"]),
    )
    smpplib_main_loop(
        client,
        options["system_id"],
        options["password"],
        options["interface_version"],
        options["system_type"],
    )
