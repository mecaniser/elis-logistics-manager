"""Payload-free cross-process wakeups; the inbox remains the durable authority."""
import asyncio
import logging
import select
from sqlalchemy import text

CHANNEL = 'db094_financial_inbox'


def notify(db):
    # PostgreSQL delivers NOTIFY only on commit, never for a rolled-back job.
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text("SELECT pg_notify('db094_financial_inbox', '')"))


def _connect(engine):
    # Dedicated socket, not a pooled transaction or held tenant lock.
    args, kwargs = engine.dialect.create_connect_args(engine.url)
    kwargs.setdefault("connect_timeout", 10)
    connection = engine.dialect.dbapi.connect(*args, **kwargs)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute('LISTEN ' + CHANNEL)
        return connection
    except BaseException:
        connection.close()
        raise


def _receive(connection):
    # OS socket wait: zero SQL while idle. Short timeout bounds shutdown latency.
    ready, _, _ = select.select([connection], [], [], 1)
    if not ready:
        return False
    connection.poll()
    received = bool(connection.notifies)
    connection.notifies.clear()
    return received


async def listen(engine, stop, wake):
    if engine.dialect.name != 'postgresql':
        return  # Local SQLite uses the post-commit in-process wakeup.
    while not stop.is_set():
        connection = None
        try:
            connection = await asyncio.to_thread(_connect, engine)
            # LISTEN first, then drain: closes startup/reconnection notification gap.
            wake.set()
            while not stop.is_set():
                if await asyncio.to_thread(_receive, connection):
                    wake.set()
        except Exception:
            logging.getLogger(__name__).warning('DBN wake listener unavailable; reconnect scheduled.')
        finally:
            if connection is not None:
                await asyncio.to_thread(connection.close)
        if not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
