import collections
import select
import socket

import smpplib


class PgSequenceGenerator(smpplib.client.SimpleSequenceGenerator):
    """
    smpplib sequence generator that uses a Postgres sequence to persist
    sequence numbers across restarts and client instances. See:
    https://www.postgresql.org/docs/10/sql-createsequence.html
    """

    def __init__(self, conn, backend_name):
        self.conn = conn
        self.sequence_name = f"smpp_gateway_sequence_{backend_name}"
        with conn.cursor() as curs:
            curs.execute(
                f"""
                CREATE SEQUENCE IF NOT EXISTS {self.sequence_name}
                    MINVALUE {self.MIN_SEQUENCE}
                    MAXVALUE {self.MAX_SEQUENCE}
                    CYCLE
                """
            )

    def _fetchone(self, query):
        with self.conn.cursor() as curs:
            curs.execute(query)
            return curs.fetchone()[0]

    @property
    def sequence(self):
        "Current (last) value of the sequence."
        return self._fetchone(f"SELECT last_value from {self.sequence_name}")

    def next_sequence(self):
        "Increments and returns the next value of the sequence."
        return self._fetchone(f"SELECT nextval('{self.sequence_name}')")


class ThreadSafeClient(smpplib.client.Client):
    """
    Thread-safe smpplib Client, adapted from:
    https://stackoverflow.com/a/51105047/166053
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Any data received by this queue will be sent
        self._send_queue = collections.deque()
        # Any data sent to ssock shows up on rsock
        self._rsock, self._ssock = socket.socketpair()

    def send_pdu(self, pdu, send_later=False):
        if send_later:
            # Put the data to send inside the queue
            self._send_queue.append(pdu)
            # Trigger the main thread by sending data to ssock which goes to rsock
            self._ssock.send(b"\x00")
        else:
            return super().send_pdu(pdu)

    def send_message(self, **kwargs):
        """Send message

        Required Arguments:
            source_addr_ton -- Source address TON
            source_addr -- Source address (string)
            dest_addr_ton -- Destination address TON
            destination_addr -- Destination address (string)
            short_message -- Message text (string)
        """

        ssm = smpplib.smpp.make_pdu("submit_sm", client=self, **kwargs)
        self.send_pdu(ssm, send_later=True)
        return ssm

    def listen(self, ignore_error_codes=None, auto_send_enquire_link=True):
        while True:
            # When either main socket has data or rsock has data, select.select will return
            rlist, _, _ = select.select(
                [self._socket, self._rsock], [], [], self.timeout
            )
            if not rlist and auto_send_enquire_link:
                self.logger.debug("Socket timeout, listening again")
                pdu = smpplib.smpp.make_pdu("enquire_link", client=self)
                self.send_pdu(pdu)
                continue
            elif not rlist:
                # backwards-compatible with existing behavior
                raise socket.timeout()
            for ready_socket in rlist:
                if ready_socket is self._socket:
                    self.read_once(ignore_error_codes, auto_send_enquire_link)
                else:
                    # Ready_socket is rsock
                    self._rsock.recv(1)  # Dump the ready mark
                    # Send the data.
                    super().send_pdu(self._send_queue.pop())
