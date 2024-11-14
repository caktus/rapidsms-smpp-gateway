from unittest import mock

import pytest

from smpplib import consts as smpplib_consts
from smpplib.command import DeliverSM, SubmitSMResp

from smpp_gateway.models import MOMessage, MTMessage
from smpp_gateway.queries import pg_listen
from smpp_gateway.smpp import PgSmppClient, get_smpplib_client
from tests.factories import BackendFactory, MTMessageFactory, MTMessageStatusFactory


@pytest.mark.django_db(transaction=True)
class TestMessageReceivedHandler:
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
            {},  # submit_sm_params
            False,  # set_priority_flag
            20,  # mt_messages_per_second
            "",  # hc_check_uuid
            "",  # hc_ping_key
            "",  # hc_check_slug
        )

        pdu = DeliverSM("deliver_sm")
        pdu.short_message = b"this is a short message"
        pdu.source_addr = "+46166371876"

        listen_conn = pg_listen("notify_mo_channel")

        client.message_received_handler(pdu)

        # should notify the MO listener
        listen_conn.poll()
        assert len(listen_conn.notifies) == 1

        # there should be a message for the MO listener to process
        msg = MOMessage.objects.get()
        assert msg.backend == backend
        assert msg.short_message.tobytes() == pdu.short_message
        assert msg.params["source_addr"] == "+46166371876"
        assert msg.status == MOMessage.Status.NEW

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
            {},  # submit_sm_params
            False,  # set_priority_flag
            20,  # mt_messages_per_second
            "",  # hc_check_uuid
            "",  # hc_ping_key
            "",  # hc_check_slug
        )
        outbound_msg = MTMessageFactory(status=MTMessage.Status.SENT, backend=backend)
        outbound_msg_status = MTMessageStatusFactory(
            mt_message=outbound_msg, message_id="abcdefg"
        )

        pdu = DeliverSM("deliver_sm")
        pdu.short_message = b"this is a delivery receipt"
        pdu.source_addr = "+46166371876"
        pdu.receipted_message_id = "abcdefg"

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

    def test_received_null_short_message(self):
        """When a message is received with a null short_message, persist it
        and notify the MO listener."""
        backend = BackendFactory()
        client = get_smpplib_client(
            "127.0.0.1",
            8000,
            "notify_mo_channel",
            backend,
            {},  # submit_sm_params
            False,  # set_priority_flag
            20,  # mt_messages_per_second
            "",  # hc_check_uuid
            "",  # hc_ping_key
            "",  # hc_check_slug
        )

        pdu = DeliverSM("deliver_sm")
        pdu.short_message = None
        pdu.source_addr = "+46166371876"

        listen_conn = pg_listen("notify_mo_channel")

        client.message_received_handler(pdu)

        # should notify the MO listener
        listen_conn.poll()
        assert len(listen_conn.notifies) == 1

        # there should be a message for the MO listener to process
        msg = MOMessage.objects.get()
        assert msg.backend == backend
        assert msg.short_message == b""
        assert msg.params["source_addr"] == "+46166371876"
        assert msg.status == MOMessage.Status.NEW


@pytest.mark.django_db(transaction=True)
def test_message_sent_handler():
    """The associated MTMessageStatus should be updated with the submission
    status and message_id.
    """
    backend = BackendFactory()
    client = get_smpplib_client(
        "127.0.0.1",
        8000,
        "notify_mo_channel",
        backend,
        {},  # submit_sm_params
        False,  # set_priority_flag
        20,  # mt_messages_per_second
        "",  # hc_check_uuid
        "",  # hc_ping_key
        "",  # hc_check_slug
    )
    outbound_msg = MTMessageFactory(status=MTMessage.Status.SENT, backend=backend)
    outbound_msg_status = MTMessageStatusFactory(mt_message=outbound_msg)

    pdu = SubmitSMResp("submit_sm_resp")
    pdu.sequence = outbound_msg_status.sequence_number
    pdu.status = smpplib_consts.SMPP_ESME_RSUBMITFAIL
    pdu.message_id = "qwerty"

    client.message_sent_handler(pdu)

    outbound_msg_status.refresh_from_db()

    assert outbound_msg_status.command_status == smpplib_consts.SMPP_ESME_RSUBMITFAIL
    assert outbound_msg_status.message_id == "qwerty"


@pytest.mark.django_db(transaction=True)
@mock.patch.object(PgSmppClient, "send_message", return_value=mock.Mock(sequence=1))
class TestSetPriorityFlag:
    def get_client_and_message(
        self,
        submit_sm_params=None,
        set_priority_flag=True,
        message_priority_flag=MTMessage.PriorityFlag.LEVEL_1,
    ):
        backend = BackendFactory()
        client = get_smpplib_client(
            "127.0.0.1",
            8000,
            "notify_mo_channel",
            backend,
            submit_sm_params or {},
            set_priority_flag,
            20,  # mt_messages_per_second
            "",  # hc_check_uuid
            "",  # hc_ping_key
            "",  # hc_check_slug
        )
        message = MTMessageFactory(
            status=MTMessage.Status.NEW,
            backend=backend,
            priority_flag=message_priority_flag,
        )
        return client, message

    def test_set_priority_flag_is_true(self, mock_send_message):
        """If set_priority_flag is True and the priority_flag is set on a MTMessage
        object, the priority_flag param should be set in the PDU.
        """
        client, message = self.get_client_and_message()
        client.receive_pg_notify()

        mock_send_message.assert_called_once()
        assert (
            mock_send_message.call_args.kwargs["priority_flag"] == message.priority_flag
        )

    def test_set_priority_flag_is_true_and_priority_in_submit_sm_params(
        self, mock_send_message
    ):
        """If set_priority_flag is True and the priority_flag is set on a MTMessage
        object and also in the submit_sm_params dictionary, the priority_flag from
        the message object should take precendence.
        """
        client, message = self.get_client_and_message(
            {"priority_flag": MTMessage.PriorityFlag.LEVEL_0}
        )
        client.receive_pg_notify()

        mock_send_message.assert_called_once()
        assert (
            mock_send_message.call_args.kwargs["priority_flag"] == message.priority_flag
        )

    def test_set_priority_flag_is_true_but_priority_not_set(self, mock_send_message):
        """If set_priority_flag is True and but the priority_flag is not set on a
        MTMessage object, the priority_flag param should NOT be set in the PDU.
        """
        client = self.get_client_and_message(message_priority_flag=None)[0]
        client.receive_pg_notify()

        mock_send_message.assert_called_once()
        assert "priority_flag" not in mock_send_message.call_args.kwargs

    def test_set_priority_flag_is_false(self, mock_send_message):
        """If set_priority_flag is False and the priority_flag is set on a
        MTMessage object, the priority_flag param should NOT be set in the PDU.
        """
        client = self.get_client_and_message(set_priority_flag=False)[0]
        client.receive_pg_notify()

        mock_send_message.assert_called_once()
        assert "priority_flag" not in mock_send_message.call_args.kwargs

    def test_set_priority_flag_is_false_but_priority_in_submit_sm_params(
        self, mock_send_message
    ):
        """If set_priority_flag is False and but a priority_flag was set in the
        submit_sm_params dictionary, the priority_flag from submit_sm_params
        should still be set in the PDU.
        """
        priority = MTMessage.PriorityFlag.LEVEL_0
        client, message = self.get_client_and_message(
            {"priority_flag": priority}, False
        )
        client.receive_pg_notify()

        mock_send_message.assert_called_once()
        assert mock_send_message.call_args.kwargs["priority_flag"] == priority
