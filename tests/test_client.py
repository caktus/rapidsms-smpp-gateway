import pytest

from smpplib.command import DeliverSM

from smpp_gateway.models import MOMessage, MTMessage
from smpp_gateway.queries import pg_listen
from smpp_gateway.smpp import get_smpplib_client
from tests.factories import BackendFactory, MTMessageFactory, MTMessageStatusFactory
from tests.utils import drain_conn


@pytest.mark.django_db(transaction=True)
class TestMessageReceivedHandler(object):
    def test_received_mo_message(self):
        """When a message is received that is not a receipt
        acknowledgement, persist it and notify the MO listener.
        """
        backend = BackendFactory()
        client = get_smpplib_client(
            "127.0.0.1",
            8000,
            "notify_mo_channel",
            backend,
            {},
        )

        pdu = DeliverSM("deliver_sm")
        pdu.short_message = b"this is a short message"
        pdu.source_addr = "111.222.333.444"

        listen_conn = pg_listen("notify_mo_channel")

        client.message_received_handler(pdu)

        # should notify the MO listener
        listen_conn.poll()
        assert len(listen_conn.notifies) == 1

        # there should be a message for the MO listener to process
        msg = MOMessage.objects.get()
        assert msg.backend == backend
        assert msg.short_message.tobytes() == pdu.short_message
        assert msg.params["source_addr"] == "111.222.333.444"
        assert msg.status == MOMessage.Status.NEW

        drain_conn(listen_conn)

    def test_received_message_receipt(self):
        """When a message is received that is a receipt acknowledgement,
        persist the delivery report on the appropriate outbound messages.
        """
        backend = BackendFactory()
        client = get_smpplib_client(
            "127.0.0.1",
            8000,
            "notify_mo_channel",
            backend,
            {},
        )
        outbound_msg = MTMessageFactory(status=MTMessage.Status.SENT, backend=backend)
        outbound_msg_status = MTMessageStatusFactory(mt_message=outbound_msg)

        pdu = DeliverSM("deliver_sm")
        pdu.short_message = b"this is a delivery receipt"
        pdu.source_addr = "111.222.333.444"
        pdu.receipted_message_id = outbound_msg_status.message_id

        listen_conn = pg_listen("notify_mo_channel")

        client.message_received_handler(pdu)

        # should *not* notify the MO listener
        listen_conn.poll()
        assert len(listen_conn.notifies) == 0

        outbound_msg.refresh_from_db()
        outbound_msg_status.refresh_from_db()

        assert outbound_msg.status == MTMessage.Status.DELIVERED
        assert (
            outbound_msg_status.delivery_report.tobytes()
            == b"this is a delivery receipt"
        )

        drain_conn(listen_conn)
