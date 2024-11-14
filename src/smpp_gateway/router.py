from rapidsms.messages.incoming import IncomingMessage
from rapidsms.messages.outgoing import OutgoingMessage
from rapidsms.router.blocking import BlockingRouter

from smpp_gateway.models import MTMessage


class PriorityIncomingMessage(IncomingMessage):
    default_priority_flag = MTMessage.PriorityFlag.LEVEL_2

    def respond(self, text, **kwargs):
        fields = kwargs.get("fields", {})
        if "priority_flag" not in fields:
            fields["priority_flag"] = self.default_priority_flag.value
        kwargs["fields"] = fields
        return super().respond(text, **kwargs)


class PriorityOutgoingMessage(OutgoingMessage):
    default_priority_flag = MTMessage.PriorityFlag.LEVEL_1

    def extra_backend_context(self):
        context = super().extra_backend_context()
        context["priority_flag"] = self.fields.get(
            "priority_flag", self.default_priority_flag.value
        )
        return context


class PriorityBlockingRouter(BlockingRouter):
    incoming_message_class = PriorityIncomingMessage
    outgoing_message_class = PriorityOutgoingMessage

    def new_incoming_message(self, text, connections, class_=None, **kwargs):
        if class_ is None:
            class_ = self.incoming_message_class
        return super().new_incoming_message(text, connections, class_=class_, **kwargs)

    def new_outgoing_message(self, text, connections, class_=None, **kwargs):
        if class_ is None:
            class_ = self.outgoing_message_class
        return super().new_outgoing_message(text, connections, class_=class_, **kwargs)
