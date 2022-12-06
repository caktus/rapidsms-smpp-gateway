from multiprocessing.pool import ThreadPool

import pytest

from smpp_gateway.models import MOMessage, MTMessage
from smpp_gateway.queries import (
    get_mo_messages_to_process,
    get_mt_messages_to_send,
    pg_listen,
    pg_notify,
)
from tests.factories import BackendFactory, MOMessageFactory, MTMessageFactory


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


@pytest.mark.django_db
class TestGetMessagesToProcess(object):
    def test_empty(self):
        """Return an empty list if there are no queued inbound messages."""
        messages = get_mo_messages_to_process(limit=1)
        assert messages.count() == 0

    def test_partial_page(self):
        """Return fewer than `limit` messages if appropriate."""
        MOMessageFactory.create_batch(5)

        messages = get_mo_messages_to_process(limit=100)

        assert messages.count() == 5

    def test_full_page(self):
        """Return only `limit` messages if more are present."""
        MOMessageFactory.create_batch(5)

        messages = get_mo_messages_to_process(limit=3)

        assert messages.count() == 3

    def test_new_messages_only(self):
        """Return only messages with status NEW."""
        backend = BackendFactory()
        new_messages = [MOMessageFactory(backend=backend, status=MOMessage.Status.NEW)]
        for other_status in [
            val for val in MOMessage.Status.values if val != MOMessage.Status.NEW
        ]:
            MOMessageFactory.create_batch(
                3,
                backend=backend,
                status=other_status,
            )
        new_messages.append(
            MOMessageFactory(backend=backend, status=MOMessage.Status.NEW)
        )

        messages = get_mo_messages_to_process(limit=10)

        assert len(messages) == 2
        assert set(messages) == set(new_messages)

    def test_updates_status_to_processing(self):
        """Returned messages should be updated to status PROCESSING."""
        backend = BackendFactory()
        MOMessageFactory.create_batch(5, backend=backend)

        messages = get_mo_messages_to_process(limit=3)
        returned_message_pks = {msg.pk for msg in messages}

        for message in MOMessage.objects.all():
            if message.pk in returned_message_pks:
                assert message.status == MOMessage.Status.PROCESSING
            else:
                assert message.status == MOMessage.Status.NEW


@pytest.mark.django_db(transaction=True)
class TestConcurrency(object):
    def test_get_mo_messages_concurrently(self):
        """
        Multiple concurrent calls to get_mo_messages_to_process()
        fetch a given message only once.
        """
        message_count = 50
        backend = BackendFactory()
        new_messages = MOMessageFactory.create_batch(
            message_count,
            backend=backend,
            status=MOMessage.Status.NEW,
        )

        def get_one_message(_):
            return get_mo_messages_to_process(limit=1)[0]

        pool = ThreadPool(processes=10)
        messages = pool.map(get_one_message, range(message_count))

        assert len(messages) == message_count
        assert set(messages) == set(new_messages)

    def test_get_mt_messages_concurrently(self):
        """
        Multiple concurrent calls to get_mt_messages_to_send()
        fetch a given message only once.
        """
        message_count = 50
        backend = BackendFactory()
        new_messages = MTMessageFactory.create_batch(
            message_count,
            backend=backend,
            status=MTMessage.Status.NEW,
        )

        def get_one_message(_):
            return get_mt_messages_to_send(limit=1, backend=backend)[0]

        pool = ThreadPool(processes=10)
        messages = pool.map(get_one_message, range(message_count))

        assert len(messages) == message_count
        assert {msg["id"] for msg in messages} == {msg.id for msg in new_messages}


@pytest.mark.django_db(transaction=True)
class TestNotifications(object):
    def test_listen_notify_new_messages(self):
        """`pg_notify` should publish messages that can be read by the
        connection made from `pg_listen`.
        """
        listen_conn = pg_listen("test_channel")

        listen_conn.poll()
        assert len(listen_conn.notifies) == 0

        for _ in range(5):
            pg_notify("test_channel")

        listen_conn.poll()
        assert len(listen_conn.notifies) == 5

    def test_listen_notify_preexisting_messages(self):
        """The connection made from `pg_listen` cannot recieve messages sent
        before it was created.
        """
        for _ in range(4):
            pg_notify("test_channel")

        listen_conn = pg_listen("test_channel")
        listen_conn.poll()
        assert len(listen_conn.notifies) == 0
