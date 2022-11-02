import logging

from django.db import connection
from django.utils import timezone
from rapidsms.backends.base import BackendBase

from smpp_gateway.models import MTMessage
from smpp_gateway.utils import grouper

logger = logging.getLogger(__name__)


class SMPPGatewayBackend(BackendBase):
    """Outgoing SMS backend for smpp_gateway."""

    # Optional additional params from:
    # https://github.com/python-smpplib/python-smpplib/blob/d9d91beb2d7f37915b13a064bb93f907379342ec/smpplib/command.py#L652-L700
    OPTIONAL_PARAMS = ("source_addr",)

    def configure(self, **kwargs):
        self.send_group_size = kwargs.get("send_group_size", 100)
        self.socket_timeout = kwargs.get("socket_timeout", 5)

    def prepare_request(self, id_, text, identities, context):
        for identity in identities:
            now = timezone.now()
            params = {
                param: context[param]
                for param in self.OPTIONAL_PARAMS
                if param in context
            }
            params["destination_addr"] = identity
            yield {
                "create_time": now,
                "modify_time": now,
                "backend": self.model,
                "short_message": text,
                "params": params,
                "status": MTMessage.Status.NEW,
            }

    def send(self, id_, text, identities, context=None):
        logger.debug("Sending message: %s", text)
        context = context or {}
        kwargs_generator = self.prepare_request(id_, text, identities, context)
        for kwargs_group in grouper(kwargs_generator, self.send_group_size):
            MTMessage.objects.bulk_create(
                [MTMessage(**kwargs) for kwargs in kwargs_group]
            )
            with connection.cursor() as curs:
                curs.execute(f"NOTIFY {self.model.name}")
