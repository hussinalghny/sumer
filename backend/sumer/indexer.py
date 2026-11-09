"""الفهرسة: تحويل صفحة محللة إلى مستند قابل للبحث، مع الجودة والسبام والتكرار."""

import hashlib
import math
import re
from collections import Counter
from datetime import datetime

from . import text as T
from .parse import ParsedPage

# قائمة مختصرة لكشف المحتوى الإباحي للبحث الآمن (مطبّعة)
ADULT_TERMS = {T.normalize(w) for w in """
porn xxx sex nude nsfw erotic escort
اباحي اباحيه سكس جنس عاري عاريه
""".split()}

TECH_TERMS = {T.normalize(w) for w in """
python javascript php laravel react programming code api linux docker database sql
برمجه برمجة مبرمج كود خوارزميه شبكات سيرفر قاعده بيانات ذكاء اصطناعي
""".split()}

BODY_INDEX_CHARS = 120_000


def url_hash(url: str) -> bytes:
    return hashlib.sha256(url.encode("utf-8")).digest()


def classify(host: str, domain_category: str | None, parsed: ParsedPage, doc_type: str) -> str:
    if domain_category:
        return domain_category
    if doc_type == "pdf":
        return "document"
    if host.endswith(".gov.iq") or host.endswith(".gov"):
        return "gov"
    if host.endswith(".edu.iq") or host.endswith(".edu") or ".ac." in host:
        return "academic"
    if parsed.meta.get("og:type", "").startswith("article") or parsed.published:
        return "news"
    toks = set(T.tokens(parsed.title + " " + parsed.headings))
    if len(toks & {T.stem(t) for t in TECH_TERMS}) >= 1:
        return "tech"
    return "web"


def spam_signals(parsed: ParsedPage, words: list[str]) -> list[tuple[str, float, str]]:
    sig = []
    n = len(words)
    if n < 15:
        sig.append(("thin_content", 0.2, f"{n} كلمة"))
    if n >= 100:
        top, cnt = Counter(words).most_common(1)[0]
        ratio = cnt / n
        if ratio > 0.12:
            sig.append(("keyword_stuffing", min(1.0, ratio * 4), f"«{top}» تكررت {cnt} مرة"))
    if n and len(parsed.links) / max(n, 1) > 0.5 and len(parsed.links) > 50:
        sig.append(("link_farm", 0.6, f"{len(parsed.links)} رابط مقابل {n} كلمة"))
    if parsed.title and len(parsed.title) > 200:
        sig.append(("long_title", 0.2, f"{len(parsed.title)} حرف"))
    return sig


def quality_score(parsed: ParsedPage, n_words: int, spam: float) -> float:
    q = 0.2
    q += min(0.35, math.log1p(n_words) / 25)
    q += 0.1 if parsed.description else 0
    q += 0.1 if parsed.headings else 0
    q += 0.1 if 10 <= len(parsed.title) <= 120 else 0
    q += 0.05 if parsed.lang_attr else 0
    return max(0.0, min(1.0, q - spam * 0.5))


def index_document(conn, *, page_id: int, domain_id: int, host: str, url: str, parsed: ParsedPage,
                   doc_type: str, domain_category: str | None, simhash: int, content_hash: bytes,
                   analyzer_version: int, index_version_id: int) -> dict:
    """يكتب المستند وبياناته الوصفية وإشارات السبام. يرجع ملخصاً (مكرر؟ لغة؟)."""
    full_text = "\n".join(x for x in (parsed.title, parsed.description, parsed.headings, parsed.text) if x)
    words = T.tokens(full_text)
    lang = T.detect_language(full_text) or (parsed.lang_attr[:2] if parsed.lang_attr[:2] in ("ar", "en") else None)
    if parsed.lang_attr.startswith("ckb") or parsed.lang_attr.startswith("ku"):
        lang = "ckb" if T.detect_language(full_text) != "en" else lang
    category = classify(host, domain_category, parsed, doc_type)
    signals = spam_signals(parsed, words)
    spam = min(1.0, sum(s[1] for s in signals))
    is_adult = len(set(T.words(full_text[:20000])) & ADULT_TERMS) >= 2
    quality = quality_score(parsed, len(words), spam)
    title_norm = " ".join(T.words(parsed.title))[:300]

    # كشف التكرار: محتوى مطابق تماماً، أو SimHash قريب ضمن نفس النطاق ونفس العنوان
    # التكرار حتمي مهما كان ترتيب الزحف: الأصل هو الرابط الأقصر (الأنظف)، ثم الأقدم
    dup = conn.execute(
        "SELECT p.id FROM crawled_pages p JOIN indexed_documents d ON d.page_id = p.id "
        "WHERE p.content_hash = %s AND p.id <> %s AND (length(p.url), p.id) < (length(%s), %s) "
        "ORDER BY length(p.url), p.id LIMIT 1",
        (content_hash, page_id, url, page_id)).fetchone()
    duplicate_of = dup["id"] if dup else None
    if not duplicate_of and title_norm:
        near = conn.execute(
            "SELECT p.id, p.simhash FROM indexed_documents d JOIN crawled_pages p ON p.id = d.page_id "
            "WHERE d.domain_id = %s AND d.title_norm = %s AND d.page_id <> %s AND (length(p.url), p.id) < (length(%s), %s) "
            "AND p.simhash IS NOT NULL ORDER BY length(p.url), p.id LIMIT 50", (domain_id, title_norm, page_id, url, page_id)).fetchall()
        for r in near:
            if T.hamming(r["simhash"], simhash) <= 3:
                duplicate_of = r["id"]
                break
    # صفحات أحدث كانت مكررة لهذه الصفحة تبقى كذلك؛ وإذا تغيّر محتوى هذه الصفحة نحرّرها لتُقيّم من جديد
    conn.execute("UPDATE indexed_documents d SET duplicate_of = NULL FROM crawled_pages p "
                 "WHERE d.duplicate_of = %s AND p.id = d.page_id AND p.content_hash IS DISTINCT FROM %s "
                 "AND (p.simhash IS NULL OR bit_count((p.simhash # %s)::bit(64)) > 3)", (page_id, content_hash, simhash))
    # إذا صارت هذه الصفحة أصلاً، الصفحات المطابقة الأطول تشير إليها
    if not duplicate_of:
        conn.execute("UPDATE indexed_documents d SET duplicate_of = %s FROM crawled_pages p WHERE p.id = d.page_id "
                     "AND p.content_hash = %s AND d.page_id <> %s AND (length(p.url), p.id) > (length(%s), %s)",
                     (page_id, content_hash, page_id, url, page_id))

    published = None
    if parsed.published:
        try:
            published = datetime.fromisoformat(parsed.published.replace("Z", "+00:00"))
        except ValueError:
            published = None

    conn.execute(
        """
        INSERT INTO indexed_documents (page_id, domain_id, url, title, description, headings, body, lang, category,
            doc_type, tsv, title_norm, word_count, quality, spam_score, is_adult, published_at, duplicate_of,
            analyzer_version, index_version_id, indexed_at)
        VALUES (%(page_id)s, %(domain_id)s, %(url)s, %(title)s, %(description)s, %(headings)s, %(body)s, %(lang)s,
            %(category)s, %(doc_type)s,
            setweight(to_tsvector('simple', %(a)s), 'A') || setweight(to_tsvector('simple', %(b)s), 'B')
              || setweight(to_tsvector('simple', %(c)s), 'C'),
            %(title_norm)s, %(wc)s, %(quality)s, %(spam)s, %(adult)s, %(published)s, %(dup)s, %(av)s, %(iv)s, now())
        ON CONFLICT (page_id) DO UPDATE SET url = EXCLUDED.url, title = EXCLUDED.title,
            description = EXCLUDED.description, headings = EXCLUDED.headings, body = EXCLUDED.body,
            lang = EXCLUDED.lang, category = EXCLUDED.category, doc_type = EXCLUDED.doc_type, tsv = EXCLUDED.tsv,
            title_norm = EXCLUDED.title_norm, word_count = EXCLUDED.word_count, quality = EXCLUDED.quality,
            spam_score = EXCLUDED.spam_score, is_adult = EXCLUDED.is_adult, published_at = EXCLUDED.published_at,
            duplicate_of = EXCLUDED.duplicate_of, analyzer_version = EXCLUDED.analyzer_version,
            index_version_id = EXCLUDED.index_version_id, indexed_at = now()
        """,
        dict(page_id=page_id, domain_id=domain_id, url=url, title=parsed.title[:300],
             description=parsed.description[:500], headings=parsed.headings[:2000],
             body=parsed.text[:BODY_INDEX_CHARS], lang=lang, category=category, doc_type=doc_type,
             a=T.analyzed(parsed.title + " " + host.replace(".", " ")),
             b=T.analyzed(parsed.headings + " " + parsed.description),
             c=T.analyzed(parsed.text[:BODY_INDEX_CHARS]),
             title_norm=title_norm, wc=len(words), quality=quality, spam=spam, adult=is_adult,
             published=published, dup=duplicate_of, av=analyzer_version, iv=index_version_id))

    conn.execute(
        "INSERT INTO document_metadata (page_id, meta, hreflang, author, site_name, og_type) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (page_id) DO UPDATE SET meta = EXCLUDED.meta, "
        "hreflang = EXCLUDED.hreflang, author = EXCLUDED.author, site_name = EXCLUDED.site_name, og_type = EXCLUDED.og_type",
        (page_id, _json(parsed.meta), _json(parsed.hreflang), parsed.meta.get("author"),
         parsed.meta.get("og:site_name"), parsed.meta.get("og:type")))

    conn.execute("DELETE FROM spam_signals WHERE page_id = %s", (page_id,))
    for name, score, details in signals:
        conn.execute("INSERT INTO spam_signals (page_id, signal, score, details) VALUES (%s, %s, %s, %s)",
                     (page_id, name, score, details))
    return {"lang": lang, "category": category, "duplicate_of": duplicate_of, "spam": spam, "words": len(words)}


def reanalyze(conn, page_id: int, analyzer_version: int, index_version_id: int):
    """إعادة بناء tsv من النص المخزّن (لإعادة بناء الفهرس بدون إعادة زحف)."""
    row = conn.execute("SELECT d.title, d.description, d.headings, d.body, dm.host FROM indexed_documents d "
                       "JOIN domains dm ON dm.id = d.domain_id WHERE d.page_id = %s", (page_id,)).fetchone()
    if not row:
        return
    conn.execute(
        "UPDATE indexed_documents SET tsv = setweight(to_tsvector('simple', %s), 'A') || "
        "setweight(to_tsvector('simple', %s), 'B') || setweight(to_tsvector('simple', %s), 'C'), "
        "title_norm = %s, analyzer_version = %s, index_version_id = %s WHERE page_id = %s",
        (T.analyzed(row["title"] + " " + row["host"].replace(".", " ")),
         T.analyzed(row["headings"] + " " + row["description"]), T.analyzed(row["body"]),
         " ".join(T.words(row["title"]))[:300], analyzer_version, index_version_id, page_id))


def _json(d):
    import json
    return json.dumps(d or {}, ensure_ascii=False)


_IRAQ_HINT = re.compile(r"\.iq$")


def is_iraqi_host(host: str) -> bool:
    return bool(_IRAQ_HINT.search(host))
