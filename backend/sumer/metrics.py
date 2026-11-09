"""مقاييس النظام الحقيقية: من PostgreSQL وRedis وpsutil. لا أرقام ثابتة."""

import os
import shutil
import socket
import subprocess
import time

import psutil

from . import db
from .config import settings

_net_prev = {"t": time.time(), "io": psutil.net_io_counters()}


def overview() -> dict:
    row = db.fetchone("""
        SELECT
          (SELECT count(*) FROM indexed_documents WHERE duplicate_of IS NULL) AS indexed_pages,
          (SELECT count(*) FROM domains WHERE page_count > 0) AS indexed_sites,
          (SELECT count(*) FROM domains WHERE is_iraqi AND page_count > 0) AS iraqi_domains,
          (SELECT count(*) FROM domains) AS known_domains,
          (SELECT count(*) FROM crawled_pages WHERE last_crawled_at >= date_trunc('day', now())) AS crawled_today,
          (SELECT count(*) FROM indexed_documents WHERE indexed_at >= date_trunc('day', now())) AS indexed_today,
          (SELECT count(*) FROM crawl_jobs WHERE status = 'pending') AS pending_jobs,
          (SELECT count(*) FROM crawl_jobs WHERE status = 'running') AS running_jobs,
          (SELECT count(*) FROM crawl_jobs WHERE status = 'failed') AS failed_jobs,
          (SELECT count(*) FROM image_index WHERE status = 'ok') AS indexed_images,
          (SELECT count(*) FROM indexed_documents WHERE doc_type = 'pdf') AS indexed_documents,
          (SELECT count(*) FROM indexed_documents WHERE duplicate_of IS NOT NULL) AS duplicates
    """)
    perf = db.fetchone("""
        SELECT COALESCE(sum(value) FILTER (WHERE metric = 'searches'), 0) AS searches,
               COALESCE(sum(value) FILTER (WHERE metric = 'latency_ms_sum'), 0) AS latency_sum,
               COALESCE(sum(value) FILTER (WHERE metric = 'errors'), 0) AS errors
        FROM ops_metrics_hourly WHERE hour > now() - interval '24 hours'""")
    out = dict(row)
    out["searches_24h"] = perf["searches"]
    out["avg_response_ms"] = round(perf["latency_sum"] / perf["searches"], 1) if perf["searches"] else None
    out["error_rate_24h"] = round(perf["errors"] / perf["searches"], 4) if perf["searches"] else None
    return out


def system() -> dict:
    now = time.time()
    io = psutil.net_io_counters()
    dt = max(now - _net_prev["t"], 1e-3)
    rx = (io.bytes_recv - _net_prev["io"].bytes_recv) / dt
    tx = (io.bytes_sent - _net_prev["io"].bytes_sent) / dt
    _net_prev.update(t=now, io=io)
    vm = psutil.virtual_memory()
    du = shutil.disk_usage(settings.data_dir if settings.data_dir.exists() else "/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2), "cpu_count": psutil.cpu_count(),
        "load_avg": [round(x, 2) for x in os.getloadavg()],
        "ram_used_mb": round(vm.used / 2**20), "ram_total_mb": round(vm.total / 2**20), "ram_percent": vm.percent,
        "disk_used_gb": round(du.used / 2**30, 1), "disk_total_gb": round(du.total / 2**30, 1),
        "disk_percent": round(du.used / du.total * 100, 1),
        "net_rx_kbps": round(rx / 1024, 1), "net_tx_kbps": round(tx / 1024, 1),
        "host": socket.gethostname(), "boot_time": psutil.boot_time(),
    }


def database() -> dict:
    try:
        r = db.fetchone("SELECT version() AS v, pg_database_size(current_database()) AS size, "
                        "(SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) AS connections")
        sizes = db.fetchall(
            "SELECT relname AS table, pg_total_relation_size(c.oid) AS bytes FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r' "
            "ORDER BY 2 DESC LIMIT 12")
        return {"ok": True, "version": r["v"].split(",")[0], "size_mb": round(r["size"] / 2**20, 1),
                "connections": r["connections"], "tables": [dict(x) for x in sizes]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def redis_health(redis) -> dict:
    try:
        t0 = time.perf_counter()
        await redis.ping()
        info = await redis.info()
        return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 2), "version": info.get("redis_version"),
                "used_memory_mb": round(info.get("used_memory", 0) / 2**20, 1), "clients": info.get("connected_clients"),
                "uptime_s": info.get("uptime_in_seconds")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def index_health() -> dict:
    try:
        v = db.fetchone("SELECT id, label, analyzer_version, doc_count, activated_at FROM index_versions WHERE status = 'active'")
        t0 = time.perf_counter()
        db.fetchone("SELECT count(*) FROM indexed_documents WHERE tsv @@ to_tsquery('simple', 'test') ")
        probe = round((time.perf_counter() - t0) * 1000, 1)
        idx = db.fetchone("SELECT pg_relation_size('indexed_documents_tsv_idx') AS gin, "
                          "pg_total_relation_size('indexed_documents') AS total")
        stale = db.fetchone("SELECT count(*) AS n FROM indexed_documents WHERE analyzer_version <> %s",
                            (__import__("sumer.text", fromlist=["x"]).ANALYZER_VERSION,))
        return {"ok": v is not None, "active_version": dict(v) if v else None, "probe_ms": probe,
                "gin_index_mb": round(idx["gin"] / 2**20, 1), "total_mb": round(idx["total"] / 2**20, 1),
                "docs_needing_rebuild": stale["n"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def workers(redis) -> list[dict]:
    out = []
    for wid in await redis.smembers("workers"):
        h = await redis.hgetall(f"worker:{wid}")
        if not h:
            await redis.srem("workers", wid)
            continue
        h["alive"] = time.time() - int(h.get("seen", 0)) < 30
        out.append(h)
    return out


def queues() -> list[dict]:
    rows = db.fetchall("SELECT kind, status, count(*) AS n, min(scheduled_at) FILTER (WHERE status = 'pending') AS oldest "
                       "FROM crawl_jobs GROUP BY 1, 2 ORDER BY 1, 2")
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()} for r in rows]


def docker_status() -> dict:
    sock = "/var/run/docker.sock"
    if not os.path.exists(sock) or not shutil.which("docker"):
        return {"available": False, "reason": "لا يوجد وصول لـ Docker من هذا الخادم (اربط /var/run/docker.sock للقراءة لتفعيله)"}
    try:
        out = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Status}}|{{.State}}"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode:
            return {"available": False, "reason": out.stderr.strip()[:300]}
        rows = [dict(zip(("name", "image", "status", "state"), l.split("|"))) for l in out.stdout.strip().splitlines()]
        return {"available": True, "containers": rows}
    except Exception as e:
        return {"available": False, "reason": str(e)}


def alerts(sysm, ov, redis_h, db_h, idx_h, workers_list) -> list[dict]:
    a = []
    if not db_h.get("ok"):
        a.append({"level": "critical", "key": "db_down"})
    if not redis_h.get("ok"):
        a.append({"level": "critical", "key": "redis_down"})
    if not idx_h.get("ok"):
        a.append({"level": "critical", "key": "index_unhealthy"})
    if sysm["disk_percent"] > 85:
        a.append({"level": "high", "key": "disk_high", "value": sysm["disk_percent"]})
    if sysm["ram_percent"] > 90:
        a.append({"level": "high", "key": "ram_high", "value": sysm["ram_percent"]})
    if not any(w.get("alive") for w in workers_list):
        a.append({"level": "medium", "key": "no_workers"})
    if ov["failed_jobs"] > 50:
        a.append({"level": "medium", "key": "failed_jobs", "value": ov["failed_jobs"]})
    if idx_h.get("docs_needing_rebuild"):
        a.append({"level": "low", "key": "index_rebuild_needed", "value": idx_h["docs_needing_rebuild"]})
    return a
