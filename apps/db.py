import mysql.connector
from flask import current_app

class DBCursor:
    """Wrapper around a mysql.connector cursor that supports the context manager protocol
    and forwards attribute access (execute, fetchall, fetchone, etc.)."""
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        # Return the wrapper so attribute forwarding works consistently
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def close(self):
        return self._cursor.close()


class DBConnection:
    """Wrapper around a mysql.connector connection that:
    - supports the context manager protocol (so `with get_db_connection() as conn:` works)
    - returns DBCursor objects from .cursor(...) so `with conn.cursor(...) as c:` works
    - forwards other attribute access to the underlying connection
    """
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        # Return a DBCursor wrapper which itself is a context manager
        return DBCursor(self._conn.cursor(*args, **kwargs))

    def __enter__(self):
        # Return the wrapper so callers using "with get_db_connection() as connection:" get this object
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                # attempt rollback on exception
                try:
                    self._conn.rollback()
                except Exception:
                    pass
        finally:
            try:
                self._conn.close()
            except Exception:
                pass

    def __getattr__(self, name):
        # Forward other attribute access (commit, close, is_connected, etc.)
        return getattr(self._conn, name)

    def close(self):
        return self._conn.close()


def get_db_connection():
    """Get a connection to the MySQL database wrapped in DBConnection."""
    connection = mysql.connector.connect(
        host=current_app.config['MYSQL_HOST'],
        user=current_app.config['MYSQL_USER'],
        password=current_app.config['MYSQL_PASSWORD'],
        database=current_app.config['MYSQL_DATABASE']
    )
    return DBConnection(connection)