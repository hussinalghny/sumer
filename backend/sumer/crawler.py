"""عامل الزحف والمهام.

- قائمة المهام في PostgreSQL (crawl_jobs) مع FOR UPDATE SKIP LOCKED: آمنة لعدة عمّال على عدة خوادم.
- Redis للتحكم (تشغيل/إيقاف/إيقاف مؤقت)، والتهذيب لكل نطاق، ونبضات العمّال.
- كل طلب شبكة يمر عبر netguard (حماية SSRF وإعادة ربط DNS).
"""

import asyncio
import hashlib
import re
import json
import os
import socket
import time
import traceback
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
import redis.asyncio as aioredis

from . import db
from . import text as T
from .config import settings
from .indexer import index_document, is_iraqi_host, reanalyze, url_hash
from .netguard import BlockedDestination, safe_fetch
from .parse import IMAGE_EXT, normalize_url, parse_html, parse_pdf, parse_sitemap

UA_TOKEN = "SumerBot"
CRAWL_KINDS = ("crawl", "sitemap", "image")


def ua() -> str:
    return db.get_setting("crawler.user_agent", f"{UA_TOKEN}/1.0")


# ======================= أدوات قاعدة البيانات =======================
def get_or_create_domain(conn, host: str, discovered_from: int | None = None) -> dict:
    row = conn.execute("SELECT * FROM domains WHERE host = %s", (host,)).fetchone()
    if row:
        return row
    depth = db.get_setting("crawler.default_depth", 3)
    iraqi = is_iraqi_host(host)
    budget = int(db.get_setting("crawler.iraqi_domain_budget" if iraqi else "crawler.new_domain_budget",
                                10000 if iraqi else 200))
    return conn.execute(
        "INSERT INTO domains (host, is_iraqi, crawl_depth, max_pages, discovered_from) VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (host) DO UPDATE SET host = EXCLUDED.host RETURNING *",
        (host, iraqi, depth, budget, discovered_from)).fetchone()


# ======================= ترتيب الطابور حسب الأهمية =======================
_TRAP_SEGMENT = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})/.*/\1/")


def is_trap(url: str, max_len: int = 500) -> bool:
    """فخاخ الزحف: روابط طويلة جداً، معاملات كثيرة، مقاطع مسار مكررة (تقاويم ومسارات لا نهائية)."""
    if len(url) > max_len:
        return True
    p = urlsplit(url)
    if p.query.count("&") >= 5:
        return True
    segs = [x for x in p.path.split("/") if x]
    if len(segs) > 12:
        return True
    counts = {}
    for x in segs:
        counts[x] = counts.get(x, 0) + 1
        if counts[x] >= 3:
            return True
    return bool(_TRAP_SEGMENT.search(p.path))


def link_priority(src_dom: dict, dst_dom: dict, depth: int, same_site: bool) -> int:
    """أولوية الرابط (الأصغر يُزحف أولاً): سلطة الموقع المصدر، الموقع العراقي، الصفحات القريبة من الجذر.
    كل رابط وارد إضافي يرفع أولوية الصفحة لاحقاً (bump_priority)، مثل ترتيب الأهمية بالروابط الواردة."""
    p = 120
    p -= int(60 * (src_dom.get("authority") or 0))
    p -= int(30 * (dst_dom.get("authority") or 0))
    p -= 25 if dst_dom.get("is_iraqi") else 0
    p += 10 * depth if same_site else 15
    return max(5, min(p, 400))


def bump_priority(conn, url: str):
    conn.execute("UPDATE crawl_jobs SET priority = GREATEST(5, priority - 3) WHERE kind = 'crawl' "
                 "AND md5(url) = md5(%s) AND status = 'pending'", (url,))


def enqueue(conn, kind: str, url: str | None = None, *, domain_id=None, depth=0, priority=100,
            payload=None, delay_s: float = 0, created_by=None, page_id=None) -> int | None:
    row = conn.execute(
        "INSERT INTO crawl_jobs (kind, url, domain_id, depth, priority, payload, scheduled_at, created_by, page_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, now() + make_interval(secs => %s), %s, %s) "
        "ON CONFLICT DO NOTHING RETURNING id",
        (kind, url, domain_id, depth, priority, json.dumps(payload or {}), delay_s, created_by, page_id)).fetchone()
    return row["id"] if row else None


def log(conn, event, level="info", url=None, domain_id=None, status=None, ms=None, msg=None):
    conn.execute("INSERT INTO crawl_logs (level, event, url, domain_id, http_status, duration_ms, message) "
                 "VALUES (%s, %s, %s, %s, %s, %s, %s)", (level, event, url, domain_id, status, ms, (msg or "")[:1000]))


def add_seed(conn, url: str, admin_id=None) -> dict:
    u = normalize_url(url)
    if not u:
        raise ValueError("رابط غير صالح")
    host = urlsplit(u).hostname
    dom = get_or_create_domain(conn, host)
    conn.execute("INSERT INTO seed_urls (url, domain_id, added_by) VALUES (%s, %s, %s) ON CONFLICT (url) DO NOTHING",
                 (u, dom["id"], admin_id))
    enqueue(conn, "crawl", u, domain_id=dom["id"], depth=0, priority=10, created_by=admin_id)
    enqueue(conn, "sitemap", f"{urlsplit(u).scheme}://{urlsplit(u).netloc}/", domain_id=dom["id"], priority=20)
    return {"url": u, "domain_id": dom["id"]}


# ======================= العامل =======================
class Worker:
    def __init__(self, concurrency: int | None = None, worker_id: str | None = None, once: bool = False):
        self.id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.fixed_concurrency = concurrency
        self.once = once                      # للاختبارات: يتوقف عند فراغ القائمة
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10), trust_env=False,
                                        http2=False, verify=True, limits=httpx.Limits(max_connections=100))
        self.processed = 0
        self.active = 0
        self.started = time.time()
        self._robots: dict[str, tuple[float, urllib.robotparser.RobotFileParser]] = {}
        self._image_pool = None

    # ---------- التحكم ----------
    async def state(self) -> str:
        s = await self.redis.get("crawler:state")
        if s is None:
            s = db.get_setting("crawler.state", "running")
            await self.redis.set("crawler:state", s)
        return s

    async def concurrency(self) -> int:
        if self.fixed_concurrency:
            return self.fixed_concurrency
        c = await self.redis.get("crawler:concurrency")
        return int(c or db.get_setting("crawler.concurrency", 8))

    async def heartbeat(self):
        await self.redis.hset(f"worker:{self.id}", mapping={
            "id": self.id, "pid": os.getpid(), "host": socket.gethostname(), "started": int(self.started),
            "active": self.active, "processed": self.processed, "seen": int(time.time())})
        await self.redis.expire(f"worker:{self.id}", 30)
        await self.redis.sadd("workers", self.id)

    def claim(self, n: int, state: str) -> list[dict]:
        if state == "stopped" or n <= 0:
            return []
        kinds = None if state == "running" else ("reindex_domain", "rebuild_index", "delete_outdated",
                                                 "compute_authority", "refresh_terms", "retention", "backup")
        with db.pool().connection() as conn:
            return conn.execute(
                "UPDATE crawl_jobs SET status = 'running', started_at = now(), attempts = attempts + 1, worker = %s "
                "WHERE id IN (SELECT id FROM crawl_jobs WHERE id IN ("
                "  SELECT id FROM (SELECT id, priority, scheduled_at, row_number() OVER "
                "    (PARTITION BY COALESCE(domain_id, -id) ORDER BY priority, scheduled_at) AS rn "
                "   FROM (SELECT id, domain_id, priority, scheduled_at FROM crawl_jobs WHERE status = 'pending' "
                "         AND scheduled_at <= now() AND (%s::text[] IS NULL OR kind = ANY(%s::text[])) "
                "         ORDER BY priority, scheduled_at LIMIT %s) c) r "
                "  WHERE rn <= 2 ORDER BY priority, scheduled_at LIMIT %s) "
                "FOR UPDATE SKIP LOCKED) RETURNING *",
                (self.id, list(kinds) if kinds else None, list(kinds) if kinds else None, n * 20, n)).fetchall()

    def finish(self, job, status="done", error=None, retry_in: float | None = None):
        with db.pool().connection() as conn:
            if retry_in is not None:
                conn.execute("UPDATE crawl_jobs SET status = 'pending', attempts = attempts - 1, worker = NULL, "
                             "scheduled_at = now() + make_interval(secs => %s) WHERE id = %s", (retry_in, job["id"]))
            elif status == "failed" and job["attempts"] < job["max_attempts"]:
                backoff = 60 * (2 ** job["attempts"])
                conn.execute("UPDATE crawl_jobs SET status = 'pending', error = %s, worker = NULL, "
                             "scheduled_at = now() + make_interval(secs => %s) WHERE id = %s",
                             ((error or "")[:2000], backoff, job["id"]))
            else:
                conn.execute("UPDATE crawl_jobs SET status = %s, error = %s, finished_at = now() WHERE id = %s",
                             (status, (error or "")[:2000] if error else None, job["id"]))

    async def run(self):
        tasks: set[asyncio.Task] = set()
        last_sched = 0.0
        try:
            while True:
                await self.heartbeat()
                restart = await self.redis.get("control:restart_workers")
                if restart and datetime.fromisoformat(restart).timestamp() > self.started:
                    break  # إعادة تشغيل آمنة: Docker/systemd يعيد تشغيل العملية
                state = await self.state()
                if time.time() - last_sched > 30:
                    last_sched = time.time()
                    await self.schedule_periodic()
                free = await self.concurrency() - len(tasks)
                jobs = await asyncio.to_thread(self.claim, free, state) if free > 0 else []
                for job in jobs:
                    t = asyncio.create_task(self.handle(job))
                    tasks.add(t)
                    t.add_done_callback(tasks.discard)
                if self.once and not jobs and not tasks:
                    pending = db.fetchone("SELECT count(*) AS n FROM crawl_jobs WHERE status = 'pending' "
                                          "AND scheduled_at <= now() + interval '5 seconds'")["n"]
                    if not pending or state != "running":
                        break
                await asyncio.sleep(0.2 if jobs or self.once else 1.0)
        finally:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if self.once:
                await asyncio.to_thread(refresh_terms)
            await self.redis.srem("workers", self.id)
            await self.redis.delete(f"worker:{self.id}")
            await self.client.aclose()
            await self.redis.aclose()

    async def handle(self, job):
        self.active += 1
        try:
            fn = getattr(self, f"job_{job['kind']}")
            result = await fn(job)
            if isinstance(result, tuple) and result[0] == "retry":
                self.finish(job, retry_in=result[1])
            else:
                self.finish(job, "done")
        except Exception as e:  # أي فشل يسجّل ويعاد حسب السياسة
            self.finish(job, "failed", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}")
            with db.pool().connection() as conn:
                log(conn, "job_failed", "error", job.get("url"), job.get("domain_id"), msg=f"{job['kind']}: {e}")
        finally:
            self.active -= 1
            self.processed += 1

    # ---------- الجدولة الدورية ----------
    async def schedule_periodic(self):
        if not await self.redis.set("scheduler:lock", self.id, nx=True, ex=25):
            return
        with db.pool().connection() as conn:
            due = conn.execute(
                "SELECT p.url, p.domain_id, p.depth FROM crawled_pages p JOIN domains d ON d.id = p.domain_id "
                "WHERE p.next_crawl_at <= now() AND d.status = 'active' ORDER BY p.next_crawl_at LIMIT 500").fetchall()
            for r in due:
                enqueue(conn, "crawl", r["url"], domain_id=r["domain_id"], depth=r["depth"], priority=150)
            if due:
                conn.execute("UPDATE crawled_pages SET next_crawl_at = NULL WHERE url = ANY(%s)",
                             ([r["url"] for r in due],))
            for kind, every in (("refresh_terms", 600), ("compute_authority", 86400), ("retention", 3600)):
                key = f"periodic:{kind}"
                if await self.redis.set(key, "1", nx=True, ex=every):
                    enqueue(conn, kind, None, priority=300)

    # ---------- robots.txt ----------
    async def robots(self, conn, dom, scheme: str, netloc: str | None = None) -> urllib.robotparser.RobotFileParser:
        """RFC 9309: ‏4xx = مسموح كله، 5xx أو تعذّر الوصول = ممنوع كله مؤقتاً."""
        host = netloc or dom["host"]
        cached = self._robots.get(host)
        if cached and time.time() < cached[0]:
            return cached[1]
        ttl = 3600
        rp = urllib.robotparser.RobotFileParser()
        fresh = dom["robots_fetched_at"] and dom["robots_fetched_at"] > datetime.now(timezone.utc) - timedelta(hours=24)
        body = dom["robots_txt"] if fresh else None
        fresh_fail = False
        if body is None:
            try:
                res = await safe_fetch(self.client, f"{scheme}://{host}/robots.txt", {"User-Agent": ua()},
                                       max_bytes=500_000, allowed_ports=self.ports())
                if res.status == 200:
                    body = res.content.decode("utf-8", "replace")
                elif res.status >= 500:
                    body, fresh_fail = "User-agent: *\nDisallow: /", True
                else:
                    body = ""
            except (httpx.HTTPError, BlockedDestination) as e:
                log(conn, "robots_unreachable", "warn", f"{scheme}://{host}/robots.txt", dom["id"], msg=str(e))
                body, fresh_fail = "User-agent: *\nDisallow: /", True
            rp.parse(body.splitlines())
            if fresh_fail:
                self._robots[host] = (time.time() + 600, rp)
                return rp
            delay = rp.crawl_delay(UA_TOKEN)
            conn.execute("UPDATE domains SET robots_txt = %s, robots_fetched_at = now(), robots_crawl_delay = %s "
                         "WHERE id = %s", (body[:100_000], float(delay) if delay else None, dom["id"]))
        else:
            rp.parse(body.splitlines())
        self._robots[host] = (time.time() + ttl, rp)
        return rp

    def ports(self):
        return tuple(db.get_setting("crawler.allowed_ports", [80, 443]))

    async def polite(self, dom) -> float:
        """يرجع 0 إذا مسموح الآن، وإلا عدد الثواني للانتظار."""
        delay_ms = max(dom["min_delay_ms"], int((dom["robots_crawl_delay"] or 0) * 1000))
        key = f"throttle:{dom['host']}"
        if await self.redis.set(key, "1", nx=True, px=delay_ms):
            return 0
        ttl = await self.redis.pttl(key)
        return max(ttl, 100) / 1000

    # ---------- مهمة: زحف صفحة ----------
    async def job_crawl(self, job):
        url = job["url"]
        parts = urlsplit(url)
        force = bool(job["payload"].get("force"))
        with db.pool().connection() as conn:
            dom = get_or_create_domain(conn, parts.hostname)
            if dom["status"] == "blocked":
                return
            if dom["status"] == "paused":
                return ("retry", 3600)
            if any(parts.path.startswith(p) for p in dom["excluded_paths"] if p):
                self.record(conn, url, dom, job["depth"], status="excluded")
                log(conn, "excluded_path", "info", url, dom["id"])
                return
            if dom["page_count"] >= dom["max_pages"] and not force:
                exists = conn.execute("SELECT 1 FROM crawled_pages WHERE url_hash = %s", (url_hash(url),)).fetchone()
                if not exists:
                    return
            rp = await self.robots(conn, dom, parts.scheme, parts.netloc)
            if not rp.can_fetch(UA_TOKEN, url):
                self.record(conn, url, dom, job["depth"], status="robots_blocked")
                conn.execute("DELETE FROM indexed_documents WHERE url = %s", (url,))
                log(conn, "robots_blocked", "info", url, dom["id"])
                return
            prev = conn.execute("SELECT * FROM crawled_pages WHERE url_hash = %s", (url_hash(url),)).fetchone()

        wait = await self.polite(dom)
        if wait:
            return ("retry", wait)

        headers = {"User-Agent": ua(), "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
                   "Accept-Language": "ar,ckb;q=0.9,en;q=0.8", "Accept-Encoding": "gzip, deflate"}
        if prev and not force:
            if prev["etag"]:
                headers["If-None-Match"] = prev["etag"]
            if prev["last_modified"]:
                headers["If-Modified-Since"] = prev["last_modified"]

        t0 = time.monotonic()
        max_bytes = int(db.get_setting("crawler.max_page_bytes", 5_000_000))
        try:
            res = await safe_fetch(self.client, url, headers, max_bytes=max_bytes, allowed_ports=self.ports())
        except BlockedDestination as e:
            with db.pool().connection() as conn:
                self.record(conn, url, dom, job["depth"], status="error", error=str(e))
                log(conn, "ssrf_blocked", "warn", url, dom["id"], msg=str(e))
                conn.execute("INSERT INTO security_events (kind, severity, details) VALUES ('crawler_ssrf_blocked', 'medium', %s)",
                             (json.dumps({"host": parts.hostname, "reason": str(e)}, ensure_ascii=False),))
            return
        except httpx.HTTPError as e:
            with db.pool().connection() as conn:
                conn.execute("UPDATE domains SET error_count = error_count + 1 WHERE id = %s", (dom["id"],))
                log(conn, "network_error", "error", url, dom["id"], msg=f"{type(e).__name__}: {e}")
            raise
        ms = int((time.monotonic() - t0) * 1000)

        with db.pool().connection() as conn:
            final = normalize_url(res.url) or url
            if res.redirects:
                log(conn, "redirect", "info", url, dom["id"], res.redirects[0][1], ms, f"→ {final}")
                if urlsplit(final).hostname != parts.hostname or final != url:
                    self.record(conn, url, dom, job["depth"], status="redirect", http=res.redirects[0][1], redirected_to=final)
                    conn.execute("DELETE FROM indexed_documents WHERE url = %s", (url,))
                    fdom = get_or_create_domain(conn, urlsplit(final).hostname)
                    if self.may_follow(fdom, dom):
                        enqueue(conn, "crawl", final, domain_id=fdom["id"], depth=job["depth"], priority=job["priority"])
                    return
            if res.status == 304 and prev:
                conn.execute("UPDATE crawled_pages SET status = 'not_modified', http_status = 304, crawl_count = crawl_count + 1, "
                             "last_crawled_at = now(), next_crawl_at = now() + make_interval(hours => %s) WHERE id = %s",
                             (dom["crawl_frequency_h"], prev["id"]))
                log(conn, "not_modified", "info", url, dom["id"], 304, ms)
                return
            if res.status in (404, 410) or res.status >= 400 and res.status < 500:
                self.record(conn, url, dom, job["depth"], status="broken", http=res.status)
                conn.execute("DELETE FROM indexed_documents WHERE url = %s", (url,))
                log(conn, "broken", "warn", url, dom["id"], res.status, ms)
                return
            if res.status >= 500:
                log(conn, "http_error", "error", url, dom["id"], res.status, ms)
                raise RuntimeError(f"HTTP {res.status}")
            if res.truncated:
                self.record(conn, url, dom, job["depth"], status="too_large", http=res.status)
                log(conn, "too_large", "warn", url, dom["id"], res.status, ms)
                return

            ctype = res.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype in ("text/html", "application/xhtml+xml"):
                html = _decode(res.content, res.headers.get("content-type", ""))
                parsed, doc_type = parse_html(html, final), "html"
            elif ctype == "application/pdf":
                parsed, doc_type = parse_pdf(res.content), "pdf"
            else:
                self.record(conn, url, dom, job["depth"], status="unsupported", http=res.status, ctype=ctype)
                return

            content_hash = hashlib.sha256((parsed.title + "\n" + parsed.text).encode()).digest()
            sh = T.simhash(parsed.title + " " + parsed.text[:50_000])
            # canonical يشير لصفحة ثانية: نزحفها هي بدل هذه
            if parsed.canonical and parsed.canonical != final and urlsplit(parsed.canonical).hostname == urlsplit(final).hostname:
                self.record(conn, url, dom, job["depth"], status="duplicate", http=res.status, canonical=parsed.canonical)
                conn.execute("DELETE FROM indexed_documents WHERE url = %s", (url,))
                enqueue(conn, "crawl", parsed.canonical, domain_id=dom["id"], depth=job["depth"], priority=job["priority"])
                log(conn, "canonical", "info", url, dom["id"], res.status, ms, f"→ {parsed.canonical}")
                return
            status = "noindex" if parsed.noindex else "ok"
            page = self.record(conn, final, dom, job["depth"], status=status, http=res.status, ctype=ctype,
                               content_hash=content_hash, simhash=sh, etag=res.headers.get("etag"),
                               last_modified=res.headers.get("last-modified"), canonical=parsed.canonical,
                               next_h=dom["crawl_frequency_h"])
            log(conn, "fetched", "info", final, dom["id"], res.status, ms)
            if parsed.noindex:
                conn.execute("DELETE FROM indexed_documents WHERE page_id = %s", (page["id"],))
            else:
                iv = conn.execute("SELECT id, analyzer_version FROM index_versions WHERE status = 'active'").fetchone()
                info = index_document(conn, page_id=page["id"], domain_id=dom["id"], host=dom["host"], url=final,
                                      parsed=parsed, doc_type=doc_type, domain_category=dom["category"], simhash=sh,
                                      content_hash=content_hash, analyzer_version=T.ANALYZER_VERSION,
                                      index_version_id=iv["id"])
                if info["duplicate_of"]:
                    log(conn, "duplicate", "info", final, dom["id"], msg=f"مطابق للصفحة {info['duplicate_of']}")
            conn.execute("UPDATE domains SET last_crawled_at = now(), page_count = "
                         "(SELECT count(*) FROM crawled_pages WHERE domain_id = %s AND status IN ('ok', 'not_modified')) "
                         "WHERE id = %s", (dom["id"], dom["id"]))
            if not parsed.nofollow:
                self.links(conn, page["id"], dom, parsed.links, job["depth"])
            if doc_type == "html" and db.get_setting("search.image_enabled", True):
                for img_url, alt, ctx, w, h in parsed.images[:25]:
                    if (w and w < 80) or (h and h < 80):
                        continue
                    conn.execute(
                        "INSERT INTO image_index (image_url, url_hash, page_id, domain_id, alt, context) "
                        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (url_hash) DO NOTHING",
                        (img_url, url_hash(img_url), page["id"], dom["id"], alt, (parsed.title + " · " + ctx)[:600]))
                    enqueue(conn, "image", img_url, domain_id=dom["id"], priority=200, page_id=page["id"])

    def may_follow(self, target_dom, from_dom) -> bool:
        if target_dom["status"] != "active":
            return False
        if target_dom["id"] == from_dom["id"] or target_dom["is_iraqi"]:
            return True
        if db.get_setting("crawler.discovery_mode", "iraq") == "open" or db.get_setting("crawler.follow_external", False):
            return True
        # في وضع «العراق»: النطاقات الدولية تُزحف فقط إذا أُضيفت عمداً كبذور
        with db.pool().connection() as conn:
            return conn.execute("SELECT 1 FROM seed_urls WHERE domain_id = %s LIMIT 1", (target_dom["id"],)).fetchone() is not None

    def links(self, conn, page_id, dom, links, depth):
        conn.execute("DELETE FROM page_links WHERE src_page_id = %s", (page_id,))
        max_len = int(db.get_setting("crawler.max_url_length", 500))
        max_pending = int(db.get_setting("crawler.max_pending_per_domain", 500))
        pending: dict[int, int] = {}
        seen = set()
        for link, anchor in links[:500]:
            h = url_hash(link)
            if h in seen:
                continue
            seen.add(h)
            host = urlsplit(link).hostname
            if urlsplit(link).path.lower().endswith(IMAGE_EXT) or is_trap(link, max_len):
                continue
            tdom = dom if host == dom["host"] else get_or_create_domain(conn, host, discovered_from=dom["id"])
            conn.execute("INSERT INTO page_links (src_page_id, dst_url_hash, dst_url, dst_domain_id, anchor) "
                         "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", (page_id, h, link, tdom["id"], anchor))
            same = tdom["id"] == dom["id"]
            nd = depth + 1 if same else 0
            if (same and nd > dom["crawl_depth"]) or not self.may_follow(tdom, dom):
                continue
            if tdom["page_count"] >= tdom["max_pages"]:
                continue
            if conn.execute("SELECT 1 FROM crawled_pages WHERE url_hash = %s", (h,)).fetchone():
                continue
            if tdom["id"] not in pending:
                pending[tdom["id"]] = conn.execute("SELECT count(*) AS n FROM crawl_jobs WHERE domain_id = %s "
                                                   "AND status = 'pending'", (tdom["id"],)).fetchone()["n"]
            if pending[tdom["id"]] >= max_pending:
                bump_priority(conn, link)      # موجود بالطابور: رابط وارد جديد يرفع أهميته
                continue
            if enqueue(conn, "crawl", link, domain_id=tdom["id"], depth=nd,
                       priority=link_priority(dom, tdom, nd, same)):
                pending[tdom["id"]] += 1
            else:
                bump_priority(conn, link)

    def record(self, conn, url, dom, depth, *, status, http=None, ctype=None, content_hash=None, simhash=None,
               etag=None, last_modified=None, canonical=None, error=None, redirected_to=None, next_h=None):
        return conn.execute(
            """
            INSERT INTO crawled_pages (url, url_hash, domain_id, depth, http_status, content_type, content_hash, simhash,
                etag, last_modified, canonical_url, status, error, redirected_to, crawl_count, last_crawled_at, next_crawl_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, now(),
                CASE WHEN %s::int IS NULL THEN NULL ELSE now() + make_interval(hours => %s::int) END)
            ON CONFLICT (url_hash) DO UPDATE SET http_status = EXCLUDED.http_status, content_type = EXCLUDED.content_type,
                content_hash = EXCLUDED.content_hash, simhash = EXCLUDED.simhash, etag = EXCLUDED.etag,
                last_modified = EXCLUDED.last_modified, canonical_url = EXCLUDED.canonical_url, status = EXCLUDED.status,
                error = EXCLUDED.error, redirected_to = EXCLUDED.redirected_to, crawl_count = crawled_pages.crawl_count + 1,
                last_crawled_at = now(), next_crawl_at = EXCLUDED.next_crawl_at
            RETURNING id
            """,
            (url, url_hash(url), dom["id"], depth, http, ctype, content_hash, simhash, etag, last_modified, canonical,
             status, error, redirected_to, next_h, next_h)).fetchone()

    # ---------- مهمة: sitemap ----------
    async def job_sitemap(self, job):
        parts = urlsplit(job["url"])
        base = f"{parts.scheme}://{parts.netloc}"
        with db.pool().connection() as conn:
            dom = get_or_create_domain(conn, parts.hostname)
            rp = await self.robots(conn, dom, parts.scheme, parts.netloc)
        maps = [normalize_url(m, base) for m in (rp.site_maps() or [])] or [base + "/sitemap.xml"]
        maps = [m for m in maps if m]
        if job["payload"].get("sitemap"):
            maps = [job["payload"]["sitemap"]]
        added = 0
        for sm in maps[:20]:
            try:
                res = await safe_fetch(self.client, sm, {"User-Agent": ua()}, max_bytes=20_000_000, allowed_ports=self.ports())
            except (httpx.HTTPError, BlockedDestination) as e:
                with db.pool().connection() as conn:
                    log(conn, "sitemap_error", "warn", sm, dom["id"], msg=str(e))
                continue
            if res.status != 200:
                continue
            content = res.content
            if sm.endswith(".gz"):
                import gzip
                content = gzip.decompress(content)[:50_000_000]
            urls, children = parse_sitemap(content)
            with db.pool().connection() as conn:
                for child in children[:50]:
                    enqueue(conn, "sitemap", base + "/", domain_id=dom["id"], priority=30, payload={"sitemap": child})
                for u in urls[: dom["max_pages"]]:
                    nu = normalize_url(u)
                    if nu and urlsplit(nu).hostname == dom["host"] and rp.can_fetch(UA_TOKEN, nu):
                        if not conn.execute("SELECT 1 FROM crawled_pages WHERE url_hash = %s", (url_hash(nu),)).fetchone():
                            if enqueue(conn, "crawl", nu, domain_id=dom["id"], depth=1, priority=110):
                                added += 1
                log(conn, "sitemap", "info", sm, dom["id"], 200, msg=f"{len(urls)} رابط، أضيف {added}")

    # ---------- مهمة: صورة ----------
    async def job_image(self, job):
        from .images import process_image_bytes
        with db.pool().connection() as conn:
            img = conn.execute("SELECT * FROM image_index WHERE url_hash = %s", (url_hash(job["url"]),)).fetchone()
            if not img or img["status"] == "ok":
                return
            dom = get_or_create_domain(conn, urlsplit(job["url"]).hostname)
            rp = await self.robots(conn, dom, urlsplit(job["url"]).scheme, urlsplit(job["url"]).netloc)
            if not rp.can_fetch(UA_TOKEN, job["url"]):
                conn.execute("UPDATE image_index SET status = 'blocked', error = 'robots.txt' WHERE id = %s", (img["id"],))
                return
        wait = await self.polite(dom)
        if wait:
            return ("retry", wait)
        try:
            res = await safe_fetch(self.client, job["url"], {"User-Agent": ua(), "Accept": "image/*"},
                                   max_bytes=8_000_000, allowed_ports=self.ports())
        except BlockedDestination as e:
            with db.pool().connection() as conn:
                conn.execute("UPDATE image_index SET status = 'failed', error = %s WHERE id = %s", (str(e), img["id"]))
            return
        with db.pool().connection() as conn:
            if res.status != 200 or not res.headers.get("content-type", "").startswith("image/") or res.truncated:
                conn.execute("UPDATE image_index SET status = 'failed', error = %s, fetched_at = now() WHERE id = %s",
                             (f"HTTP {res.status} {res.headers.get('content-type', '')}", img["id"]))
                return
        await process_image_bytes(img["id"], res.content)

    # ---------- مهام الصيانة ----------
    async def job_reindex_domain(self, job):
        with db.pool().connection() as conn:
            rows = conn.execute("SELECT url, depth FROM crawled_pages WHERE domain_id = %s AND status IN "
                                "('ok', 'not_modified', 'error')", (job["domain_id"],)).fetchall()
            for r in rows:
                enqueue(conn, "crawl", r["url"], domain_id=job["domain_id"], depth=r["depth"], priority=40,
                        payload={"force": True})
            log(conn, "reindex_domain", "info", domain_id=job["domain_id"], msg=f"{len(rows)} صفحة")

    async def job_rebuild_index(self, job):
        await asyncio.to_thread(rebuild_index, job["payload"].get("version_id"))

    async def job_delete_outdated(self, job):
        days = int(job["payload"].get("days", 180))
        with db.pool().connection() as conn:
            n1 = conn.execute("DELETE FROM indexed_documents d USING crawled_pages p WHERE p.id = d.page_id AND "
                              "(p.status IN ('broken', 'robots_blocked', 'noindex') OR p.last_crawled_at < now() - make_interval(days => %s))",
                              (days,)).rowcount
            log(conn, "delete_outdated", "info", msg=f"حُذف {n1} مستند")

    async def job_compute_authority(self, job):
        await asyncio.to_thread(compute_authority)

    async def job_refresh_terms(self, job):
        await asyncio.to_thread(refresh_terms)

    async def job_retention(self, job):
        await asyncio.to_thread(apply_retention)

    async def job_backup(self, job):
        from .backup import run_backup
        await asyncio.to_thread(run_backup, job["payload"].get("backup_id"))


def _decode(content: bytes, ctype: str) -> str:
    charset = None
    if "charset=" in ctype:
        charset = ctype.split("charset=")[-1].split(";")[0].strip().strip('"')
    if not charset:
        head = content[:2048].decode("ascii", "ignore").lower()
        if "charset=" in head:
            charset = head.split("charset=")[1].split('"')[0].split("'")[0].split(";")[0].strip(" />")
    for enc in (charset, "utf-8", "windows-1256"):
        if not enc:
            continue
        try:
            return content.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", "replace")


# ======================= وظائف الصيانة المتزامنة =======================
def rebuild_index(version_id=None):
    with db.connect() as conn:
        if version_id is None:
            version_id = conn.execute(
                "INSERT INTO index_versions (label, analyzer_version, status, notes) "
                "VALUES ('v' || (SELECT count(*) + 1 FROM index_versions), %s, 'building', 'إعادة بناء') RETURNING id",
                (T.ANALYZER_VERSION,)).fetchone()["id"]
        try:
            last, n = 0, 0
            while True:
                ids = [r["page_id"] for r in conn.execute(
                    "SELECT page_id FROM indexed_documents WHERE page_id > %s ORDER BY page_id LIMIT 500", (last,))]
                if not ids:
                    break
                with conn.transaction():
                    for pid in ids:
                        reanalyze(conn, pid, T.ANALYZER_VERSION, version_id)
                n += len(ids)
                last = ids[-1]
                conn.execute("UPDATE index_versions SET doc_count = %s WHERE id = %s", (n, version_id))
            with conn.transaction():
                conn.execute("UPDATE index_versions SET status = 'retired' WHERE status = 'active'")
                conn.execute("UPDATE index_versions SET status = 'active', activated_at = now(), doc_count = %s "
                             "WHERE id = %s", (n, version_id))
        except Exception as e:
            conn.execute("UPDATE index_versions SET status = 'failed', notes = %s WHERE id = %s", (str(e)[:500], version_id))
            raise
    refresh_terms()


def refresh_terms():
    with db.connect() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM index_terms")
            conn.execute("INSERT INTO index_terms (term, df) SELECT word, ndoc FROM "
                         "ts_stat('SELECT tsv FROM indexed_documents WHERE duplicate_of IS NULL') "
                         "WHERE length(word) BETWEEN 2 AND 40")


def compute_authority(iterations: int = 20, damping: float = 0.85):
    """PageRank على مستوى النطاقات، ثم سمعة النطاق = سلطة + نوع النطاق − نسبة الأخطاء والسبام."""
    import math
    with db.connect() as conn:
        edges = conn.execute(
            "SELECT p.domain_id AS src, l.dst_domain_id AS dst, count(*) AS w FROM page_links l "
            "JOIN crawled_pages p ON p.id = l.src_page_id WHERE l.dst_domain_id IS NOT NULL "
            "AND l.dst_domain_id <> p.domain_id GROUP BY 1, 2").fetchall()
        nodes = [r["id"] for r in conn.execute("SELECT id FROM domains")]
        if not nodes:
            return
        idx = {n: i for i, n in enumerate(nodes)}
        out_w = [0.0] * len(nodes)
        for e in edges:
            out_w[idx[e["src"]]] += e["w"]
        rank = [1.0 / len(nodes)] * len(nodes)
        for _ in range(iterations):
            new = [(1 - damping) / len(nodes)] * len(nodes)
            dangling = sum(rank[i] for i in range(len(nodes)) if out_w[i] == 0)
            for i in range(len(nodes)):
                new[i] += damping * dangling / len(nodes)
            for e in edges:
                s, d = idx[e["src"]], idx[e["dst"]]
                new[d] += damping * rank[s] * e["w"] / out_w[s]
            rank = new
        top = max(rank) or 1
        with conn.transaction():
            for n, r in zip(nodes, rank):
                authority = math.log1p(r / top * 100) / math.log1p(100)
                conn.execute(
                    "UPDATE domains d SET authority = %s, reputation = LEAST(1, GREATEST(0, "
                    "0.35 + 0.35 * %s + CASE WHEN host LIKE '%%.gov.iq' THEN 0.25 WHEN host LIKE '%%.edu.iq' THEN 0.2 "
                    "WHEN is_iraqi THEN 0.05 ELSE 0 END "
                    "- 0.2 * LEAST(1, error_count::real / GREATEST(page_count, 1)) "
                    "- 0.4 * COALESCE((SELECT avg(spam_score) FROM indexed_documents x WHERE x.domain_id = d.id), 0))) "
                    "WHERE id = %s", (authority, authority, n))
            budget = int(db.get_setting("crawler.new_domain_budget", 200))
            cap = int(db.get_setting("crawler.max_budget", 100000))
            conn.execute("UPDATE domains SET max_pages = LEAST(%s, GREATEST(max_pages, (%s * (1 + 50 * authority))::int)) "
                         "WHERE budget_auto AND NOT is_iraqi", (cap, budget))


def apply_retention():
    s = db.get_settings("retention.")
    with db.connect() as conn:
        conn.execute("DELETE FROM crawl_logs WHERE ts < now() - make_interval(days => %s)", (int(s.get("retention.crawl_logs_days", 30)),))
        conn.execute("DELETE FROM security_events WHERE ts < now() - make_interval(days => %s)", (int(s.get("retention.security_events_days", 90)),))
        conn.execute("DELETE FROM audit_logs WHERE ts < now() - make_interval(days => %s)", (int(s.get("retention.audit_logs_days", 365)),))
        conn.execute("DELETE FROM ops_metrics_hourly WHERE hour < now() - make_interval(days => %s)", (int(s.get("retention.ops_metrics_days", 400)),))
        conn.execute("DELETE FROM admin_sessions WHERE expires_at < now() - interval '7 days'")
        conn.execute("DELETE FROM crawl_jobs WHERE status IN ('done', 'cancelled') AND finished_at < now() - interval '7 days'")
    from .privacy import cleanup_temp
    cleanup_temp()
