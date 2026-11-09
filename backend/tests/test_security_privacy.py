"""اختبارات الخصوصية والأمن: SSRF، عدم تخزين الاستعلامات، CSRF، الصلاحيات، 2FA، التدقيق."""

import asyncio
import io
import logging

import pyotp
import pytest
from PIL import Image

from conftest import login
from sumer import db, netguard
from sumer.config import settings


# ---------------- SSRF ----------------
@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.1", "169.254.169.254",
                                "100.64.1.1", "::1", "fd00::1", "::ffff:127.0.0.1", "0.0.0.0", "224.0.0.1"])
def test_private_ips_blocked(ip):
    assert not netguard.is_public_ip(ip)


def test_public_ip_allowed():
    assert netguard.is_public_ip("8.8.8.8")


def test_resolver_blocks_internal(monkeypatch):
    object.__setattr__(settings, "allow_private_networks", False)
    try:
        for url in ("http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "http://localhost/",
                    "http://[::1]/", "file:///etc/passwd", "gopher://x/", "http://user:pw@example.com/",
                    "http://example.com:6379/"):
            with pytest.raises(netguard.BlockedDestination):
                asyncio.run(netguard.resolve(url))
    finally:
        object.__setattr__(settings, "allow_private_networks", True)


# ---------------- الخصوصية ----------------
def test_no_query_table_exists(crawled):
    tables = {r["table_name"] for r in db.fetchall("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    assert not any("quer" in t for t in tables)


def test_search_query_not_persisted(client):
    marker = "كلمةسريةفريدة123"
    r = client.post("/api/search", json={"q": marker})
    assert r.status_code == 200
    asyncio.run(_flush())
    for table in db.fetchall("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"):
        t = table["table_name"]
        cols = db.fetchall("SELECT column_name FROM information_schema.columns WHERE table_name = %s AND data_type IN "
                           "('text', 'jsonb', 'ARRAY')", (t,))
        for c in cols:
            hit = db.fetchone(f'SELECT 1 FROM "{t}" WHERE "{c["column_name"]}"::text LIKE %s LIMIT 1', ("%" + marker + "%",))
            assert hit is None, f"نص البحث وُجد في {t}.{c['column_name']}"


async def _flush():
    import redis.asyncio as aioredis
    from sumer import privacy
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await privacy.flush_metrics(r)
    keys = [k async for k in r.scan_iter("*")]
    for k in keys:
        assert "كلمةسريةفريدة" not in k
        if (await r.type(k)) == "hash":
            vals = await r.hgetall(k)
            assert not any("كلمةسريةفريدة" in f + v for f, v in vals.items())
    await r.aclose()


def test_aggregated_metrics_recorded(client):
    client.post("/api/search", json={"q": "جواز"})
    asyncio.run(_flush())
    row = db.fetchone("SELECT sum(value) AS n FROM ops_metrics_hourly WHERE metric = 'searches'")
    assert row["n"] and row["n"] >= 1


def test_ip_not_stored_in_rate_limiter(client):
    import redis
    client.post("/api/search", json={"q": "طقس"})
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    keys = [k for k in r.scan_iter("rl:*")]
    assert keys and not any("127.0.0.1" in k or "testclient" in k for k in keys)


def test_privacy_headers_and_no_cookies(client):
    r = client.post("/api/search", json={"q": "جواز"})
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert "set-cookie" not in r.headers


def test_validation_error_does_not_echo_query(client):
    r = client.post("/api/search", json={"q": "x" * 1000})
    assert r.status_code == 422 and "xxxx" not in r.text


def test_reverse_image_upload_not_written(client, tmp_path):
    from sumer.config import settings as s
    before = set(p for p in s.data_dir.rglob("*") if p.is_file())
    img = db.fetchone("SELECT thumb_path FROM image_index WHERE image_url LIKE '%masgouf%'")
    buf = io.BytesIO()
    Image.open(s.data_dir / "thumbs" / img["thumb_path"]).convert("RGB").resize((400, 260)).save(buf, "PNG")
    r = client.post("/api/images/reverse", files={"file": ("q.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["results"] and "masgouf" in r.json()["results"][0]["image_url"]
    after = set(p for p in s.data_dir.rglob("*") if p.is_file())
    assert after == before


def test_invalid_upload_rejected(client):
    r = client.post("/api/images/reverse", files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422


def test_voice_and_translation_report_unavailable_honestly(client):
    r = client.post("/api/translate", json={"text": "مرحبا", "target": "en"})
    assert r.status_code in (200, 503)
    if r.status_code == 503:
        assert "غير مثبت" in r.json()["detail"]
    cfg = client.get("/api/public/config").json()
    assert cfg["features"]["translation"] == (r.status_code == 200)


# ---------------- المصادقة والصلاحيات ----------------
def test_admin_requires_auth(client):
    assert client.get("/api/admin/overview").status_code == 401


def test_wrong_password_and_lockout(client, admins):
    from fastapi.testclient import TestClient
    from sumer.app import app
    c = TestClient(app, base_url="https://testserver")
    for _ in range(5):
        assert c.post("/api/admin/auth/login", json={"email": "auditor@sumer.test", "password": "wrong"}).status_code == 401
    r = c.post("/api/admin/auth/login", json={"email": "auditor@sumer.test", "password": admins["password"]})
    assert r.status_code == 401   # الحساب مقفل مؤقتاً
    db.execute("UPDATE admin_users SET locked_until = NULL, failed_logins = 0 WHERE email = 'auditor@sumer.test'")
    assert db.fetchone("SELECT count(*) AS n FROM audit_logs WHERE action = 'login_failed'")["n"] >= 5


def test_csrf_required(admins):
    c = login(None, "super_admin@sumer.test", admins["password"])
    token = c.headers.pop("x-csrf-token")
    assert c.post("/api/admin/crawler/state", json={"state": "paused"}).status_code == 403
    c.headers["x-csrf-token"] = token
    assert c.post("/api/admin/crawler/state", json={"state": "running"}).status_code == 200


def test_least_privilege_enforced_on_backend(admins):
    aud = login(None, "auditor@sumer.test", admins["password"])
    assert aud.get("/api/admin/overview").status_code == 200
    assert aud.get("/api/admin/audit").status_code == 200
    assert aud.post("/api/admin/crawler/state", json={"state": "stopped"}).status_code == 403
    assert aud.post("/api/admin/index/rebuild").status_code == 403
    assert aud.post("/api/admin/admins", json={"email": "x@y.iq", "name": "xx", "role": "auditor"}).status_code == 403
    cm = login(None, "crawler_manager@sumer.test", admins["password"])
    assert cm.post("/api/admin/crawler/state", json={"state": "running"}).status_code == 200
    assert cm.get("/api/admin/security/settings").status_code == 403
    assert cm.get("/api/admin/admins").status_code == 403
    denied = db.fetchone("SELECT count(*) AS n FROM audit_logs WHERE action = 'permission_denied'")["n"]
    assert denied >= 4


def test_non_super_cannot_create_super(admins):
    sec = login(None, "security_admin@sumer.test", admins["password"])
    assert sec.post("/api/admin/admins", json={"email": "z@y.iq", "name": "zz", "role": "super_admin"}).status_code == 403


def test_two_factor_flow(admins):
    c = login(None, "search_manager@sumer.test", admins["password"])
    setup = c.post("/api/admin/auth/2fa/setup").json()
    code = pyotp.TOTP(setup["secret"]).now()
    assert c.post("/api/admin/auth/2fa/enable", json={"code": code}).status_code == 200
    stored = db.fetchone("SELECT totp_secret_enc FROM admin_users WHERE email = 'search_manager@sumer.test'")["totp_secret_enc"]
    assert setup["secret"] not in stored          # السر مخزن مشفراً
    from fastapi.testclient import TestClient
    from sumer.app import app
    c2 = TestClient(app, base_url="https://testserver")
    r = c2.post("/api/admin/auth/login", json={"email": "search_manager@sumer.test", "password": admins["password"]})
    assert r.json()["mfa_required"]
    c2.headers["x-csrf-token"] = r.json()["csrf"]
    assert c2.get("/api/admin/search/settings").status_code == 401         # قبل الرمز
    assert c2.post("/api/admin/auth/mfa", json={"code": "000000"}).status_code == 401
    assert c2.post("/api/admin/auth/mfa", json={"code": pyotp.TOTP(setup["secret"]).now()}).status_code == 200
    assert c2.get("/api/admin/search/settings").status_code == 200


def test_suspend_revokes_sessions(admins):
    sup = login(None, "super_admin@sumer.test", admins["password"])
    victim = login(None, "crawler_manager@sumer.test", admins["password"])
    assert victim.get("/api/admin/crawler/status").status_code == 200
    uid = admins["ids"]["crawler_manager"]
    assert sup.patch(f"/api/admin/admins/{uid}", json={"status": "suspended"}).status_code == 200
    assert victim.get("/api/admin/crawler/status").status_code == 401
    sup.patch(f"/api/admin/admins/{uid}", json={"status": "active"})


def test_password_policy():
    from sumer import auth
    with pytest.raises(ValueError):
        auth.hash_password("short")
    with pytest.raises(ValueError):
        auth.hash_password("alllowercaseletters")


def test_login_rate_limit(admins):
    import redis
    from fastapi.testclient import TestClient
    from sumer.app import app
    from sumer.config import settings as st
    r = redis.Redis.from_url(st.redis_url)
    for k in r.scan_iter("rl:admin_login:*"):
        r.delete(k)
    db.set_setting("ratelimit.admin_login_per_15m", 3)
    try:
        c = TestClient(app, base_url="https://testserver")
        codes = [c.post("/api/admin/auth/login", json={"email": "nobody@x.iq", "password": "x"}).status_code for _ in range(5)]
        assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    finally:
        db.set_setting("ratelimit.admin_login_per_15m", 100000)
        for k in r.scan_iter("rl:admin_login:*"):
            r.delete(k)
