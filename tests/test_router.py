from django.test import TestCase
from django.test.utils import override_settings

from smpp_gateway.router import PriorityBlockingRouter

from .factories import ConnectionFactory


@override_settings(
    INSTALLED_BACKENDS={
        "smppsim": {
            "ENGINE": "smpp_gateway.outgoing.SMPPGatewayBackend",
        }
    }
)
class PriorityBlockingRouterTest(TestCase):
    def setUp(self):
        self.router = PriorityBlockingRouter(apps=[], backends={})
        self.connection = ConnectionFactory()

    def test_new_incoming_message(self):
        """The new_incoming_message method should return a PriorityIncomingMessage
        object by default.
        """
        msg = self.router.new_incoming_message(
            text="foo", connections=[self.connection]
        )
        self.assertIsInstance(msg, PriorityBlockingRouter.incoming_message_class)

    def test_incoming_message_respond_sets_priority_flag(self):
        """Calling respond() on a PriorityIncomingMessage object should add
        a priority_flag in the fields dict, if one is not already set.
        """
        msg = self.router.new_incoming_message(
            text="foo", connections=[self.connection]
        )

        # Set priority_flag to the default value of 2 if not already set
        result = msg.respond("response")
        self.assertEqual(
            result["fields"]["priority_flag"], msg.default_priority_flag.value
        )

        # Do not change the priority_flag if it's already set
        result = msg.respond("response", fields={"priority_flag": 1})
        self.assertEqual(result["fields"]["priority_flag"], 1)

    def test_new_outgoing_message(self):
        """The new_outgoing_message method should return a PriorityOutgoingMessage
        object by default.
        """
        msg = self.router.new_outgoing_message(
            text="foo", connections=[self.connection]
        )
        self.assertIsInstance(msg, PriorityBlockingRouter.outgoing_message_class)

    def test_outgoing_message_extra_backend_context_has_priority_flag(self):
        """The new_outgoing_message method should return a PriorityOutgoingMessage
        object by default.
        """
        msg = self.router.new_outgoing_message(
            text="foo", connections=[self.connection], fields={"priority_flag": 2}
        )
        context = msg.extra_backend_context()
        self.assertEqual(context["priority_flag"], 2)

        # priority_flag should default to 1 if not set in the message's fields
        msg = self.router.new_outgoing_message(
            text="foo", connections=[self.connection]
        )
        context = msg.extra_backend_context()
        self.assertEqual(context["priority_flag"], msg.default_priority_flag.value)
