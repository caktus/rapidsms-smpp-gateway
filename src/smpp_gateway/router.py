from rapidsms.messages.incoming import IncomingMessage
from rapidsms.messages.outgoing import OutgoingMessage
from rapidsms.router.blocking import BlockingRouter

from smpp_gateway.models import MTMessage


class PriorityIncomingMessage(IncomingMessage):
    def respond(self, text, **kwargs):
        fields = kwargs.get("fields", {})
        if "priority_flag" not in fields:
            fields["priority_flag"] = MTMessage.PriorityFlag.LEVEL_2.value
        kwargs["fields"] = fields
        return super().respond(text, **kwargs)


class PriorityOutgoingMessage(OutgoingMessage):
    def extra_backend_context(self):
        context = super().extra_backend_context()
        context["priority_flag"] = self.fields.get(
            "priority_flag", MTMessage.PriorityFlag.LEVEL_2.value
        )
        return context


class PriorityBlockingRouter(BlockingRouter):
    def new_incoming_message(self, text, connections, class_=IncomingMessage, **kwargs):
        return super().new_incoming_message(
            text, connections, class_=PriorityIncomingMessage, **kwargs
        )

    def new_outgoing_message(self, text, connections, class_=OutgoingMessage, **kwargs):
        return super().new_incoming_message(
            text, connections, class_=PriorityOutgoingMessage, **kwargs
        )
