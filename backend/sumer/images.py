"""معالجة الصور: فك الترميز في عملية منفصلة بحدود ذاكرة ووقت (sandbox)،
بصمة dHash للبحث العكسي وكشف المكرر، وصورة مصغّرة محلية حتى لا يتصل متصفح المستخدم بمواقع خارجية.
"""

import asyncio
import io
import json
import os
from concurrent.futures import ProcessPoolExecutor

from . import db
from . import text as T
from .config import settings

_pool: ProcessPoolExecutor | None = None
MAX_PIXELS = 40_000_000


def _limit_resources():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))   # 1GB
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    except Exception:
        pass


def executor() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        import multiprocessing
        _pool = ProcessPoolExecutor(max_workers=2, initializer=_limit_resources,
                                    mp_context=multiprocessing.get_context("spawn"))
    return _pool


def analyze_bytes(data: bytes, thumb: bool = True) -> dict:
    """تعمل داخل العملية المعزولة. لا تكتب على القرص."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    with Image.open(io.BytesIO(data)) as im:
        fmt = (im.format or "").lower()
        if fmt not in ("jpeg", "png", "gif", "webp", "bmp"):
            raise ValueError(f"صيغة غير مدعومة: {fmt}")
        im.seek(0)
        w, h = im.size
        gray = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px = list(gray.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
        dh = bits - (1 << 64) if bits >= 1 << 63 else bits
        out = {"width": w, "height": h, "format": fmt, "dhash": dh, "bytes": len(data)}
        if thumb:
            t = im.convert("RGB")
            t.thumbnail((360, 360))
            buf = io.BytesIO()
            t.save(buf, "WEBP", quality=78)
            out["thumb"] = buf.getvalue()
        return out


def bands(dh: int) -> tuple[int, int, int, int]:
    u = dh & ((1 << 64) - 1)
    return tuple((u >> (16 * i)) & 0xFFFF for i in range(4))


async def analyze(data: bytes, thumb: bool = True) -> dict:
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(loop.run_in_executor(executor(), analyze_bytes, data, thumb), timeout=30)


async def process_image_bytes(image_id: int, data: bytes):
    try:
        info = await analyze(data)
    except Exception as e:
        db.execute("UPDATE image_index SET status = 'failed', error = %s, fetched_at = now() WHERE id = %s",
                   (f"{type(e).__name__}: {e}"[:500], image_id))
        return
    thumbs = settings.data_dir / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    path = thumbs / f"{image_id}.webp"
    path.write_bytes(info["thumb"])
    b = bands(info["dhash"])
    with db.pool().connection() as conn:
        img = conn.execute("SELECT alt, context FROM image_index WHERE id = %s", (image_id,)).fetchone()
        dup = conn.execute("SELECT id FROM image_index WHERE dhash = %s AND id <> %s AND status = 'ok' "
                           "ORDER BY id LIMIT 1", (info["dhash"], image_id)).fetchone()
        adult = False
        if img:
            from .indexer import ADULT_TERMS
            adult = len(set(T.words(img["alt"] + " " + img["context"])) & ADULT_TERMS) >= 1
        conn.execute(
            "UPDATE image_index SET width = %s, height = %s, format = %s, bytes = %s, dhash = %s, band0 = %s, band1 = %s, "
            "band2 = %s, band3 = %s, thumb_path = %s, status = %s, duplicate_of = %s, is_adult = %s, error = NULL, "
            "fetched_at = now(), tsv = to_tsvector('simple', %s) WHERE id = %s",
            (info["width"], info["height"], info["format"], info["bytes"], info["dhash"], *b, path.name,
             "duplicate" if dup else "ok", dup["id"] if dup else None, adult,
             T.analyzed((img["alt"] + " " + img["context"]) if img else ""), image_id))


def similar(dh: int, limit: int = 40, max_distance: int = 12, safe: bool = True) -> list[dict]:
    """بحث عكسي: مرشّحون يشتركون بربع بصمة على الأقل، ثم مسافة هامنغ الدقيقة."""
    b = bands(dh)
    rows = db.fetchall(
        "SELECT i.id, i.image_url, i.width, i.height, i.format, i.alt, i.thumb_path, i.dhash, d.host, p.url AS page_url, "
        "bit_count((i.dhash # %s)::bit(64)) AS distance FROM image_index i "
        "LEFT JOIN domains d ON d.id = i.domain_id LEFT JOIN crawled_pages p ON p.id = i.page_id "
        "WHERE i.status = 'ok' AND (i.band0 = %s OR i.band1 = %s OR i.band2 = %s OR i.band3 = %s) "
        "AND (NOT %s OR NOT i.is_adult) ORDER BY distance LIMIT %s",
        (dh, *b, safe, limit * 3))
    return [dict(r) for r in rows if r["distance"] <= max_distance][:limit]
