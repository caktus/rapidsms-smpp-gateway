import json
import logging

from typing import Dict, Optional

from django.db import connection as db_conn
from rapidsms.models import Backend

from smpp_gateway.client import PgSmppClient, PgSmppSequenceGenerator
from smpp_gateway.monitoring import HealthchecksIoWorker

logger = logging.getLogger(__name__)


def get_smpplib_client(
    host: str,
    port: int,
    notify_mo_channel: str,
    backend: Backend,
    submit_sm_params: Dict,
    hc_uuid: str,
) -> PgSmppClient:
    sequence_generator = PgSmppSequenceGenerator(db_conn, backend.name)
    if hc_uuid:
        hc_worker = HealthchecksIoWorker(hc_uuid)
    else:
        hc_worker = None
    client = PgSmppClient(
        notify_mo_channel,
        backend,
        hc_worker,
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
        options["hc_uuid"],
    )
    smpplib_main_loop(
        client,
        options["system_id"],
        options["password"],
        options["interface_version"],
        options["system_type"],
    )
