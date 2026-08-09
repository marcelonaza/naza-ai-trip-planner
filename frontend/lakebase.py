"""Read/write access used by the Flask frontend."""

import base64
import os
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor

_workspace = WorkspaceClient()


def _url() -> str:
    secret = _workspace.secrets.get_secret(
        scope=os.environ.get("LAKEBASE_SECRET_SCOPE", "database"),
        key=os.environ.get("LAKEBASE_SECRET_KEY", "lakebase-url"),
    )
    return base64.b64decode(secret.value).decode("utf-8")


@contextmanager
def connection():
    conn = psycopg2.connect(_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()
