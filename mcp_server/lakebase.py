"""Lakebase connection helper matching the validated boot-camp pattern."""

import base64
import os
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor

_workspace = WorkspaceClient()
_scope = os.environ.get("LAKEBASE_SECRET_SCOPE", "database")
_key = os.environ.get("LAKEBASE_SECRET_KEY", "lakebase-url")


def _lakebase_url() -> str:
    secret = _workspace.secrets.get_secret(scope=_scope, key=_key)
    return base64.b64decode(secret.value).decode("utf-8")


@contextmanager
def get_connection():
    conn = psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def run_write_returning(sql: str, params: tuple | dict | None = None) -> dict:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        conn.commit()
        return row


def run_write(sql: str, params: tuple | dict | None = None) -> int:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        count = cursor.rowcount
        conn.commit()
        return count
