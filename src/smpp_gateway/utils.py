import base64
import itertools
import logging
import signal
import string

from typing import Any, Dict

import smpplib

ASCII_PRINTABLE_BYTES = {ord(c) for c in string.printable}

logger = logging.getLogger(__name__)


def set_exit_signals(signals=[signal.SIGINT, signal.SIGTERM]):
    """
    Helper method for handling graceful exit signals such as SIGINT and SIGTERM.

    Use like so:

    exit_signal_received = set_exit_signals()
    while True:
        get_and_process_some_data()
        if exit_signal_received():
            logger.info("Received exit signal, leaving loop...")
            return
    """
    _received_exit_signal = False

    def set_received_exit_signal(sig_num, stack_frame):
        nonlocal _received_exit_signal
        logger.info(f"Got signal {sig_num}, setting exit_signal_received = True")
        _received_exit_signal = True

    for sig in signals:
        signal.signal(sig, set_received_exit_signal)

    return lambda: _received_exit_signal


def grouper(iterable, n):
    """
    Collect data into fixed-length chunks or blocks. Handy for grouping iterables of
    objects into batches suitable for bulk_create().
    """
    # In case iterable is not an iterator (but is, e.g., a list), islice()
    # will return the first group indefinitely, so ensure iterable is an
    # iterator first.
    iterable = iter(iterable)
    while True:
        group = list(itertools.islice(iterable, n))
        if not group:
            break
        yield group


def maybe_decode(value):
    if isinstance(value, bytes):
        if all(b in ASCII_PRINTABLE_BYTES for b in value):
            return value.decode("ascii")
        else:
            return base64.b64encode(value).decode("utf-8")
    return value


def decoded_params(pdu: smpplib.command.Command) -> Dict[str, Any]:
    return {key: maybe_decode(getattr(pdu, key)) for key in pdu.params.keys()}
