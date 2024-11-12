from unittest import mock

import pytest

from smpplib import consts as smpplib_consts
from smpplib.command import DeliverSM, SubmitSMResp

from smpp_gateway.models import MOMessage, MTMessage
from smpp_gateway.queries import get_mt_messages_to_send, pg_listen
from smpp_gateway.smpp import get_smpplib_client
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
            False,  # listen_transactional_mt_messages_only
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
            False,  # listen_transactional_mt_messages_only
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
            False,  # listen_transactional_mt_messages_only
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
        False,  # listen_transactional_mt_messages_only
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
def test_listen_transactional_mt_messages_only_set():
    """If listen_transactional_mt_messages_only is set, when client.receive_pg_notify()
    is called it fetches and sends one transactional message.
    """
    backend = BackendFactory()
    client = get_smpplib_client(
        "127.0.0.1",
        8000,
        "notify_mo_channel",
        backend,
        {},  # submit_sm_params
        True,  # listen_transactional_mt_messages_only
        "",  # hc_check_uuid
        "",  # hc_ping_key
        "",  # hc_check_slug
    )

    messages = MTMessageFactory.create_batch(
        3, status=MTMessage.Status.NEW, backend=backend, is_transactional=True
    )

    # The client should have received 3 notifications with the message IDs as payloads
    assert [i.payload for i in client._pg_conn.notifies] == [
        str(i.id) for i in messages
    ]

    with mock.patch.object(
        client, "split_and_send_message", return_value=[mock.Mock(sequence=1)]
    ) as mock_split_and_send_message, mock.patch(
        "smpp_gateway.client.get_mt_messages_to_send",
        wraps=get_mt_messages_to_send,
    ) as mock_get_mt_messages_to_send:
        client.receive_pg_notify()

    # The sent message should be the last message created, since we pop from the
    # list of notifications in receive_pg_notify()
    last_msg = messages[-1]
    mock_get_mt_messages_to_send.assert_called_once()
    assert mock_get_mt_messages_to_send.call_args.kwargs["extra_filter"] == {
        "id": last_msg.id,
        "is_transactional": True,
    }
    mock_split_and_send_message.assert_called_once()
    assert MTMessage.objects.filter(status=MTMessage.Status.SENT).count() == 1
    assert MTMessage.objects.get(status=MTMessage.Status.SENT) == last_msg
    assert MTMessage.objects.filter(status=MTMessage.Status.NEW).count() == 2


@pytest.mark.django_db(transaction=True)
def test_listen_transactional_mt_messages_only_not_set():
    """If listen_transactional_mt_messages_only is not set, when client.receive_pg_notify()
    is called it fetches and sends all new messages, regardless of whether they
    are transactional or not.
    """
    backend = BackendFactory()
    client = get_smpplib_client(
        "127.0.0.1",
        8000,
        "notify_mo_channel",
        backend,
        {},  # submit_sm_params
        False,  # listen_transactional_mt_messages_only
        "",  # hc_check_uuid
        "",  # hc_ping_key
        "",  # hc_check_slug
    )
    transactional = MTMessageFactory.create_batch(
        3, status=MTMessage.Status.NEW, backend=backend, is_transactional=True
    )
    MTMessageFactory.create_batch(
        3, status=MTMessage.Status.NEW, backend=backend, is_transactional=False
    )

    # The client should have received 6 notifications. The payload for the first
    # 3 should be the message IDs and for the others it should be an empty string
    assert [i.payload for i in client._pg_conn.notifies] == (
        [str(i.id) for i in transactional] + [""] * 3
    )

    with mock.patch.object(
        client,
        "split_and_send_message",
        side_effect=[[mock.Mock(sequence=i)] for i in range(6)],
    ) as mock_split_and_send_message, mock.patch(
        "smpp_gateway.client.get_mt_messages_to_send",
        wraps=get_mt_messages_to_send,
    ) as mock_get_mt_messages_to_send:
        client.receive_pg_notify()

    mock_get_mt_messages_to_send.assert_called_once()
    assert mock_get_mt_messages_to_send.call_args.kwargs["extra_filter"] is None
    assert mock_split_and_send_message.call_count == 6
    assert MTMessage.objects.filter(status=MTMessage.Status.SENT).count() == 6
    assert MTMessage.objects.filter(status=MTMessage.Status.NEW).count() == 0
