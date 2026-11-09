"""نتائج احتياطية من الويب العام عبر واجهة بحث مرخّصة (Brave Search API).

تُستخدم فقط عندما يكون فهرس سومر قليل النتائج للاستعلام، وتُعرض بوسم واضح «من الويب العام».
- الطلب يخرج من خادم سومر، فلا يصل عنوان IP المستخدم ولا متصفحه للمزوّد.
- لا يُخزَّن الاستعلام ولا النتائج في أي مكان (لا قاعدة بيانات ولا ذاكرة مؤقتة).
- لا تُضاف هذه النتائج للفهرس المحلي (شروط المزوّد تمنع بناء فهرس من نتائجه).
التفعيل: ضع SUMER_BRAVE_API_KEY في .env. الإيقاف من الإعداد search.web_fallback = false.
"""

import html
import re
from urllib.parse import urlsplit

import httpx

from . import db
from .config import settings

API = "https://api.search.brave.com/res/v1/web/search"
PROVIDER = "Brave Search"
MAX_PAGES = 10  # المزوّد يسمح بإزاحة حتى 9
_TOKEN = re.compile(r"<strong>(.*?)</strong>", re.S)
_TAGS = re.compile(r"<[^>]+>")


def enabled() -> bool:
    return bool(settings.brave_api_key) and bool(db.get_setting("search.web_fallback", True))


def threshold() -> int:
    return int(db.get_setting("search.web_fallback_min", settings.web_fallback_min))


def _clean(s: str) -> str:
    return " ".join(html.unescape(_TAGS.sub("", s or "")).split())


def segs(s: str) -> list[dict]:
    """يحوّل <strong> من المزوّد لمقاطع تمييز آمنة (نص فقط، بلا HTML)."""
    out, pos = [], 0
    s = s or ""
    for m in _TOKEN.finditer(s):
        if m.start() > pos:
            out.append({"t": _clean(s[pos:m.start()]) + " ", "h": False})
        out.append({"t": _clean(m.group(1)) + " ", "h": True})
        pos = m.end()
    if pos < len(s):
        out.append({"t": _clean(s[pos:]), "h": False})
    return [x for x in out if x["t"].strip()]


def parse(data: dict) -> tuple[list[dict], bool]:
    results = []
    for it in (data.get("web") or {}).get("results") or []:
        url = it.get("url") or ""
        if not url.startswith(("https://", "http://")):
            continue
        host = (urlsplit(url).hostname or "").lower()
        title = it.get("title") or url
        results.append({
            "url": url, "title": _clean(title), "host": host, "lang": it.get("language"),
            "category": "web", "doc_type": "html", "indexed_at": None, "published_at": None,
            "title_hl": segs(title) or [{"t": url, "h": False}], "snippet": segs(it.get("description") or ""),
            "iraqi": host.endswith(".iq"), "source": "web",
        })
    more = bool((data.get("query") or {}).get("more_results_available"))
    return results, more


async def search(q: str, page: int, lang: str | None, safe: str) -> tuple[list[dict], bool]:
    if page > MAX_PAGES:
        return [], False
    params = {"q": q[:400], "count": 10, "offset": page - 1, "text_decorations": "true",
              "safesearch": {"off": "off", "strict": "strict"}.get(safe, "moderate")}
    if lang in ("ar", "en"):
        params["search_lang"] = lang
    headers = {"Accept": "application/json", "X-Subscription-Token": settings.brave_api_key,
               "User-Agent": "SumerSearch/1.0"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0), follow_redirects=False) as c:
        r = await c.get(API, params=params, headers=headers)
    r.raise_for_status()
    return parse(r.json())
