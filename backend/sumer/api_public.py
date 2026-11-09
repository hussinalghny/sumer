"""الواجهة العامة للبحث. كل الطلبات POST حتى لا يظهر نص البحث في الروابط أو سجلات الوسطاء."""

import time

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import ai, db, images, metrics, privacy, rconn
from . import search as S
from .config import settings

router = APIRouter(prefix="/api")
MAX_UPLOAD = 8 * 1024 * 1024


class SearchIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)
    page: int = Field(1, ge=1, le=20)
    lang: str | None = Field(None, max_length=5)
    category: str | None = Field(None, max_length=20)
    since_days: int | None = Field(None, ge=1, le=3650)
    safe: str | None = Field(None, pattern="^(strict|moderate|off)$")
    sort: str = Field("relevance", pattern="^(relevance|date)$")


class TextIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)


class ImagesIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)
    page: int = Field(1, ge=1, le=20)
    size: str | None = Field(None, pattern="^(small|medium|large)$")
    format: str | None = Field(None, pattern="^(jpeg|png|gif|webp|bmp)$")
    safe: str | None = Field(None, pattern="^(strict|moderate|off)$")


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source: str | None = Field(None, max_length=5)
    target: str = Field(max_length=5)


class InspectIn(BaseModel):
    url: str = Field(min_length=3, max_length=2000)


async def _limit(request: Request, bucket: str, key: str):
    limit = int(db.get_setting(key, 60))
    if not await privacy.allow(rconn.get(), bucket, _ip(request), limit):
        await privacy.count(rconn.get(), "rate_limited", bucket)
        raise HTTPException(429, "rate_limited")


def _ip(request: Request) -> str:
    if settings.trusted_proxy and request.headers.get("x-real-ip"):
        return request.headers["x-real-ip"]
    return request.client.host if request.client else "0.0.0.0"


def _guard(feature: str = "search.enabled"):
    if db.get_setting("site.maintenance", False):
        raise HTTPException(503, "maintenance")
    if not db.get_setting(feature, True):
        raise HTTPException(503, "disabled")


@router.get("/public/config")
def public_config():
    s = db.get_settings("site.")
    langs = db.fetchall("SELECT code, native_name, direction FROM language_metadata WHERE enabled ORDER BY priority DESC, code")
    ai_state = {x["key"]: x["state"] == "ready" for x in ai.status()}
    return {
        "name_ar": s.get("site.name_ar"), "name_en": s.get("site.name_en"),
        "tagline_ar": s.get("site.tagline_ar"), "tagline_en": s.get("site.tagline_en"),
        "logo": "/api/public/logo" if s.get("site.logo_path") else None,
        "default_lang": s.get("site.default_lang", "ar"), "default_theme": s.get("site.default_theme", "system"),
        "maintenance": s.get("site.maintenance", False), "announcement": s.get("site.announcement"),
        "languages": [dict(l) for l in langs],
        "features": {"images": db.get_setting("search.image_enabled", True), "voice": ai_state["speech"],
                     "translation": ai_state["translation"], "reverse_image": True},
        "safe_default": db.get_setting("search.safe_default", "moderate"),
    }


@router.get("/public/logo")
def logo():
    p = db.get_setting("site.logo_path")
    if not p:
        raise HTTPException(404)
    return FileResponse(settings.data_dir / "branding" / p, headers={"Cache-Control": "public, max-age=3600"})


@router.post("/search")
async def search(body: SearchIn, request: Request):
    _guard()
    await _limit(request, "search", "ratelimit.search_per_minute")
    r = rconn.get()
    t0 = time.perf_counter()
    try:
        safe = body.safe or db.get_setting("search.safe_default", "moderate")
        res = S.search(body.q, body.page, {"lang": body.lang, "category": body.category, "since_days": body.since_days},
                       safe=safe, sort=body.sort)
    except Exception:
        await privacy.count(r, "errors", "search")
        raise
    ms = int((time.perf_counter() - t0) * 1000)
    await privacy.count(r, "searches")
    await privacy.count(r, "latency_ms_sum", "", ms)
    await privacy.count(r, "lang", res.get("lang") or "unknown")
    await privacy.count(r, "category", body.category or "all")
    if not res["total"]:
        await privacy.count(r, "zero_results")
    return res


@router.post("/suggest")
async def suggest(body: TextIn, request: Request):
    _guard()
    await _limit(request, "suggest", "ratelimit.search_per_minute")
    return {"suggestions": S.suggest(body.q)}


@router.post("/images")
async def images_search(body: ImagesIn, request: Request):
    _guard("search.image_enabled")
    await _limit(request, "search", "ratelimit.search_per_minute")
    await privacy.count(rconn.get(), "searches_images")
    res = S.search_images(body.q, body.page, body.size, body.format, body.safe or db.get_setting("search.safe_default", "moderate"))
    for x in res["results"]:
        x["thumb"] = f"/api/images/thumb/{x['id']}"
    return res


@router.get("/images/thumb/{image_id}")
def thumb(image_id: int):
    """الصور المصغّرة تُخدم من خادمنا، فمتصفح المستخدم لا يتصل بمواقع خارجية."""
    row = db.fetchone("SELECT thumb_path FROM image_index WHERE id = %s AND status IN ('ok', 'duplicate')", (image_id,))
    if not row or not row["thumb_path"]:
        raise HTTPException(404)
    path = settings.data_dir / "thumbs" / row["thumb_path"]
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


async def _read_upload(f: UploadFile) -> bytes:
    data = await f.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file_too_large")
    return data


@router.post("/images/reverse")
async def reverse_image(request: Request, file: UploadFile = File(...)):
    """الصورة المرفوعة تعالج بالذاكرة داخل عملية معزولة، ولا تُكتب على القرص أبداً."""
    _guard("search.image_enabled")
    await _limit(request, "upload", "ratelimit.upload_per_minute")
    data = await _read_upload(file)
    try:
        info = await images.analyze(data, thumb=False)
    except Exception:
        raise HTTPException(422, "invalid_image")
    finally:
        del data
    safe = db.get_setting("search.safe_default", "moderate") != "off"
    rows = images.similar(info["dhash"], safe=safe)
    await privacy.count(rconn.get(), "searches_reverse_image")
    return {"query_image": {"width": info["width"], "height": info["height"], "format": info["format"]},
            "results": [{"id": r["id"], "image_url": r["image_url"], "page_url": r["page_url"], "host": r["host"],
                         "width": r["width"], "height": r["height"], "format": r["format"], "alt": r["alt"],
                         "distance": r["distance"], "thumb": f"/api/images/thumb/{r['id']}"} for r in rows]}


@router.post("/inspect")
async def inspect(body: InspectIn, request: Request):
    _guard()
    await _limit(request, "search", "ratelimit.search_per_minute")
    try:
        return S.inspect_url(body.url)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/voice")
async def voice(request: Request, file: UploadFile = File(...), language: str | None = Form(None)):
    _guard()
    await _limit(request, "upload", "ratelimit.upload_per_minute")
    data = await _read_upload(file)
    try:
        return ai.transcribe(data, language)
    except ai.ServiceUnavailable as e:
        raise HTTPException(503, str(e))
    finally:
        del data


@router.post("/translate")
async def translate(body: TranslateIn, request: Request):
    _guard()
    await _limit(request, "translate", "ratelimit.search_per_minute")
    try:
        return ai.translate(body.text, body.source, body.target)
    except ai.ServiceUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/detect-language")
async def detect_language(body: TextIn):
    return ai.detect(body.q)


@router.get("/status")
async def status(request: Request):
    """حالة عامة مختصرة للخدمات، بدون تفاصيل حساسة."""
    r = rconn.get()
    redis_h = await metrics.redis_health(r)
    idx = metrics.index_health()
    workers = await metrics.workers(r)
    ai_s = {x["key"]: x["state"] for x in ai.status()}
    return {"search": "ok" if idx.get("ok") else "down", "index": "ok" if idx.get("ok") else "down",
            "cache": "ok" if redis_h.get("ok") else "down",
            "crawler": "ok" if any(w["alive"] for w in workers) else "idle",
            "voice": ai_s["speech"], "translation": ai_s["translation"],
            "maintenance": db.get_setting("site.maintenance", False), "version": settings.version}
