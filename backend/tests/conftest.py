"""تجهيز الاختبارات: قاعدة بيانات نظيفة، موقع تجريبي محلي، زحف حقيقي، وعميل API."""

import asyncio
import os
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ADMIN_URL = os.getenv("SUMER_TEST_ADMIN_DB", "postgresql://postgres@127.0.0.1:5432/postgres")
TEST_DB = "sumer_pytest"
os.environ["SUMER_DATABASE_URL"] = f"postgresql://sumer:sumer_dev@127.0.0.1:5432/{TEST_DB}"
os.environ["SUMER_REDIS_URL"] = "redis://127.0.0.1:6379/15"
os.environ["SUMER_ALLOW_PRIVATE_NETWORKS"] = "1"   # الموقع التجريبي على 127.0.0.1
os.environ["SUMER_COOKIE_SECURE"] = "0"
os.environ["SUMER_APP_SECRET"] = "test-secret-" + "x" * 32
os.environ["SUMER_BACKUP_KEY"] = "test-backup-key"
os.environ.setdefault("SUMER_DATA_DIR", "/tmp/sumer-pytest-data")


SITE_ROOT: list = []


def _reset_db():
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        c.execute(f"CREATE DATABASE {TEST_DB} OWNER sumer")
    with psycopg.connect(ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}", autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    from make_site import build
    from site_server import serve
    root = tmp_path_factory.mktemp("site")
    build(root)
    srv = serve(root)
    SITE_ROOT.append(root)
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="session")
def crawled(site):
    """قاعدة بيانات مزحوفة فعلياً من الموقع التجريبي."""
    import redis
    redis.Redis.from_url(os.environ["SUMER_REDIS_URL"]).flushdb()
    _reset_db()
    from sumer import crawler, db
    db.close_pool()
    db.migrate()
    with db.pool().connection() as c:
        crawler.add_seed(c, site + "/index.html")
        c.execute("UPDATE domains SET min_delay_ms = 100, excluded_paths = '{/admin-area/}'")
    asyncio.run(crawler.Worker(concurrency=4, once=True).run())
    crawler.compute_authority()
    crawler.refresh_terms()
    return site


@pytest.fixture(scope="session")
def client(crawled):
    from fastapi.testclient import TestClient
    from sumer.app import app
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture(scope="session")
def admins(crawled):
    from sumer import auth, db
    db.set_setting("ratelimit.admin_login_per_15m", 100000)
    pw = "Str0ng-Passw0rd!"
    ids = {}
    for role in ("super_admin", "crawler_manager", "auditor", "search_manager", "security_admin"):
        ids[role] = auth.create_admin(f"{role}@sumer.test", role, pw, role)
    return {"password": pw, "ids": ids}


def login(client, email, password):
    from fastapi.testclient import TestClient
    from sumer.app import app
    c = TestClient(app, base_url="https://testserver")
    c.__enter__()
    r = c.post("/api/admin/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    c.headers["x-csrf-token"] = r.json()["csrf"]
    return c
