"""اختبارات الاكتشاف التلقائي: اتباع الروابط بين المواقع، ترتيب الأهمية، الميزانية، العدالة بين المواقع، والفخاخ."""

import asyncio

import pytest

from conftest import SITE_ROOT, login
from site_server import serve
from sumer import crawler, db
from sumer.crawler import is_trap, link_priority


def test_trap_detection():
    assert is_trap("https://x.iq/" + "a" * 600)
    assert is_trap("https://x.iq/p?a=1&b=2&c=3&d=4&e=5&f=6")
    assert is_trap("https://x.iq/cal/2026/1/1/next/2026/1/2/")
    assert is_trap("https://x.iq/a/b/a/b/a/c")
    assert not is_trap("https://x.iq/news/2026/11/06/story.html?id=5")


def test_importance_priority():
    src_strong = {"authority": 0.9}
    src_weak = {"authority": 0.0}
    iraqi = {"authority": 0.0, "is_iraqi": True}
    foreign = {"authority": 0.0, "is_iraqi": False}
    assert link_priority(src_strong, foreign, 1, True) < link_priority(src_weak, foreign, 1, True)
    assert link_priority(src_weak, iraqi, 0, False) < link_priority(src_weak, foreign, 0, False)
    assert link_priority(src_weak, foreign, 1, True) < link_priority(src_weak, foreign, 3, True)


@pytest.fixture(scope="module")
def site_b(tmp_path_factory, crawled):
    """موقع ثانٍ على مضيف مختلف (localhost) فيه 5 صفحات مترابطة."""
    root = tmp_path_factory.mktemp("siteb")
    for i in range(1, 6):
        nav = " ".join(f'<a href="/b{j}.html">b{j}</a>' for j in range(1, 6))
        (root / f"b{i}.html").write_text(
            f"<html lang='en'><head><title>Palm dates of Basra {i}</title></head><body>{nav}"
            f"<p>Basra palm groves produce famous dates, page number {i}, with irrigation and harvest notes.</p></body></html>")
    (root / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    srv = serve(root)
    base = f"http://localhost:{srv.server_port}"
    (SITE_ROOT[0] / "outbound.html").write_text(
        f"<html><head><title>روابط خارجية</title></head><body><p>صفحة فيها رابط لموقع آخر عن تمور البصرة.</p>"
        f"<a href='{base}/b1.html'>تمور البصرة</a></body></html>", encoding="utf-8")
    yield base
    srv.shutdown()


def crawl_outbound(site):
    db.execute("UPDATE domains SET min_delay_ms = 100")
    with db.pool().connection() as c:
        crawler.enqueue(c, "crawl", site + "/outbound.html", domain_id=db.fetchone(
            "SELECT id FROM domains WHERE host = '127.0.0.1'")["id"], priority=1, payload={"force": True})
    asyncio.run(crawler.Worker(concurrency=4, once=True).run())


def test_iraq_mode_does_not_follow_foreign_sites(crawled, site_b):
    db.set_setting("crawler.discovery_mode", "iraq")
    crawl_outbound(crawled)
    dom = db.fetchone("SELECT * FROM domains WHERE host = 'localhost'")
    src = db.fetchone("SELECT id FROM domains WHERE host = '127.0.0.1'")
    assert dom and dom["discovered_from"] == src["id"]              # اكتُشف وسُجّل مصدره
    assert dom["max_pages"] == db.get_setting("crawler.new_domain_budget")
    assert not db.fetchone("SELECT 1 FROM crawled_pages WHERE domain_id = %s", (dom["id"],))   # لكن لم يُزحف


def test_open_mode_discovers_and_respects_budget(crawled, site_b, admins):
    c = login(None, "super_admin@sumer.test", admins["password"])
    r = c.put("/api/admin/crawler/config", json={"discovery_mode": "open", "new_domain_budget": 3})
    assert r.status_code == 200
    assert c.put("/api/admin/crawler/config", json={"discovery_mode": "everything"}).status_code == 422
    db.execute("UPDATE domains SET max_pages = 3, min_delay_ms = 100 WHERE host = 'localhost'")
    db.execute("DELETE FROM crawled_pages WHERE url LIKE '%outbound.html'")
    crawl_outbound(crawled)
    dom = db.fetchone("SELECT * FROM domains WHERE host = 'localhost'")
    ok = db.fetchone("SELECT count(*) AS n FROM crawled_pages WHERE domain_id = %s AND status = 'ok'", (dom["id"],))["n"]
    assert 1 <= ok <= 3                       # زُحف الموقع الجديد تلقائياً، ضمن ميزانيته
    from sumer import search
    assert search.search("Basra palm dates")["results"][0]["host"] == "localhost"
    st = c.get("/api/admin/crawler/status").json()
    assert st["discovery_mode"] == "open" and st["discovery"]["domains_total"] >= 2
    db.set_setting("crawler.discovery_mode", "iraq")


def test_budget_grows_with_authority_unless_manual(crawled, site_b, admins):
    db.execute("UPDATE domains SET authority = 0 WHERE host = 'localhost'")
    crawler.compute_authority()
    dom = db.fetchone("SELECT max_pages, authority, budget_auto FROM domains WHERE host = 'localhost'")
    assert dom["budget_auto"] and dom["max_pages"] >= db.get_setting("crawler.new_domain_budget")
    c = login(None, "super_admin@sumer.test", admins["password"])
    did = db.fetchone("SELECT id FROM domains WHERE host = 'localhost'")["id"]
    c.patch(f"/api/admin/domains/{did}", json={"max_pages": 7})
    crawler.compute_authority()
    d2 = db.fetchone("SELECT max_pages, budget_auto FROM domains WHERE id = %s", (did,))
    assert d2["max_pages"] == 7 and not d2["budget_auto"]


def test_fair_claim_across_sites(crawled, site_b):
    db.execute("UPDATE crawl_jobs SET status = 'cancelled' WHERE status = 'pending'")
    a = db.fetchone("SELECT id FROM domains WHERE host = '127.0.0.1'")["id"]
    b = db.fetchone("SELECT id FROM domains WHERE host = 'localhost'")["id"]
    with db.pool().connection() as c:
        for i in range(10):
            crawler.enqueue(c, "crawl", f"http://127.0.0.1/fair-{i}", domain_id=a, priority=10)
        crawler.enqueue(c, "crawl", "http://localhost/fair-b", domain_id=b, priority=50)
    w = crawler.Worker(concurrency=1, once=True)
    jobs = w.claim(4, "running")
    by = [j["domain_id"] for j in jobs]
    assert by.count(a) <= 2 and b in by       # موقع واحد لا يحتكر الدفعة
    db.execute("UPDATE crawl_jobs SET status = 'cancelled' WHERE url LIKE '%fair-%'")


def test_pending_cap_per_domain(crawled, site_b):
    db.set_setting("crawler.max_pending_per_domain", 10)
    db.set_setting("crawler.discovery_mode", "open")
    try:
        src = db.fetchone("SELECT * FROM domains WHERE host = '127.0.0.1'")
        tgt = db.fetchone("SELECT * FROM domains WHERE host = 'localhost'")
        db.execute("UPDATE domains SET max_pages = 100000, page_count = 0 WHERE id = %s", (tgt["id"],))
        page = db.fetchone("SELECT id FROM crawled_pages WHERE domain_id = %s LIMIT 1", (src["id"],))["id"]
        links = [(f"http://localhost/cap-{i}.html", "") for i in range(40)]
        w = crawler.Worker(concurrency=1, once=True)
        with db.pool().connection() as c:
            w.links(c, page, dict(src), links, 0)
        n = db.fetchone("SELECT count(*) AS n FROM crawl_jobs WHERE domain_id = %s AND status = 'pending' AND url LIKE '%%cap-%%'",
                        (tgt["id"],))["n"]
        assert n <= 10
    finally:
        db.execute("UPDATE crawl_jobs SET status = 'cancelled' WHERE url LIKE '%cap-%'")
        db.set_setting("crawler.max_pending_per_domain", 500)
        db.set_setting("crawler.discovery_mode", "iraq")
