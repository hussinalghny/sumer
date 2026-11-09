"""تطبيق FastAPI. شغّله بدون سجلات وصول: uvicorn sumer.app:app --no-access-log"""

import asyncio
import contextlib
import logging
import time

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import api_admin, api_public, db, privacy, rconn
from .config import settings

# لا نسجّل الطلبات أبداً. الأخطاء تُسجّل بدون مسار الطلب أو جسمه.
logging.getLogger("uvicorn.access").disabled = True

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "interest-cohort=(), browsing-topics=(), geolocation=(), camera=(), microphone=(self)",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


async def _flusher(redis):
    while True:
        await asyncio.sleep(60)
        with contextlib.suppress(Exception):
            await privacy.flush_metrics(redis)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    r = rconn.get()
    await r.set("api:started", time.time(), nx=True)
    task = asyncio.create_task(_flusher(r))
    yield
    task.cancel()
    with contextlib.suppress(Exception):
        await privacy.flush_metrics(r)


app = FastAPI(title="Sumer Search API", version=settings.version, lifespan=lifespan,
              docs_url="/api/docs" if settings.env != "production" else None, redoc_url=None,
              openapi_url="/api/openapi.json" if settings.env != "production" else None)


@app.middleware("http")
async def headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        if k == "Cache-Control" and "cache-control" in response.headers:
            continue
        response.headers.setdefault(k, v)
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation(request: Request, exc: RequestValidationError):
    # لا نعيد قيم المدخلات في الخطأ (قد تكون نص بحث)
    return JSONResponse({"detail": "invalid_request", "fields": [".".join(map(str, e["loc"])) for e in exc.errors()]}, 422)


app.include_router(api_public.router)
app.include_router(api_admin.router)
