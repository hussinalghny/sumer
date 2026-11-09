"""واجهة لوحة التحكم. كل مسار يفحص الصلاحية بالخلفية عبر auth.require، وكل تغيير يسجَّل في audit_logs."""

import io
import json
import secrets
from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field

from . import ai, auth, backup, crawler, db, metrics, privacy, rconn
from . import search as S
from .auth import AdminCtx, audit, require
from .config import settings

router = APIRouter(prefix="/api/admin")
PAGE = 25


def _page(p: int) -> int:
    return max(0, (p - 1) * PAGE)


def _plain(rows):
    def conv(v):
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if isinstance(v, (bytes, memoryview)):
            return bytes(v).hex()
        return v
    if rows is None:
        return None
    if isinstance(rows, list):
        return [{k: conv(v) for k, v in dict(r).items()} for r in rows]
    return {k: conv(v) for k, v in dict(rows).items()}


# ============================ المصادقة ============================
class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip = auth.client_ip(request)
    limit = int(db.get_setting("ratelimit.admin_login_per_15m", 10))
    if not await privacy.allow(rconn.get(), "admin_login", ip or "unknown", limit, 900):
        db.execute("INSERT INTO security_events (kind, severity, details) VALUES ('admin_login_rate_limited', 'high', '{}')")
        raise HTTPException(429, "rate_limited")
    user = db.fetchone("SELECT * FROM admin_users WHERE email = %s", (body.email.strip().lower(),))
    now = datetime.now(timezone.utc)
    if not user or user["status"] != "active" or (user["locked_until"] and user["locked_until"] > now) \
            or not auth.verify_password(user["password_hash"], body.password):
        if user:
            db.execute("UPDATE admin_users SET failed_logins = failed_logins + 1, locked_until = CASE WHEN failed_logins + 1 >= %s "
                       "THEN now() + make_interval(mins => %s) ELSE locked_until END WHERE id = %s",
                       (auth.MAX_FAILED, auth.LOCK_MINUTES, user["id"]))
        audit(None, "login_failed", body.email[:200], success=False, ip=ip, email=body.email[:200])
        db.execute("INSERT INTO security_events (kind, severity, details) VALUES ('admin_login_failed', 'medium', %s)",
                   (json.dumps({"email": body.email[:200]}),))
        raise HTTPException(401, "invalid_credentials")
    db.execute("UPDATE admin_users SET failed_logins = 0, locked_until = NULL, last_login_at = now() WHERE id = %s", (user["id"],))
    token, csrf = auth.create_session(user["id"], ip, request.headers.get("user-agent"), mfa_passed=not user["totp_enabled"])
    response.set_cookie(auth.COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="strict",
                        path="/api/admin", max_age=auth.SESSION_HOURS * 3600)
    audit(None, "login", user["email"], {"mfa_pending": user["totp_enabled"]}, ip=ip, email=user["email"])
    return {"mfa_required": user["totp_enabled"], "csrf": csrf}


@router.post("/auth/mfa")
def mfa(body: CodeIn, ctx: AdminCtx = require(allow_pre_mfa=True)):
    user = db.fetchone("SELECT * FROM admin_users WHERE id = %s", (ctx.id,))
    if not auth.verify_totp(user, body.code):
        audit(ctx, "mfa_failed", success=False)
        raise HTTPException(401, "invalid_code")
    db.execute("UPDATE admin_sessions SET mfa_passed = TRUE WHERE token_hash = %s", (ctx.session["token_hash"],))
    audit(ctx, "mfa_passed")
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response, ctx: AdminCtx = require(allow_pre_mfa=True)):
    db.execute("UPDATE admin_sessions SET revoked_at = now() WHERE token_hash = %s", (ctx.session["token_hash"],))
    response.delete_cookie(auth.COOKIE, path="/api/admin")
    audit(ctx, "logout")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    ctx = auth.load_session(request)
    if not ctx:
        raise HTTPException(401, "unauthenticated")
    return {"user": ctx.user, "permissions": sorted(ctx.perms), "csrf": ctx.session["csrf_token"],
            "mfa_passed": ctx.session["mfa_passed"], "require_2fa": db.get_setting("security.require_2fa", False)}


class PasswordIn(BaseModel):
    current: str
    new: str


@router.post("/auth/password")
def change_password(body: PasswordIn, ctx: AdminCtx = require(allow_pre_mfa=False)):
    user = db.fetchone("SELECT * FROM admin_users WHERE id = %s", (ctx.id,))
    if not auth.verify_password(user["password_hash"], body.current):
        raise HTTPException(401, "invalid_credentials")
    try:
        h = auth.hash_password(body.new)
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.execute("UPDATE admin_users SET password_hash = %s, must_change_pw = FALSE WHERE id = %s", (h, ctx.id))
    db.execute("UPDATE admin_sessions SET revoked_at = now() WHERE user_id = %s AND token_hash <> %s",
               (ctx.id, ctx.session["token_hash"]))
    audit(ctx, "password_changed")
    return {"ok": True}


@router.post("/auth/2fa/setup")
def twofa_setup(ctx: AdminCtx = require(allow_pre_mfa=True)):
    if not ctx.session["mfa_passed"] and ctx.user["totp_enabled"]:
        raise HTTPException(401, "mfa_required")
    secret = pyotp.random_base32()
    db.execute("UPDATE admin_users SET totp_secret_enc = %s, totp_enabled = FALSE WHERE id = %s",
               (auth.encrypt_secret(secret), ctx.id))
    audit(ctx, "2fa_setup_started")
    name = db.get_setting("site.name_en", "Sumer")
    return {"secret": secret, "uri": pyotp.TOTP(secret).provisioning_uri(ctx.user["email"], issuer_name=f"{name} Admin")}


@router.post("/auth/2fa/enable")
def twofa_enable(body: CodeIn, ctx: AdminCtx = require(allow_pre_mfa=True)):
    user = db.fetchone("SELECT * FROM admin_users WHERE id = %s", (ctx.id,))
    if not auth.verify_totp(user, body.code):
        raise HTTPException(401, "invalid_code")
    db.execute("UPDATE admin_users SET totp_enabled = TRUE WHERE id = %s", (ctx.id,))
    db.execute("UPDATE admin_sessions SET mfa_passed = TRUE WHERE token_hash = %s", (ctx.session["token_hash"],))
    audit(ctx, "2fa_enabled")
    return {"ok": True}


# ============================ النظرة العامة ============================
@router.get("/overview")
async def overview(request: Request, ctx: AdminCtx = require("dashboard.view")):
    r = rconn.get()
    ov, sysm = metrics.overview(), metrics.system()
    redis_h, db_h, idx_h = await metrics.redis_health(r), metrics.database(), metrics.index_health()
    w = await metrics.workers(r)
    started = await r.get("api:started")
    return {"metrics": ov, "system": sysm, "uptime_s": int(datetime.now(timezone.utc).timestamp() - float(started)) if started else None,
            "workers": w, "crawler_state": await r.get("crawler:state") or db.get_setting("crawler.state"),
            "alerts": metrics.alerts(sysm, ov, redis_h, db_h, idx_h, w),
            "health": {"database": db_h.get("ok"), "redis": redis_h.get("ok"), "index": idx_h.get("ok")}}


# ============================ التحكم بالبحث ============================
SEARCH_KEYS = ("search.enabled", "search.image_enabled", "search.safe_default", "search.ranking",
               "search.region_priority", "search.per_domain_limit")


@router.get("/search/settings")
def search_settings(ctx: AdminCtx = require("search.view")):
    return {k: db.get_setting(k) for k in SEARCH_KEYS}


class SettingsIn(BaseModel):
    values: dict


def _validate_search(k, v):
    if k in ("search.enabled", "search.image_enabled") and not isinstance(v, bool):
        raise HTTPException(422, f"{k}: boolean")
    if k == "search.safe_default" and v not in ("strict", "moderate", "off"):
        raise HTTPException(422, k)
    if k == "search.ranking":
        allowed = {"text", "title", "authority", "quality", "freshness", "iraqi", "language", "spam_penalty"}
        if not isinstance(v, dict) or not set(v) <= allowed or not all(isinstance(x, (int, float)) and 0 <= x <= 10 for x in v.values()):
            raise HTTPException(422, "ranking: أوزان بين 0 و10")
    if k == "search.region_priority" and (not isinstance(v, dict) or not all(isinstance(x, (int, float)) and 0 <= x <= 5 for x in v.values())):
        raise HTTPException(422, k)
    if k == "search.per_domain_limit" and (not isinstance(v, int) or not 1 <= v <= 10):
        raise HTTPException(422, k)


@router.put("/search/settings")
def update_search_settings(body: SettingsIn, ctx: AdminCtx = require("search.manage")):
    for k, v in body.values.items():
        if k not in SEARCH_KEYS:
            raise HTTPException(422, f"مفتاح غير مسموح: {k}")
        _validate_search(k, v)
    for k, v in body.values.items():
        db.set_setting(k, v, ctx.id)
    audit(ctx, "search_settings_updated", details=body.values)
    return {k: db.get_setting(k) for k in SEARCH_KEYS}


@router.get("/languages")
def languages(ctx: AdminCtx = require("search.view")):
    return db.fetchall("SELECT * FROM language_metadata ORDER BY priority DESC")


class LangIn(BaseModel):
    enabled: bool
    priority: float = Field(ge=0, le=5)


@router.put("/languages/{code}")
def update_language(code: str, body: LangIn, ctx: AdminCtx = require("search.manage")):
    n = db.fetchone("UPDATE language_metadata SET enabled = %s, priority = %s WHERE code = %s RETURNING code",
                    (body.enabled, body.priority, code))
    if not n:
        raise HTTPException(404)
    audit(ctx, "language_updated", code, body.model_dump())
    return {"ok": True}


class TestIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)
    lang: str | None = None
    category: str | None = None
    safe: str = "moderate"


@router.post("/search/test")
def test_search(body: TestIn, ctx: AdminCtx = require("search.test")):
    # استعلامات المشرف للاختبار لا تُحفظ أيضاً
    return S.search(body.q, 1, {"lang": body.lang, "category": body.category}, safe=body.safe, explain=True)


@router.get("/search/eval-set")
def eval_set(ctx: AdminCtx = require("search.view")):
    return db.get_setting("search.eval_set", [])


class EvalItem(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    expected_url: str = Field(min_length=5, max_length=2000)


class EvalSetIn(BaseModel):
    items: list[EvalItem] = Field(max_length=500)


@router.put("/search/eval-set")
def update_eval_set(body: EvalSetIn, ctx: AdminCtx = require("search.manage")):
    db.set_setting("search.eval_set", [i.model_dump() for i in body.items], ctx.id)
    audit(ctx, "eval_set_updated", details={"count": len(body.items)})
    return {"ok": True}


@router.post("/search/evaluate")
def evaluate(ctx: AdminCtx = require("search.test")):
    """تقييم جودة البحث على مجموعة يحددها المشرف: MRR وP@1 وP@3."""
    items = db.get_setting("search.eval_set", []) or []
    rows, rr, p1, p3 = [], 0.0, 0, 0
    for it in items:
        res = S.search(it["query"], 1)
        urls = [r["url"] for r in res["results"]]
        rank = urls.index(it["expected_url"]) + 1 if it["expected_url"] in urls else None
        rr += 1 / rank if rank else 0
        p1 += 1 if rank == 1 else 0
        p3 += 1 if rank and rank <= 3 else 0
        rows.append({"query": it["query"], "expected_url": it["expected_url"], "rank": rank, "top": urls[:3]})
    n = len(items) or 1
    return {"count": len(items), "mrr": round(rr / n, 3), "p_at_1": round(p1 / n, 3), "p_at_3": round(p3 / n, 3), "rows": rows}


@router.get("/search/quality")
def quality(ctx: AdminCtx = require("search.view")):
    q = db.fetchone("""
        SELECT COALESCE(sum(value) FILTER (WHERE metric = 'searches'), 0) AS searches,
               COALESCE(sum(value) FILTER (WHERE metric = 'zero_results'), 0) AS zero_results
        FROM ops_metrics_hourly WHERE hour > now() - interval '7 days'""")
    spam = db.fetchall("SELECT signal, count(*) AS n, round(avg(score)::numeric, 2) AS avg_score FROM spam_signals GROUP BY 1 ORDER BY 2 DESC")
    top_spam = db.fetchall("SELECT d.page_id, d.url, d.title, d.spam_score FROM indexed_documents d WHERE d.spam_score >= 0.5 "
                           "ORDER BY d.spam_score DESC LIMIT 20")
    return {"searches_7d": q["searches"], "zero_result_rate": round(q["zero_results"] / q["searches"], 4) if q["searches"] else None,
            "spam_signals": _plain(spam), "top_spam": _plain(top_spam)}


# ============================ الزاحف ============================
@router.get("/crawler/status")
async def crawler_status(request: Request, ctx: AdminCtx = require("crawler.view")):
    r = rconn.get()
    progress = db.fetchone("""
        SELECT count(*) FILTER (WHERE status = 'pending' AND kind IN ('crawl', 'sitemap', 'image')) AS pending,
               count(*) FILTER (WHERE status = 'running') AS running,
               count(*) FILTER (WHERE status = 'done' AND finished_at > now() - interval '24 hours') AS done_24h,
               count(*) FILTER (WHERE status = 'failed') AS failed
        FROM crawl_jobs""")
    robots = db.fetchone("""
        SELECT count(*) FILTER (WHERE event = 'robots_blocked') AS blocked_by_robots,
               count(*) FILTER (WHERE event = 'robots_unreachable') AS robots_unreachable,
               count(*) FILTER (WHERE event = 'fetched') AS fetched,
               count(*) FILTER (WHERE event = 'ssrf_blocked') AS ssrf_blocked
        FROM crawl_logs WHERE ts > now() - interval '7 days'""")
    hourly = db.fetchall("SELECT date_trunc('hour', ts) AS hour, count(*) FILTER (WHERE event = 'fetched') AS fetched, "
                         "count(*) FILTER (WHERE level = 'error') AS errors FROM crawl_logs "
                         "WHERE ts > now() - interval '24 hours' GROUP BY 1 ORDER BY 1")
    return {"state": await r.get("crawler:state") or db.get_setting("crawler.state"),
            "concurrency": int(await r.get("crawler:concurrency") or db.get_setting("crawler.concurrency", 8)),
            "workers": await metrics.workers(r), "progress": dict(progress), "robots": dict(robots), "hourly": _plain(hourly),
            "follow_external": db.get_setting("crawler.follow_external", False),
            "default_depth": db.get_setting("crawler.default_depth", 3),
            "discovery_mode": db.get_setting("crawler.discovery_mode", "iraq"),
            "new_domain_budget": db.get_setting("crawler.new_domain_budget", 200),
            "max_pending_per_domain": db.get_setting("crawler.max_pending_per_domain", 500),
            "discovery": dict(db.fetchone(
                "SELECT count(*) AS domains_total, count(*) FILTER (WHERE first_seen_at > now() - interval '24 hours') AS discovered_24h, "
                "count(*) FILTER (WHERE is_iraqi) AS iraqi_total, count(*) FILTER (WHERE page_count > 0) AS crawled_domains "
                "FROM domains"))}


class StateIn(BaseModel):
    state: str = Field(pattern="^(running|paused|stopped)$")


@router.post("/crawler/state")
async def crawler_state(body: StateIn, request: Request, ctx: AdminCtx = require("crawler.control")):
    db.set_setting("crawler.state", body.state, ctx.id)
    await rconn.get().set("crawler:state", body.state)
    audit(ctx, "crawler_state", body.state)
    return {"state": body.state}


class CrawlerCfgIn(BaseModel):
    concurrency: int | None = Field(None, ge=1, le=256)
    follow_external: bool | None = None
    default_depth: int | None = Field(None, ge=0, le=20)
    discovery_mode: str | None = Field(None, pattern="^(iraq|open)$")
    new_domain_budget: int | None = Field(None, ge=1, le=1_000_000)
    max_pending_per_domain: int | None = Field(None, ge=10, le=100_000)


@router.put("/crawler/config")
async def crawler_config(body: CrawlerCfgIn, request: Request, ctx: AdminCtx = require("crawler.manage")):
    if body.concurrency is not None:
        db.set_setting("crawler.concurrency", body.concurrency, ctx.id)
        await rconn.get().set("crawler:concurrency", body.concurrency)
    if body.follow_external is not None:
        db.set_setting("crawler.follow_external", body.follow_external, ctx.id)
    if body.default_depth is not None:
        db.set_setting("crawler.default_depth", body.default_depth, ctx.id)
    for k in ("discovery_mode", "new_domain_budget", "max_pending_per_domain"):
        v = getattr(body, k)
        if v is not None:
            db.set_setting(f"crawler.{k}", v, ctx.id)
    audit(ctx, "crawler_config", details=body.model_dump(exclude_none=True))
    return {"ok": True}


@router.get("/crawler/seeds")
def seeds(ctx: AdminCtx = require("crawler.view")):
    return _plain(db.fetchall("SELECT s.id, s.url, s.added_at, d.host, d.page_count FROM seed_urls s "
                              "LEFT JOIN domains d ON d.id = s.domain_id ORDER BY s.added_at DESC"))


class SeedIn(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


@router.post("/crawler/seeds")
def add_seed(body: SeedIn, ctx: AdminCtx = require("crawler.manage")):
    try:
        with db.pool().connection() as c:
            res = crawler.add_seed(c, body.url, ctx.id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    audit(ctx, "seed_added", res["url"])
    return res


@router.delete("/crawler/seeds/{seed_id}")
def delete_seed(seed_id: int, ctx: AdminCtx = require("crawler.manage")):
    row = db.fetchone("DELETE FROM seed_urls WHERE id = %s RETURNING url", (seed_id,))
    if not row:
        raise HTTPException(404)
    audit(ctx, "seed_removed", row["url"])
    return {"ok": True}


@router.get("/domains")
def domains(q: str = "", status: str = "", iraqi: bool | None = None, page: int = 1, ctx: AdminCtx = require("crawler.view")):
    rows = db.fetchall(
        "SELECT id, host, is_iraqi, status, block_reason, category, reputation, authority, crawl_depth, crawl_frequency_h, "
        "min_delay_ms, max_pages, budget_auto, render_js, excluded_paths, page_count, error_count, robots_crawl_delay, last_crawled_at, first_seen_at, "
        "count(*) OVER () AS total FROM domains WHERE (%s = '' OR host ILIKE %s) AND (%s = '' OR status = %s) "
        "AND (%s::bool IS NULL OR is_iraqi = %s) ORDER BY page_count DESC, host LIMIT %s OFFSET %s",
        (q, f"%{q}%", status, status, iraqi, iraqi, PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


class DomainPatch(BaseModel):
    status: str | None = Field(None, pattern="^(active|paused|blocked)$")
    block_reason: str | None = Field(None, max_length=300)
    category: str | None = Field(None, max_length=30)
    crawl_depth: int | None = Field(None, ge=0, le=20)
    crawl_frequency_h: int | None = Field(None, ge=1, le=8760)
    min_delay_ms: int | None = Field(None, ge=100, le=600000)
    max_pages: int | None = Field(None, ge=1, le=10_000_000)
    render_js: bool | None = None
    excluded_paths: list[str] | None = Field(None, max_length=200)


@router.patch("/domains/{domain_id}")
def patch_domain(domain_id: int, body: DomainPatch, ctx: AdminCtx = require("crawler.manage")):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(422, "لا توجد تغييرات")
    if "max_pages" in data:
        data["budget_auto"] = False      # ميزانية يدوية لا تتغير تلقائياً مع السلطة
    if "excluded_paths" in data:
        data["excluded_paths"] = [p if p.startswith("/") else "/" + p for p in data["excluded_paths"] if p.strip()]
    cols = ", ".join(f"{k} = %({k})s" for k in data)
    row = db.fetchone(f"UPDATE domains SET {cols} WHERE id = %(id)s RETURNING host", {**data, "id": domain_id})
    if not row:
        raise HTTPException(404)
    if data.get("status") == "blocked":
        db.execute("UPDATE crawl_jobs SET status = 'cancelled', finished_at = now() WHERE domain_id = %s AND status = 'pending'",
                   (domain_id,))
    audit(ctx, "domain_updated", row["host"], data)
    return {"ok": True}


@router.get("/crawler/jobs")
def jobs(status: str = "", kind: str = "", page: int = 1, ctx: AdminCtx = require("crawler.view")):
    rows = db.fetchall(
        "SELECT id, kind, url, domain_id, depth, priority, status, attempts, max_attempts, left(error, 400) AS error, worker, "
        "created_at, scheduled_at, started_at, finished_at, count(*) OVER () AS total FROM crawl_jobs "
        "WHERE (%s = '' OR status = %s) AND (%s = '' OR kind = %s) ORDER BY id DESC LIMIT %s OFFSET %s",
        (status, status, kind, kind, PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


class IdsIn(BaseModel):
    ids: list[int] | None = None
    all_failed: bool = False


@router.post("/crawler/jobs/retry")
def retry_jobs(body: IdsIn, ctx: AdminCtx = require("crawler.control")):
    if body.all_failed:
        n = db.fetchone("WITH u AS (UPDATE crawl_jobs SET status = 'pending', attempts = 0, error = NULL, scheduled_at = now() "
                        "WHERE status = 'failed' RETURNING 1) SELECT count(*) AS n FROM u")["n"]
    else:
        n = db.fetchone("WITH u AS (UPDATE crawl_jobs SET status = 'pending', attempts = 0, error = NULL, scheduled_at = now() "
                        "WHERE id = ANY(%s) AND status IN ('failed', 'cancelled') RETURNING 1) SELECT count(*) AS n FROM u",
                        (body.ids or [],))["n"]
    audit(ctx, "jobs_retried", details={"count": n})
    return {"retried": n}


@router.post("/crawler/jobs/cancel")
def cancel_jobs(body: IdsIn, ctx: AdminCtx = require("crawler.control")):
    n = db.fetchone("WITH u AS (UPDATE crawl_jobs SET status = 'cancelled', finished_at = now() WHERE id = ANY(%s) "
                    "AND status = 'pending' RETURNING 1) SELECT count(*) AS n FROM u", (body.ids or [],))["n"]
    audit(ctx, "jobs_cancelled", details={"count": n})
    return {"cancelled": n}


@router.get("/crawler/logs")
def crawl_logs(event: str = "", level: str = "", page: int = 1, ctx: AdminCtx = require("crawler.view")):
    rows = db.fetchall(
        "SELECT l.id, l.ts, l.level, l.event, l.url, d.host, l.http_status, l.duration_ms, l.message, count(*) OVER () AS total "
        "FROM crawl_logs l LEFT JOIN domains d ON d.id = l.domain_id WHERE (%s = '' OR l.event = %s) AND (%s = '' OR l.level = %s) "
        "ORDER BY l.id DESC LIMIT %s OFFSET %s", (event, event, level, level, PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


# ============================ الفهرس ============================
@router.get("/index/documents")
def documents(q: str = "", domain: str = "", lang: str = "", page: int = 1, ctx: AdminCtx = require("index.view")):
    rows = db.fetchall(
        "SELECT d.page_id, d.url, d.title, d.lang, d.category, d.doc_type, d.word_count, d.quality, d.spam_score, d.is_adult, "
        "d.duplicate_of, d.indexed_at, d.analyzer_version, dm.host, count(*) OVER () AS total FROM indexed_documents d "
        "JOIN domains dm ON dm.id = d.domain_id WHERE (%s = '' OR d.title ILIKE %s OR d.url ILIKE %s) "
        "AND (%s = '' OR dm.host = %s) AND (%s = '' OR d.lang = %s) ORDER BY d.indexed_at DESC LIMIT %s OFFSET %s",
        (q, f"%{q}%", f"%{q}%", domain, domain, lang, lang, PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


@router.get("/index/documents/{page_id}")
def document(page_id: int, ctx: AdminCtx = require("index.view")):
    d = db.fetchone("SELECT d.page_id, d.url, d.title, d.description, d.headings, left(d.body, 3000) AS body_preview, d.lang, "
                    "d.category, d.doc_type, d.word_count, d.quality, d.spam_score, d.is_adult, d.duplicate_of, d.indexed_at, "
                    "d.analyzer_version, d.index_version_id, p.http_status, p.status AS crawl_status, p.crawl_count, "
                    "p.last_crawled_at, p.canonical_url, m.meta FROM indexed_documents d JOIN crawled_pages p ON p.id = d.page_id "
                    "LEFT JOIN document_metadata m ON m.page_id = d.page_id WHERE d.page_id = %s", (page_id,))
    if not d:
        raise HTTPException(404)
    spam = db.fetchall("SELECT signal, score, details FROM spam_signals WHERE page_id = %s", (page_id,))
    return {"document": _plain(d), "spam_signals": _plain(spam)}


@router.delete("/index/documents/{page_id}")
def delete_document(page_id: int, ctx: AdminCtx = require("index.manage")):
    row = db.fetchone("DELETE FROM indexed_documents WHERE page_id = %s RETURNING url", (page_id,))
    if not row:
        raise HTTPException(404)
    audit(ctx, "document_deleted", row["url"])
    return {"ok": True}


class DomainIdIn(BaseModel):
    domain_id: int


@router.post("/index/reindex-domain")
def reindex_domain(body: DomainIdIn, ctx: AdminCtx = require("index.manage")):
    dom = db.fetchone("SELECT host FROM domains WHERE id = %s", (body.domain_id,))
    if not dom:
        raise HTTPException(404)
    with db.pool().connection() as c:
        jid = crawler.enqueue(c, "reindex_domain", None, domain_id=body.domain_id, priority=5, created_by=ctx.id)
    audit(ctx, "reindex_domain", dom["host"])
    return {"job_id": jid}


class DaysIn(BaseModel):
    days: int = Field(180, ge=1, le=3650)


@router.post("/index/delete-outdated")
def delete_outdated(body: DaysIn, ctx: AdminCtx = require("index.manage")):
    with db.pool().connection() as c:
        jid = crawler.enqueue(c, "delete_outdated", None, priority=5, payload={"days": body.days}, created_by=ctx.id)
    audit(ctx, "delete_outdated", details={"days": body.days})
    return {"job_id": jid}


@router.post("/index/rebuild")
def rebuild(ctx: AdminCtx = require("index.manage")):
    if db.fetchone("SELECT 1 FROM crawl_jobs WHERE kind = 'rebuild_index' AND status IN ('pending', 'running')"):
        raise HTTPException(409, "rebuild_in_progress")
    with db.pool().connection() as c:
        jid = crawler.enqueue(c, "rebuild_index", None, priority=1, created_by=ctx.id)
    audit(ctx, "index_rebuild")
    return {"job_id": jid}


@router.post("/index/maintenance/{task}")
def maintenance(task: str, ctx: AdminCtx = require("index.manage")):
    if task not in ("refresh_terms", "compute_authority"):
        raise HTTPException(404)
    with db.pool().connection() as c:
        jid = crawler.enqueue(c, task, None, priority=5, created_by=ctx.id)
    audit(ctx, f"index_{task}")
    return {"job_id": jid}


@router.get("/index/duplicates")
def duplicates(page: int = 1, ctx: AdminCtx = require("index.view")):
    rows = db.fetchall("SELECT d.page_id, d.url, d.title, o.url AS original_url, count(*) OVER () AS total FROM indexed_documents d "
                       "JOIN crawled_pages o ON o.id = d.duplicate_of WHERE d.duplicate_of IS NOT NULL ORDER BY d.page_id DESC "
                       "LIMIT %s OFFSET %s", (PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


@router.post("/index/duplicates/purge")
def purge_duplicates(ctx: AdminCtx = require("index.manage")):
    n = db.fetchone("WITH x AS (DELETE FROM indexed_documents WHERE duplicate_of IS NOT NULL RETURNING 1) SELECT count(*) AS n FROM x")["n"]
    audit(ctx, "duplicates_purged", details={"count": n})
    return {"deleted": n}


@router.get("/index/versions")
def versions(ctx: AdminCtx = require("index.view")):
    return _plain(db.fetchall("SELECT * FROM index_versions ORDER BY id DESC"))


@router.get("/index/errors")
def index_errors(page: int = 1, ctx: AdminCtx = require("index.view")):
    rows = db.fetchall("SELECT p.id, p.url, p.status, p.http_status, p.error, p.last_crawled_at, d.host, count(*) OVER () AS total "
                       "FROM crawled_pages p JOIN domains d ON d.id = p.domain_id WHERE p.status IN ('error', 'broken', 'too_large', 'unsupported') "
                       "ORDER BY p.last_crawled_at DESC LIMIT %s OFFSET %s", (PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


@router.get("/index/storage")
def storage(ctx: AdminCtx = require("index.view")):
    return {"database": metrics.database(), "index": metrics.index_health(), "system": metrics.system()}


# ============================ الصور ============================
@router.get("/images/stats")
def images_stats(ctx: AdminCtx = require("images.view")):
    s = db.fetchall("SELECT status, count(*) AS n FROM image_index GROUP BY 1")
    fmt = db.fetchall("SELECT format, count(*) AS n FROM image_index WHERE status = 'ok' GROUP BY 1")
    q = db.fetchone("SELECT count(*) AS n FROM crawl_jobs WHERE kind = 'image' AND status IN ('pending', 'running')")
    return {"by_status": _plain(s), "by_format": _plain(fmt), "queue": q["n"],
            "thumbs_dir": str(settings.data_dir / "thumbs")}


@router.get("/images")
def images_list(status: str = "", page: int = 1, ctx: AdminCtx = require("images.view")):
    rows = db.fetchall("SELECT i.id, i.image_url, i.alt, i.width, i.height, i.format, i.bytes, i.status, i.error, i.duplicate_of, "
                       "i.is_adult, i.fetched_at, d.host, count(*) OVER () AS total FROM image_index i LEFT JOIN domains d ON d.id = i.domain_id "
                       "WHERE (%s = '' OR i.status = %s) ORDER BY i.id DESC LIMIT %s OFFSET %s", (status, status, PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


@router.post("/images/retry-failed")
def images_retry(ctx: AdminCtx = require("images.manage")):
    rows = db.fetchall("UPDATE image_index SET status = 'pending', error = NULL WHERE status = 'failed' RETURNING image_url, domain_id, page_id")
    with db.pool().connection() as c:
        for r in rows:
            crawler.enqueue(c, "image", r["image_url"], domain_id=r["domain_id"], priority=200, page_id=r["page_id"])
    audit(ctx, "images_retry", details={"count": len(rows)})
    return {"retried": len(rows)}


@router.post("/images/duplicates/purge")
def images_purge(ctx: AdminCtx = require("images.manage")):
    rows = db.fetchall("DELETE FROM image_index WHERE status = 'duplicate' RETURNING thumb_path")
    for r in rows:
        if r["thumb_path"]:
            (settings.data_dir / "thumbs" / r["thumb_path"]).unlink(missing_ok=True)
    audit(ctx, "images_duplicates_purged", details={"count": len(rows)})
    return {"deleted": len(rows)}


# ============================ الذكاء الاصطناعي ============================
@router.get("/ai/status")
def ai_status(ctx: AdminCtx = require("ai.view")):
    return {"services": ai.status(), "resources": ai.resources(), "models_dir": str(settings.models_dir)}


@router.post("/ai/{key}/load")
def ai_load(key: str, ctx: AdminCtx = require("ai.manage")):
    loaders = {"speech": ai._whisper, "translation": ai._translator}
    if key not in loaders:
        raise HTTPException(404)
    try:
        loaders[key]()
    except ai.ServiceUnavailable as e:
        raise HTTPException(503, str(e))
    audit(ctx, "ai_model_loaded", key)
    return {"ok": True}


@router.post("/ai/{key}/unload")
def ai_unload(key: str, ctx: AdminCtx = require("ai.manage")):
    ai._loaded.pop(key, None)
    audit(ctx, "ai_model_unloaded", key)
    return {"ok": True}


# ============================ الخصوصية والأمن ============================
SECURITY_KEYS = ("retention.crawl_logs_days", "retention.security_events_days", "retention.audit_logs_days",
                 "retention.ops_metrics_days", "retention.temp_files_minutes", "ratelimit.search_per_minute",
                 "ratelimit.upload_per_minute", "ratelimit.admin_login_per_15m", "security.require_2fa")


@router.get("/security/settings")
def security_settings(ctx: AdminCtx = require("security.view")):
    out = {k: db.get_setting(k) for k in SECURITY_KEYS}
    out["privacy_guarantees"] = {
        "search_queries_stored": False, "visitor_ip_stored": False, "cookies_for_visitors": False,
        "third_party_requests": False, "uploads_written_to_disk": False, "audio_retained": False}
    out["backup_encryption"] = backup.encryption_status()
    return out


@router.put("/security/settings")
def update_security(body: SettingsIn, ctx: AdminCtx = require("security.manage")):
    for k, v in body.values.items():
        if k not in SECURITY_KEYS:
            raise HTTPException(422, f"مفتاح غير مسموح: {k}")
        if k == "security.require_2fa":
            if not isinstance(v, bool):
                raise HTTPException(422, k)
        elif not isinstance(v, int) or not 1 <= v <= 100000:
            raise HTTPException(422, f"{k}: رقم صحيح موجب")
    for k, v in body.values.items():
        db.set_setting(k, v, ctx.id)
    audit(ctx, "security_settings_updated", details=body.values)
    return {"ok": True}


@router.post("/security/cleanup")
def cleanup(ctx: AdminCtx = require("security.manage")):
    n = privacy.cleanup_temp()
    crawler.apply_retention()
    audit(ctx, "cleanup_run", details={"temp_files": n})
    return {"temp_files_deleted": n}


@router.get("/security/events")
def security_events(page: int = 1, ctx: AdminCtx = require("security.view")):
    rows = db.fetchall("SELECT id, ts, kind, severity, details, count(*) OVER () AS total FROM security_events "
                       "ORDER BY id DESC LIMIT %s OFFSET %s", (PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


@router.get("/security/sessions")
def sessions(ctx: AdminCtx = require("security.view")):
    rows = db.fetchall("SELECT encode(s.token_hash, 'hex') AS id, s.user_id, u.email, s.ip, s.user_agent, s.created_at, "
                       "s.last_seen_at, s.expires_at, s.mfa_passed FROM admin_sessions s JOIN admin_users u ON u.id = s.user_id "
                       "WHERE s.revoked_at IS NULL AND s.expires_at > now() ORDER BY s.last_seen_at DESC")
    return _plain(rows)


@router.delete("/security/sessions/{sid}")
def revoke_session(sid: str, ctx: AdminCtx = require("security.manage")):
    row = db.fetchone("UPDATE admin_sessions SET revoked_at = now() WHERE token_hash = decode(%s, 'hex') AND revoked_at IS NULL "
                      "RETURNING user_id", (sid,))
    if not row:
        raise HTTPException(404)
    audit(ctx, "session_revoked", str(row["user_id"]))
    return {"ok": True}


@router.get("/audit")
def audit_logs(action: str = "", admin: str = "", page: int = 1, ctx: AdminCtx = require("audit.view")):
    rows = db.fetchall("SELECT id, ts, admin_id, admin_email, action, target, details, ip, success, count(*) OVER () AS total "
                       "FROM audit_logs WHERE (%s = '' OR action = %s) AND (%s = '' OR admin_email ILIKE %s) "
                       "ORDER BY id DESC LIMIT %s OFFSET %s", (action, action, admin, f"%{admin}%", PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


@router.get("/security/access-history")
def access_history(page: int = 1, ctx: AdminCtx = require("security.view")):
    rows = db.fetchall("SELECT id, ts, admin_email, action, ip, success, count(*) OVER () AS total FROM audit_logs "
                       "WHERE action IN ('login', 'login_failed', 'logout', 'mfa_passed', 'mfa_failed') "
                       "ORDER BY id DESC LIMIT %s OFFSET %s", (PAGE, _page(page)))
    return {"total": rows[0]["total"] if rows else 0, "rows": _plain(rows)}


# ============================ التحليلات المجمّعة ============================
@router.get("/analytics")
def analytics(hours: int = 48, ctx: AdminCtx = require("analytics.view")):
    hours = max(1, min(hours, 24 * 90))
    series = db.fetchall(
        "SELECT hour, sum(value) FILTER (WHERE metric = 'searches') AS searches, sum(value) FILTER (WHERE metric = 'errors') AS errors, "
        "sum(value) FILTER (WHERE metric = 'zero_results') AS zero_results, sum(value) FILTER (WHERE metric = 'latency_ms_sum') AS latency_sum "
        "FROM ops_metrics_hourly WHERE hour > now() - make_interval(hours => %s) GROUP BY hour ORDER BY hour", (hours,))
    dist = db.fetchall("SELECT metric, dim, sum(value) AS n FROM ops_metrics_hourly WHERE metric IN ('lang', 'category', 'rate_limited') "
                       "AND hour > now() - make_interval(hours => %s) GROUP BY 1, 2 ORDER BY 3 DESC", (hours,))
    coverage = db.fetchall("SELECT category, lang, count(*) AS n FROM indexed_documents WHERE duplicate_of IS NULL GROUP BY 1, 2")
    iraqi = db.fetchone("SELECT count(*) FILTER (WHERE dm.is_iraqi) AS iraqi, count(*) AS total FROM indexed_documents d "
                        "JOIN domains dm ON dm.id = d.domain_id WHERE d.duplicate_of IS NULL")
    crawl = db.fetchall("SELECT date_trunc('hour', ts) AS hour, count(*) FILTER (WHERE event = 'fetched') AS fetched, "
                        "count(*) FILTER (WHERE level = 'error') AS errors, avg(duration_ms) FILTER (WHERE event = 'fetched') AS avg_ms "
                        "FROM crawl_logs WHERE ts > now() - make_interval(hours => %s) GROUP BY 1 ORDER BY 1", (hours,))
    out = []
    for r in series:
        d = _plain(r)
        d["avg_latency_ms"] = round(r["latency_sum"] / r["searches"], 1) if r["searches"] else None
        out.append(d)
    return {"series": out, "distribution": _plain(dist), "coverage": _plain(coverage), "iraqi_share": dict(iraqi),
            "crawler": _plain(crawl), "note": "تحليلات مجمّعة فقط: لا استعلامات، لا IP، لا جلسات مستخدمين"}


@router.post("/analytics/flush")
async def flush(request: Request, ctx: AdminCtx = require("analytics.view")):
    await privacy.flush_metrics(rconn.get())
    return {"ok": True}


# ============================ المشرفون ============================
@router.get("/admins")
def admins(ctx: AdminCtx = require("admins.view")):
    return _plain(db.fetchall(
        "SELECT u.id, u.email, u.name, u.status, u.totp_enabled, u.created_at, u.last_login_at, u.locked_until, r.name AS role, "
        "(SELECT count(*) FROM admin_sessions s WHERE s.user_id = u.id AND s.revoked_at IS NULL AND s.expires_at > now()) AS active_sessions "
        "FROM admin_users u JOIN admin_roles r ON r.id = u.role_id ORDER BY u.id"))


@router.get("/roles")
def roles(ctx: AdminCtx = require("admins.view")):
    return _plain(db.fetchall("SELECT * FROM admin_roles ORDER BY id"))


class AdminIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    role: str


@router.post("/admins")
def create_admin(body: AdminIn, ctx: AdminCtx = require("admins.manage")):
    if body.role == "super_admin" and ctx.user["role"] != "super_admin":
        raise HTTPException(403, "forbidden")
    temp = secrets.token_urlsafe(12) + "A1!"
    try:
        uid = auth.create_admin(body.email, body.name, temp, body.role, ctx.id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(409, "email_exists")
    db.execute("UPDATE admin_users SET must_change_pw = TRUE WHERE id = %s", (uid,))
    audit(ctx, "admin_created", body.email, {"role": body.role})
    return {"id": uid, "temporary_password": temp}


class AdminPatch(BaseModel):
    role: str | None = None
    status: str | None = Field(None, pattern="^(active|suspended)$")


@router.patch("/admins/{uid}")
def patch_admin(uid: int, body: AdminPatch, ctx: AdminCtx = require("admins.manage")):
    if uid == ctx.id:
        raise HTTPException(422, "لا يمكنك تعديل حسابك من هنا")
    target = db.fetchone("SELECT u.*, r.name AS role FROM admin_users u JOIN admin_roles r ON r.id = u.role_id WHERE u.id = %s", (uid,))
    if not target:
        raise HTTPException(404)
    if ctx.user["role"] != "super_admin" and (target["role"] == "super_admin" or body.role == "super_admin"):
        raise HTTPException(403, "forbidden")
    if body.role:
        r = db.fetchone("SELECT id FROM admin_roles WHERE name = %s", (body.role,))
        if not r:
            raise HTTPException(422, "role")
        db.execute("UPDATE admin_users SET role_id = %s WHERE id = %s", (r["id"], uid))
    if body.status:
        db.execute("UPDATE admin_users SET status = %s WHERE id = %s", (body.status, uid))
        if body.status == "suspended":
            db.execute("UPDATE admin_sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL", (uid,))
    audit(ctx, "admin_updated", target["email"], body.model_dump(exclude_none=True))
    return {"ok": True}


@router.post("/admins/{uid}/revoke-sessions")
def revoke_all(uid: int, ctx: AdminCtx = require("admins.manage")):
    n = db.fetchone("WITH x AS (UPDATE admin_sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL RETURNING 1) "
                    "SELECT count(*) AS n FROM x", (uid,))["n"]
    audit(ctx, "admin_sessions_revoked", str(uid), {"count": n})
    return {"revoked": n}


@router.post("/admins/{uid}/reset-2fa")
def reset_2fa(uid: int, ctx: AdminCtx = require("admins.manage")):
    db.execute("UPDATE admin_users SET totp_enabled = FALSE, totp_secret_enc = NULL WHERE id = %s", (uid,))
    db.execute("UPDATE admin_sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL", (uid,))
    audit(ctx, "admin_2fa_reset", str(uid))
    return {"ok": True}


class RoleIn(BaseModel):
    permissions: list[str]


ALL_PERMS = sorted(set(db_p for r in [
    "dashboard.view search.view search.manage search.test crawler.view crawler.control crawler.manage index.view index.manage "
    "images.view images.manage ai.view ai.manage security.view security.manage audit.view analytics.view admins.view "
    "admins.manage infra.view infra.control settings.view settings.manage"] for db_p in r.split()))


@router.get("/permissions")
def permissions(ctx: AdminCtx = require("admins.view")):
    return ALL_PERMS


@router.put("/roles/{role_id}")
def update_role(role_id: int, body: RoleIn, ctx: AdminCtx = require("admins.manage")):
    if ctx.user["role"] != "super_admin":
        raise HTTPException(403, "forbidden")
    role = db.fetchone("SELECT name FROM admin_roles WHERE id = %s", (role_id,))
    if not role:
        raise HTTPException(404)
    if role["name"] == "super_admin":
        raise HTTPException(422, "دور المشرف الأعلى ثابت")
    bad = set(body.permissions) - set(ALL_PERMS)
    if bad:
        raise HTTPException(422, f"صلاحيات غير معروفة: {sorted(bad)}")
    db.execute("UPDATE admin_roles SET permissions = %s WHERE id = %s", (sorted(set(body.permissions)), role_id))
    audit(ctx, "role_updated", role["name"], {"permissions": body.permissions})
    return {"ok": True}


# ============================ البنية التحتية ============================
@router.get("/infra")
async def infra(request: Request, ctx: AdminCtx = require("infra.view")):
    r = rconn.get()
    sysm, ov = metrics.system(), metrics.overview()
    redis_h, db_h, idx_h = await metrics.redis_health(r), metrics.database(), metrics.index_health()
    w = await metrics.workers(r)
    bks = db.fetchall("SELECT id, file_name, bytes, sha256, encrypted, status, error, created_at, finished_at FROM backups ORDER BY id DESC LIMIT 20")
    return {"system": sysm, "database": db_h, "redis": redis_h, "index": idx_h, "workers": w, "queues": metrics.queues(),
            "docker": metrics.docker_status(), "backups": _plain(bks), "backup_encryption": backup.encryption_status(),
            "alerts": metrics.alerts(sysm, ov, redis_h, db_h, idx_h, w), "version": settings.version,
            "migrations": _plain(db.migration_status()), "env": settings.env}


class ServiceIn(BaseModel):
    service: str = Field(pattern="^(workers)$")


@router.post("/infra/restart")
async def restart(body: ServiceIn, request: Request, ctx: AdminCtx = require("infra.control")):
    """يرسل إشارة للعمّال لإعادة التشغيل بأمان (ينهون مهامهم ويعيد Docker تشغيلهم)."""
    await rconn.get().set("control:restart_workers", datetime.now(timezone.utc).isoformat(), ex=600)
    audit(ctx, "service_restart", body.service)
    return {"ok": True}


@router.post("/backups")
def create_backup(ctx: AdminCtx = require("infra.control")):
    if not backup.encryption_status()["configured"]:
        raise HTTPException(422, "SUMER_BACKUP_KEY غير مضبوط")
    bid = db.fetchone("INSERT INTO backups (file_name, encrypted, status, created_by) VALUES ('', TRUE, 'running', %s) RETURNING id",
                      (ctx.id,))["id"]
    with db.pool().connection() as c:
        crawler.enqueue(c, "backup", None, priority=1, payload={"backup_id": bid}, created_by=ctx.id)
    audit(ctx, "backup_requested", str(bid))
    return {"backup_id": bid}


# ============================ الإعدادات العامة ============================
SITE_KEYS = ("site.name_ar", "site.name_en", "site.tagline_ar", "site.tagline_en", "site.default_lang", "site.default_theme",
             "site.maintenance", "site.announcement")


@router.get("/settings/site")
def site_settings(ctx: AdminCtx = require("settings.view")):
    return {k: db.get_setting(k) for k in SITE_KEYS + ("site.logo_path",)}


@router.put("/settings/site")
def update_site(body: SettingsIn, ctx: AdminCtx = require("settings.manage")):
    for k, v in body.values.items():
        if k not in SITE_KEYS:
            raise HTTPException(422, f"مفتاح غير مسموح: {k}")
        if k == "site.maintenance" and not isinstance(v, bool):
            raise HTTPException(422, k)
        if k == "site.default_lang" and v not in ("ar", "en", "ckb"):
            raise HTTPException(422, k)
        if k == "site.default_theme" and v not in ("light", "dark", "system"):
            raise HTTPException(422, k)
        if k == "site.announcement" and not (isinstance(v, dict) and isinstance(v.get("enabled"), bool)):
            raise HTTPException(422, k)
        if isinstance(v, str) and len(v) > 300:
            raise HTTPException(422, f"{k}: طويل جداً")
    for k, v in body.values.items():
        db.set_setting(k, v, ctx.id)
    audit(ctx, "site_settings_updated", details=body.values)
    return {"ok": True}


@router.post("/settings/logo")
async def upload_logo(file: UploadFile = File(...), ctx: AdminCtx = require("settings.manage")):
    """الشعار يُعاد ترميزه PNG (لا SVG) لمنع تضمين سكربتات."""
    from PIL import Image
    data = await file.read(2_000_001)
    if len(data) > 2_000_000:
        raise HTTPException(413, "file_too_large")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGBA")
            im.thumbnail((512, 512))
            out = io.BytesIO()
            im.save(out, "PNG")
    except Exception:
        raise HTTPException(422, "invalid_image")
    d = settings.data_dir / "branding"
    d.mkdir(parents=True, exist_ok=True)
    name = f"logo-{secrets.token_hex(4)}.png"
    (d / name).write_bytes(out.getvalue())
    db.set_setting("site.logo_path", name, ctx.id)
    audit(ctx, "logo_updated", name)
    return {"logo": "/api/public/logo"}
