import pytest

from smpp_gateway.models import MTMessage
from smpp_gateway.queries import get_mt_messages_to_send
from tests.factories import BackendFactory, MTMessageFactory


@pytest.mark.django_db
class TestGetMessagesToSend(object):
    def test_empty(self):
        """Return an empty list if there are no queued outbound messages."""
        messages = get_mt_messages_to_send(100, BackendFactory())
        assert messages == []

    def test_partial_page(self):
        """Return fewer than `limit` messages if appropriate."""
        backend = BackendFactory()
        MTMessageFactory.create_batch(5, backend=backend)

        messages = get_mt_messages_to_send(100, backend)

        assert len(messages) == 5

    def test_full_page(self):
        """Return only `limit` messages if more are present."""
        backend = BackendFactory()
        MTMessageFactory.create_batch(5, backend=backend)

        messages = get_mt_messages_to_send(3, backend)

        assert len(messages) == 3

    def test_new_messages_only(self):
        """Return only messages with status NEW."""
        backend = BackendFactory()
        new_messages = [MTMessageFactory(backend=backend, status=MTMessage.Status.NEW)]
        for other_status in [
            val for val in MTMessage.Status.values if val != MTMessage.Status.NEW
        ]:
            MTMessageFactory.create_batch(
                3,
                backend=backend,
                status=other_status,
            )
        new_messages.append(
            MTMessageFactory(backend=backend, status=MTMessage.Status.NEW)
        )

        messages = get_mt_messages_to_send(10, backend)

        assert len(messages) == 2
        assert {msg["id"] for msg in messages} == {msg.id for msg in new_messages}

    def test_filter_by_backend(self):
        """Return only messages associated with the provided backend."""
        backend_1 = BackendFactory()
        backend_2 = BackendFactory()
        backend_1_messages = MTMessageFactory.create_batch(3, backend=backend_1)
        MTMessageFactory.create_batch(3, backend=backend_2)

        messages = get_mt_messages_to_send(10, backend_1)

        assert len(messages) == 3
        assert {msg["id"] for msg in messages} == {msg.id for msg in backend_1_messages}

    def test_updates_status_to_sending(self):
        """Returned messages should be updated to status SENDING."""
        backend = BackendFactory()
        MTMessageFactory.create_batch(5, backend=backend)

        messages = get_mt_messages_to_send(3, backend)
        returned_message_ids = {msg["id"] for msg in messages}

        for message in MTMessage.objects.all():
            if message.id in returned_message_ids:
                assert message.status == MTMessage.Status.SENDING
            else:
                assert message.status == MTMessage.Status.NEW


# @pytest.mark.django_db
# class TestGetMessagesToProcess:
