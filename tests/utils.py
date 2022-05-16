import psycopg2.extensions


def drain_conn(conn: psycopg2.extensions.connection):
    """Drain all notifications from conn so there is no cross-talk between
    tests.
    """
    while conn.notifies:
        conn.notifies.pop()
