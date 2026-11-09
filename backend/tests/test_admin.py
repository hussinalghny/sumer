"""اختبارات لوحة التحكم: كل زر مرتبط بعملية حقيقية في الخلفية، والأرقام من البيانات الفعلية."""

import asyncio
import pyotp

from conftest import login
from sumer import crawler, db


def sup(admins):
    return login(None, "super_admin@sumer.test", admins["password"])


def test_overview_metrics_match_database(admins):
    c = sup(admins)
    r = c.get("/api/admin/overview")
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    assert m["indexed_pages"] == db.fetchone("SELECT count(*) AS n FROM indexed_documents WHERE duplicate_of IS NULL")["n"]
    assert m["indexed_images"] == db.fetchone("SELECT count(*) AS n FROM image_index WHERE status = 'ok'")["n"]
    assert m["indexed_documents"] == 1
    s = r.json()["system"]
    assert 0 <= s["cpu_percent"] <= 100 and s["ram_total_mb"] > 0


def test_crawler_state_controls_redis(admins):
    import redis
    from sumer.config import settings
    c = sup(admins)
    assert c.post("/api/admin/crawler/state", json={"state": "paused"}).json()["state"] == "paused"
    assert redis.Redis.from_url(settings.redis_url, decode_responses=True).get("crawler:state") == "paused"
    assert db.get_setting("crawler.state") == "paused"
    c.post("/api/admin/crawler/state", json={"state": "running"})


def test_seed_add_creates_jobs_and_remove(admins):
    c = sup(admins)
    r = c.post("/api/admin/crawler/seeds", json={"url": "https://example.gov.iq/"})
    assert r.status_code == 200
    assert db.fetchone("SELECT 1 FROM crawl_jobs WHERE url = 'https://example.gov.iq/' AND status = 'pending'")
    seeds = c.get("/api/admin/crawler/seeds").json()
    sid = next(s["id"] for s in seeds if s["url"] == "https://example.gov.iq/")
    assert c.delete(f"/api/admin/crawler/seeds/{sid}").status_code == 200
    dom = db.fetchone("SELECT id FROM domains WHERE host = 'example.gov.iq'")
    assert c.patch(f"/api/admin/domains/{dom['id']}", json={"status": "blocked", "block_reason": "test"}).status_code == 200
    assert not db.fetchone("SELECT 1 FROM crawl_jobs WHERE domain_id = %s AND status = 'pending'", (dom["id"],))
    assert c.post("/api/admin/crawler/seeds", json={"url": "javascript:alert(1)"}).status_code == 422


def test_domain_settings_validation(admins):
    c = sup(admins)
    dom = db.fetchone("SELECT id FROM domains WHERE host = '127.0.0.1'")
    assert c.patch(f"/api/admin/domains/{dom['id']}", json={"crawl_depth": 99}).status_code == 422
    assert c.patch(f"/api/admin/domains/{dom['id']}", json={"crawl_depth": 4, "excluded_paths": ["admin-area/"]}).status_code == 200
    assert db.fetchone("SELECT excluded_paths FROM domains WHERE id = %s", (dom["id"],))["excluded_paths"] == ["/admin-area/"]


def test_reindex_and_rebuild_run_for_real(admins):
    c = sup(admins)
    dom = db.fetchone("SELECT id FROM domains WHERE host = '127.0.0.1'")
    assert c.post("/api/admin/index/reindex-domain", json={"domain_id": dom["id"]}).status_code == 200
    assert c.post("/api/admin/index/rebuild").status_code == 200
    assert c.post("/api/admin/index/rebuild").status_code == 409     # منع التكرار
    db.execute("UPDATE domains SET min_delay_ms = 100")
    asyncio.run(crawler.Worker(concurrency=4, once=True).run())
    v = db.fetchall("SELECT status FROM index_versions ORDER BY id")
    assert [x["status"] for x in v] == ["retired", "active"]
    forced = db.fetchone("SELECT count(*) AS n FROM crawl_jobs WHERE payload->>'force' = 'true' AND status = 'done'")["n"]
    assert forced >= 10
    from sumer import search
    assert search.search("شلون اطلع جواز")["results"][0]["url"].endswith("/passport.html")


def test_search_settings_validated_and_applied(admins):
    c = sup(admins)
    assert c.put("/api/admin/search/settings", json={"values": {"search.ranking": {"text": 99}}}).status_code == 422
    assert c.put("/api/admin/search/settings", json={"values": {"evil.key": 1}}).status_code == 422
    r = c.put("/api/admin/search/settings", json={"values": {"search.per_domain_limit": 5}})
    assert r.status_code == 200 and db.get_setting("search.per_domain_limit") == 5
    c.put("/api/admin/search/settings", json={"values": {"search.enabled": False}})
    from fastapi.testclient import TestClient
    from sumer.app import app
    with TestClient(app, base_url="https://testserver") as pub:
        assert pub.post("/api/search", json={"q": "جواز"}).status_code == 503
    c.put("/api/admin/search/settings", json={"values": {"search.enabled": True}})


def test_search_test_explains(admins):
    r = sup(admins).post("/api/admin/search/test", json={"q": "jawaz"})
    assert r.status_code == 200 and "explain" in r.json()["results"][0]


def test_eval_set(admins, crawled):
    c = sup(admins)
    items = [{"query": "شلون اطلع جواز", "expected_url": crawled + "/passport.html"},
             {"query": "ta3yeenat", "expected_url": crawled + "/jobs.html"}]
    assert c.put("/api/admin/search/eval-set", json={"items": items}).status_code == 200
    r = c.post("/api/admin/search/evaluate").json()
    assert r["p_at_1"] == 1.0 and r["mrr"] == 1.0


def test_maintenance_mode_and_announcement(admins):
    c = sup(admins)
    c.put("/api/admin/settings/site", json={"values": {"site.maintenance": True, "site.announcement": {"enabled": True, "ar": "صيانة", "en": "x"}}})
    from fastapi.testclient import TestClient
    from sumer.app import app
    with TestClient(app, base_url="https://testserver") as pub:
        assert pub.post("/api/search", json={"q": "جواز"}).status_code == 503
        assert pub.get("/api/public/config").json()["announcement"]["ar"] == "صيانة"
    c.put("/api/admin/settings/site", json={"values": {"site.maintenance": False}})


def test_logo_upload_reencoded(admins):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 50, 200)).save(buf, "JPEG")
    c = sup(admins)
    assert c.post("/api/admin/settings/logo", files={"file": ("l.jpg", buf.getvalue(), "image/jpeg")}).status_code == 200
    assert c.post("/api/admin/settings/logo", files={"file": ("l.svg", b"<svg onload=alert(1)>", "image/svg+xml")}).status_code == 422


def test_backup_encrypted(admins):
    from sumer import backup
    c = sup(admins)
    r = c.post("/api/admin/backups")
    assert r.status_code == 200
    asyncio.run(crawler.Worker(concurrency=2, once=True).run())
    b = db.fetchone("SELECT * FROM backups WHERE id = %s", (r.json()["backup_id"],))
    assert b["status"] == "ok" and b["encrypted"], b["error"]
    path = backup.backup_dir() / b["file_name"]
    raw = path.read_bytes()
    assert raw.startswith(b"SUMERBK1") and b"PGDMP" not in raw[:200]
    assert backup.decrypt_backup(path).startswith(b"PGDMP")


def test_admin_management(admins):
    c = sup(admins)
    r = c.post("/api/admin/admins", json={"email": "new@sumer-admins.iq", "name": "جديد", "role": "auditor"})
    assert r.status_code == 200 and len(r.json()["temporary_password"]) >= 12
    new = login(None, "new@sumer-admins.iq", r.json()["temporary_password"])
    assert new.get("/api/admin/auth/me").json()["user"]["must_change_pw"]
    assert c.post(f"/api/admin/admins/{r.json()['id']}/revoke-sessions").json()["revoked"] >= 1
    assert new.get("/api/admin/overview").status_code == 401


def test_role_permissions_edit(admins):
    c = sup(admins)
    roles = {r["name"]: r for r in c.get("/api/admin/roles").json()}
    assert c.put(f"/api/admin/roles/{roles['super_admin']['id']}", json={"permissions": []}).status_code == 422
    assert c.put(f"/api/admin/roles/{roles['auditor']['id']}", json={"permissions": ["root.all"]}).status_code == 422


def test_infra_analytics_security_pages(admins):
    c = sup(admins)
    for path in ("/api/admin/infra", "/api/admin/analytics", "/api/admin/security/settings", "/api/admin/security/sessions",
                 "/api/admin/security/events", "/api/admin/audit", "/api/admin/ai/status", "/api/admin/images/stats",
                 "/api/admin/index/versions", "/api/admin/index/duplicates", "/api/admin/index/documents",
                 "/api/admin/crawler/logs", "/api/admin/crawler/jobs", "/api/admin/domains", "/api/admin/search/quality",
                 "/api/admin/index/storage", "/api/admin/images", "/api/admin/index/errors", "/api/admin/languages"):
        r = c.get(path)
        assert r.status_code == 200, (path, r.text[:300])
    infra = c.get("/api/admin/infra").json()
    assert infra["database"]["ok"] and infra["redis"]["ok"] and infra["index"]["ok"]
    assert all(not m["pending"] for m in infra["migrations"])
    ai = c.get("/api/admin/ai/status").json()
    assert {s["key"] for s in ai["services"]} >= {"speech", "translation", "language_detection"}


def test_audit_trail_records_actions(admins):
    actions = {r["action"] for r in db.fetchall("SELECT DISTINCT action FROM audit_logs")}
    assert {"login", "crawler_state", "seed_added", "index_rebuild", "search_settings_updated"} <= actions
