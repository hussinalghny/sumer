"""استخراج المحتوى من HTML وPDF وsitemap."""

import io
import re
import defusedxml.ElementTree as ET  # حماية من هجمات XML
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit, quote, unquote

from selectolax.lexbor import LexborHTMLParser as HTMLParser

SKIP_SELECTORS = "script, style, noscript, template, svg, iframe, nav, footer, aside, form, select, header nav"
SKIP_EXT = (".zip", ".rar", ".7z", ".exe", ".apk", ".dmg", ".iso", ".mp4", ".mp3", ".avi", ".mov", ".wav",
            ".css", ".js", ".woff", ".woff2", ".ttf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".avif")
TRACKING_PARAMS = re.compile(r"^(utm_[a-z]+|fbclid|gclid|mc_eid|ref_src|igshid)$", re.I)


def normalize_url(url: str, base: str | None = None) -> str | None:
    """يوحّد الرابط: يحذف الجزء بعد #، ومعاملات التتبع، ويدعم الروابط بحروف غير لاتينية."""
    if not url:
        return None
    url = url.strip()
    if base:
        url = urljoin(base, url)
    url, _ = urldefrag(url)
    try:
        p = urlsplit(url)
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    host = p.hostname
    try:
        host = host.encode("idna").decode("ascii") if not host.isascii() else host.lower()
    except UnicodeError:
        return None
    netloc = host + (f":{p.port}" if p.port and p.port not in (80, 443) else "")
    path = quote(unquote(p.path or "/"), safe="/%:@!$&'()*+,;=-._~")
    query = "&".join(kv for kv in p.query.split("&") if kv and not TRACKING_PARAMS.match(kv.split("=")[0]))
    return urlunsplit((p.scheme, netloc, path, query, ""))


@dataclass
class ParsedPage:
    title: str = ""
    description: str = ""
    headings: str = ""
    text: str = ""
    lang_attr: str = ""
    canonical: str | None = None
    noindex: bool = False
    nofollow: bool = False
    links: list = field(default_factory=list)      # [(url, anchor)]
    images: list = field(default_factory=list)     # [(url, alt, context, w, h)]
    meta: dict = field(default_factory=dict)
    hreflang: dict = field(default_factory=dict)
    published: str | None = None


def parse_html(html: str, base_url: str) -> ParsedPage:
    tree = HTMLParser(html)
    page = ParsedPage()
    base = base_url
    b = tree.css_first("base[href]")
    if b:
        base = urljoin(base_url, b.attributes.get("href") or "")

    html_el = tree.css_first("html")
    if html_el:
        page.lang_attr = (html_el.attributes.get("lang") or "").lower()[:10]
    t = tree.css_first("title")
    page.title = " ".join((t.text() if t else "").split())[:300]

    for m in tree.css("meta"):
        a = m.attributes
        name = (a.get("name") or a.get("property") or "").lower()
        content = (a.get("content") or "").strip()
        if not name or not content:
            continue
        if name == "description" and not page.description:
            page.description = content[:500]
        elif name == "robots":
            c = content.lower()
            page.noindex = page.noindex or "noindex" in c or "none" in c
            page.nofollow = page.nofollow or "nofollow" in c or "none" in c
        elif name in ("og:title", "og:description", "og:type", "og:site_name", "author", "keywords",
                      "article:published_time", "og:locale"):
            page.meta[name] = content[:500]
    page.published = page.meta.get("article:published_time")
    if not page.description:
        page.description = page.meta.get("og:description", "")
    if not page.title:
        page.title = page.meta.get("og:title", "")

    for l in tree.css("link[href]"):
        rel = (l.attributes.get("rel") or "").lower()
        href = l.attributes.get("href")
        if rel == "canonical":
            page.canonical = normalize_url(href, base)
        elif rel == "alternate" and l.attributes.get("hreflang"):
            u = normalize_url(href, base)
            if u:
                page.hreflang[l.attributes["hreflang"].lower()] = u

    # الصور قبل حذف العناصر (مع سياق من النص المجاور)
    for img in tree.css("img"):
        a = img.attributes
        src = a.get("src") or a.get("data-src") or ""
        if src.startswith("data:"):
            continue
        u = normalize_url(src, base)
        if not u:
            continue
        ctx = ""
        parent = img.parent
        for _ in range(3):
            if parent is None:
                break
            ctx = " ".join(parent.text(separator=" ").split())
            if len(ctx) > 40:
                break
            parent = parent.parent
        page.images.append((u, (a.get("alt") or "").strip()[:300], ctx[:400],
                            _int(a.get("width")), _int(a.get("height"))))

    for a in tree.css("a[href]"):
        attrs = a.attributes
        if "nofollow" in (attrs.get("rel") or "").lower():
            continue
        u = normalize_url(attrs.get("href") or "", base)
        if u and not urlsplit(u).path.lower().endswith(SKIP_EXT):
            page.links.append((u, " ".join(a.text().split())[:200]))

    for node in tree.css(SKIP_SELECTORS):
        node.decompose()
    page.headings = " | ".join(" ".join(h.text().split()) for h in tree.css("h1, h2, h3"))[:2000]
    body = tree.body
    if body:
        text = body.text(separator="\n")
        lines = (" ".join(line.split()) for line in text.splitlines())
        page.text = "\n".join(line for line in lines if line)[:300_000]
    return page


def parse_pdf(data: bytes) -> ParsedPage:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    info = reader.metadata or {}
    parts = []
    for i, p in enumerate(reader.pages):
        if i >= 200:
            break
        parts.append(p.extract_text() or "")
    text = "\n".join(parts)
    page = ParsedPage(title=str(info.get("/Title") or "").strip()[:300], text=text[:300_000])
    if not page.title:
        first = next((ln.strip() for ln in text.splitlines() if len(ln.strip()) > 8), "")
        page.title = first[:200]
    page.meta = {"author": str(info.get("/Author") or "")[:200]}
    return page


def parse_sitemap(xml_bytes: bytes) -> tuple[list[str], list[str]]:
    """يرجع (روابط صفحات، روابط sitemaps فرعية)."""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:  # ParseError أو محاولة هجوم XML
        return [], []
    tag = root.tag.split("}")[-1]
    locs = [el.text.strip() for el in root.iter() if el.tag.split("}")[-1] == "loc" and el.text]
    if tag == "sitemapindex":
        return [], locs[:1000]
    return locs[:50_000], []


def _int(v):
    try:
        return int(str(v).strip().rstrip("px"))
    except (TypeError, ValueError):
        return None
