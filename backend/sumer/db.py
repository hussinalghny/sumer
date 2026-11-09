"""اتصال PostgreSQL ومشغّل الترحيلات."""

import json
from importlib import resources

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(settings.database_url, min_size=1, max_size=20,
                               kwargs={"row_factory": dict_row, "autocommit": True}, open=True)
        import atexit
        atexit.register(close_pool)
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or settings.database_url, row_factory=dict_row, autocommit=True)


def fetchall(sql, params=None):
    with pool().connection() as c:
        return c.execute(sql, params).fetchall()


def fetchone(sql, params=None):
    with pool().connection() as c:
        return c.execute(sql, params).fetchone()


def execute(sql, params=None):
    with pool().connection() as c:
        c.execute(sql, params)


def get_setting(key, default=None):
    row = fetchone("SELECT value FROM system_settings WHERE key = %s", (key,))
    return row["value"] if row else default


def get_settings(prefix: str) -> dict:
    rows = fetchall("SELECT key, value FROM system_settings WHERE key LIKE %s", (prefix + "%",))
    return {r["key"]: r["value"] for r in rows}


def set_setting(key, value, admin_id=None):
    execute(
        "INSERT INTO system_settings (key, value, updated_by) VALUES (%s, %s::jsonb, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by",
        (key, json.dumps(value, ensure_ascii=False), admin_id),
    )


def migrate(url: str | None = None) -> list[str]:
    """يطبّق ملفات migrations/*.sql بالترتيب، كل ملف بمعاملة واحدة."""
    applied = []
    with psycopg.connect(url or settings.database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                     "name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        files = sorted(p for p in resources.files("sumer").joinpath("migrations").iterdir()
                       if p.name.endswith(".sql"))
        for f in files:
            if f.name in done:
                continue
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
            applied.append(f.name)
    return applied


def migration_status():
    rows = fetchall("SELECT name, applied_at FROM schema_migrations ORDER BY name")
    applied = {r["name"]: r["applied_at"] for r in rows}
    files = sorted(p.name for p in resources.files("sumer").joinpath("migrations").iterdir()
                   if p.name.endswith(".sql"))
    return [{"name": f, "applied_at": applied.get(f), "pending": f not in applied} for f in files]
