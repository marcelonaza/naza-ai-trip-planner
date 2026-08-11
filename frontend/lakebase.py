"""OAuth-authenticated Lakebase access for the Databricks App."""

import os
from contextlib import contextmanager

import psycopg
from databricks.sdk import WorkspaceClient
from psycopg.rows import dict_row

LAKEBASE_ENDPOINT = os.environ.get(
    "LAKEBASE_ENDPOINT",
    "projects/naza-ai-trip-planner/branches/production/endpoints/primary",
)
LAKEBASE_HOST = os.environ.get(
    "LAKEBASE_HOST",
    "ep-winter-moon-d839l59e.database.us-east-2.cloud.databricks.com",
)
LAKEBASE_DATABASE = os.environ.get("LAKEBASE_DATABASE", "databricks_postgres")

_workspace = WorkspaceClient()


@contextmanager
def connection():
    current_user = _workspace.current_user.me()
    credential = _workspace.postgres.generate_database_credential(
        endpoint=LAKEBASE_ENDPOINT
    )
    if not credential.token:
        raise RuntimeError("Lakebase OAuth credential could not be generated.")

    with psycopg.connect(
        host=LAKEBASE_HOST,
        port=5432,
        dbname=LAKEBASE_DATABASE,
        user=current_user.user_name,
        password=credential.token,
        sslmode="require",
        row_factory=dict_row,
    ) as conn:
        yield conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()
