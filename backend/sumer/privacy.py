"""أدوات الخصوصية: تحديد معدل بدون تخزين IP، تحليلات مجمّعة بدون استعلامات، وتنظيف الملفات المؤقتة."""

import hashlib
import hmac
import time
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .config import settings


def temp_dir() -> Path:
    p = settings.data_dir / "tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cleanup_temp() -> int:
    minutes = int(db.get_setting("retention.temp_files_minutes", 10))
    cutoff = time.time() - minutes * 60
    n = 0
    for f in temp_dir().iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                n += 1
        except FileNotFoundError:
            pass
    return n


def client_fingerprint(ip: str) -> str:
    """بصمة مؤقتة: HMAC(مفتاح التطبيق + الساعة الحالية, IP). تتغير كل ساعة ولا يمكن عكسها إلى IP."""
    hour = int(time.time() // 3600)
    return hmac.new(settings.secret_bytes + str(hour).encode(), ip.encode(), hashlib.sha256).hexdigest()[:24]


async def allow(redis, bucket: str, ip: str, limit: int, window_s: int = 60) -> bool:
    key = f"rl:{bucket}:{client_fingerprint(ip)}:{int(time.time() // window_s)}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, window_s + 5)
    return n <= limit


async def count(redis, metric: str, dim: str = "", value: int = 1):
    """عدّاد ساعي مجمّع في Redis، يُفرّغ إلى PostgreSQL دورياً. لا يحمل أي نص بحث أو هوية."""
    hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    key = f"ops:{hour}"
    await redis.hincrby(key, f"{metric}|{dim}", value)
    await redis.expire(key, 3 * 86400)


async def flush_metrics(redis):
    now_hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    async for key in redis.scan_iter("ops:*"):
        hour = key.split(":", 1)[1]
        data = await redis.hgetall(key)
        rows = []
        for field, val in data.items():
            metric, dim = field.split("|", 1)
            rows.append((hour + ":00:00+00", metric, dim, int(val)))
        with db.pool().connection() as conn:
            for r in rows:
                conn.execute("INSERT INTO ops_metrics_hourly (hour, metric, dim, value) VALUES (%s, %s, %s, %s) "
                             "ON CONFLICT (hour, metric, dim) DO UPDATE SET value = EXCLUDED.value", r)
        if hour < now_hour:
            await redis.delete(key)
