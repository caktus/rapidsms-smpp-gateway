import logging

from django.utils import timezone
from rapidsms.backends.base import BackendBase

from smpp_gateway.models import MTMessage

logger = logging.getLogger(__name__)


class SMPPGatewayBackend(BackendBase):
    """Outgoing SMS backend for smpp_gateway."""

    def configure(self, **kwargs):
        pass

    def prepare_request(self, id_, text, identities, context):
        now = timezone.now()
        return [
            {
                "create_time": now,
                "modify_time": now,
                "channel": self.name,
                "short_message": text,
                "params": {"destination_addr": identity},
                "status": MTMessage.NEW,
            }
            for identity in identities
        ]

    def send(self, id_, text, identities, context=None):
        logger.debug("Sending message: %s", text)
        context = context or {}
        kwargs_list = self.prepare_request(id_, text, identities, context)
        MTMessage.objects.bulk_create([MTMessage(**kwargs) for kwargs in kwargs_list])
