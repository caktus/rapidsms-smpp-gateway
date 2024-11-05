from unittest import mock

import pytest

from smpp_gateway.models import MOMessage
from smpp_gateway.subscribers import handle_mo_messages
from tests.factories import MOMessageFactory


@pytest.mark.django_db
class TestHandleMOMessages:
    def receive_was_called(self, mock_receive: mock.Mock, message: MOMessage):
        return len(
            [
                call
                for call in mock_receive.call_args_list
                if call.args[0] == message.safe_decoded_short_message
            ]
        )

    def test_mark_received_messages_done(self):
        """Handle each incoming message by receving them into RapidSMS and
        marking them as done.
        """
        MOMessageFactory.create_batch(5)
        messages = MOMessage.objects.all()

        with mock.patch("smpp_gateway.subscribers.receive") as mock_receive:
            handle_mo_messages(messages)

        for message in messages:
            message.refresh_from_db()
            assert message.status == MOMessage.Status.DONE
            assert self.receive_was_called(mock_receive, message)

    def test_error_in_middle_of_patch(self):
        """If receiving one message raises an exception, ensure all received
        messages are still marked as done to avoid duplicate receiving.

        Unreceived messages should be left untouched to be retried later.
        """
        MOMessageFactory.create_batch(6)
        bad_short_msg = MOMessage.objects.order_by("pk").first()
        # Invalid data_coding value will cause a decoding failure
        bad_short_msg.params["data_coding"] = 123
        bad_short_msg.save()
        messages = MOMessage.objects.order_by("pk").all()

        with mock.patch("smpp_gateway.subscribers.receive") as mock_receive:
            mock_receive.side_effect = [None, None, Exception("boom"), None, None, None]
            with pytest.raises(Exception, match=r"boom"):
                handle_mo_messages(messages)

        # Message 0 raised a message decoding exception, it should be marked
        # with an error since there is no sense in retrying decoding errors
        # before a code change
        failed_message = messages[0]
        failed_message.refresh_from_db()
        assert failed_message.status == MOMessage.Status.ERROR
        # receive() should never be called for a message with a failed decoding
        assert self.receive_was_called(mock_receive, failed_message) == 0

        for received_message in messages[1:3]:
            # Messages 1, 2 should be received and marked as done
            received_message.refresh_from_db()
            assert received_message.status == MOMessage.Status.DONE
            assert self.receive_was_called(mock_receive, received_message)

        # Message 3 raised an exception, should not be marked done so it
        # will be retried later
        failed_message = messages[3]
        failed_message.refresh_from_db()
        assert failed_message.status == MOMessage.Status.NEW
        assert self.receive_was_called(mock_receive, failed_message)

        for other_message in messages[4:]:
            # Messages 4, 5 should remain new to be received later
            other_message.refresh_from_db()
            assert other_message.status == MOMessage.Status.NEW
            assert not self.receive_was_called(mock_receive, other_message)
