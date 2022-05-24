import base64
import itertools
import string

from typing import Any, Dict

import smpplib

ASCII_PRINTABLE_BYTES = {ord(c) for c in string.printable}


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
