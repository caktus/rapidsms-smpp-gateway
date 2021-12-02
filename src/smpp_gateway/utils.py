import itertools


def grouper(iterable, n):
    """
    Collect data into fixed-length chunks or blocks. Handy for grouping lists of
    objects into batches suitable for bulk_create(), as an alternative to
    BatchOperations(), below.
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
