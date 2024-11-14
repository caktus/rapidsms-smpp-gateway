import json
import logging

from typing import Optional

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
    submit_sm_params: dict,
    set_priority_flag: bool,
    mt_messages_per_second: int,
    hc_check_uuid: str,
    hc_ping_key: str,
    hc_check_slug: str,
) -> PgSmppClient:
    sequence_generator = PgSmppSequenceGenerator(db_conn, backend.name)
    if hc_check_uuid:
        hc_worker = HealthchecksIoWorker(uuid=hc_check_uuid)
    elif hc_ping_key and hc_check_slug:
        hc_worker = HealthchecksIoWorker(ping_key=hc_ping_key, slug=hc_check_slug)
    else:
        hc_worker = None
    client = PgSmppClient(
        notify_mo_channel,
        backend,
        hc_worker,
        submit_sm_params,
        set_priority_flag,
        mt_messages_per_second,
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
        options["set_priority_flag"],
        options["mt_messages_per_second"],
        options["hc_check_uuid"],
        options["hc_ping_key"],
        options["hc_check_slug"],
    )
    smpplib_main_loop(
        client,
        options["system_id"],
        options["password"],
        options["interface_version"],
        options["system_type"],
    )
