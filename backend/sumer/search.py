"""محرك البحث: فهم الاستعلام، الاسترجاع من الفهرس المقلوب، الترتيب، التصحيح الإملائي، والاقتراحات.

لا شيء هنا يحفظ نص الاستعلام. التحليلات الوحيدة عدّادات مجمّعة في privacy.count.
"""

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from . import db
from . import text as T
from .indexer import ADULT_TERMS
from .parse import normalize_url

PAGE_SIZE = 10
CANDIDATES = 300
_SITE = re.compile(r"\bsite:([a-z0-9.\-]+)", re.I)
_PHRASE = re.compile(r'"([^"]{2,200})"')
_SENT = re.compile(r"\n+|(?<=[.!؟?])\s+")
CATEGORY_LABELS = {"gov": "حكومي", "academic": "أكاديمي", "news": "أخبار", "tech": "تقنية",
                   "document": "مستند", "business": "أعمال", "web": "ويب", "local": "محلي"}


@dataclass
class Concept:
    raw: str
    terms: list
    label: str | None = None     # الشكل المفهوم (للعرض: «شلون ← كيف»)
    kind: str | None = None      # dialect / arabizi / spelling


@dataclass
class Query:
    raw: str
    concepts: list = field(default_factory=list)
    phrases: list = field(default_factory=list)
    site: str | None = None
    lang: str | None = None
    adult: bool = False


def term_exists(terms: list[str]) -> set[str]:
    """يتحقق من وجود المصطلح (أو بادئته) في الفهرس المقلوب نفسه، فالنتيجة محدّثة دائماً."""
    found = set()
    for t in dict.fromkeys(terms):
        clean = re.sub(r"[^\w]", "", t)
        if len(clean) < 2:
            continue
        tq = f"{clean}:*" if len(clean) >= 3 else clean
        if db.fetchone("SELECT 1 FROM indexed_documents WHERE tsv @@ to_tsquery('simple', %s) LIMIT 1", (tq,)):
            found.add(t)
    return found


def understand(raw: str) -> Query:
    q = Query(raw=raw.strip()[:300])
    text = q.raw
    m = _SITE.search(text)
    if m:
        q.site = m.group(1).lower()
        text = _SITE.sub(" ", text)
    for ph in _PHRASE.findall(text):
        toks = T.tokens(ph)
        if len(toks) >= 2:
            q.phrases.append(toks)
    text = text.replace('"', " ")
    q.lang = T.detect_language(text)
    words = T.words(text)
    q.adult = bool(set(words) & ADULT_TERMS)

    latin_variants = {}
    for w in words:
        if T.is_latin_word(w) and not w.isdigit():
            latin_variants[w] = T.arabizi_variants(w)
    candidates = [T.stem(v) for vs in latin_variants.values() for v in vs]
    known = term_exists(candidates) if candidates else set()

    for w in words:
        if w in T.STOPWORDS and w not in T.IRAQI_DIALECT:
            continue
        forms, label, kind = [w], None, None
        if w in latin_variants:
            hits = [v for v in latin_variants[w] if v in T.IRAQI_DIALECT or T.stem(v) in known]
            if hits:
                best = max(hits, key=len)
                forms.extend(hits[:4])
                label, kind = best, "arabizi"
        bare = w[2:] if w.startswith("ال") and len(w) > 4 else w
        if bare != w and bare in T.IRAQI_DIALECT:
            forms.append(bare)
        for f in list(forms):
            if f in T.IRAQI_DIALECT:
                forms.extend(T.IRAQI_DIALECT[f])
                label = label or " / ".join(T.IRAQI_DIALECT[f][:2])
                kind = kind or "dialect"
        terms = list(dict.fromkeys(T.stem(f) for f in forms if f not in T.STOPWORDS and len(f) > 1))
        if terms:
            q.concepts.append(Concept(raw=w, terms=terms, label=label, kind=kind))
    return q


def _tsquery(concepts, mode="and", phrases=()) -> str:
    def term(t):
        t = re.sub(r"[^\w]", "", t)
        return f"{t}:*" if len(t) >= 3 else t
    groups = []
    for c in concepts:
        ts = [term(t) for t in c.terms if re.sub(r"[^\w]", "", t)]
        if ts:
            groups.append("(" + " | ".join(ts) + ")")
    joiner = " & " if mode == "and" else " | "
    q = joiner.join(groups)
    for ph in phrases:
        p = " <-> ".join(re.sub(r"[^\w]", "", t) for t in ph if re.sub(r"[^\w]", "", t))
        if p:
            q = f"({q}) & ({p})" if q else f"({p})"
    return q


def spelling(concepts) -> list[Concept] | None:
    """إذا كلمة غير موجودة بالفهرس، نقترح أقرب مصطلح (تشابه ثلاثي، الأكثر تكراراً)."""
    terms = [c.terms[0] for c in concepts]
    known = term_exists([t for c in concepts for t in c.terms])
    changed, out = False, []
    for c in concepts:
        if any(t in known for t in c.terms) or len(c.terms[0]) < 3:
            out.append(c)
            continue
        row = db.fetchone(
            "SELECT term, similarity(term, %s) AS s FROM index_terms WHERE term %% %s "
            "ORDER BY s DESC, df DESC LIMIT 1", (c.terms[0], c.terms[0]))
        if row and row["s"] >= 0.3:
            changed = True
            out.append(Concept(raw=c.raw, terms=[row["term"]], label=row["term"], kind="spelling"))
        else:
            out.append(c)
    return out if changed else None


def _weights():
    s = db.get_settings("search.")
    w = {"text": 1.0, "title": 2.0, "authority": 1.5, "quality": 1.0, "freshness": 0.5, "iraqi": 0.6,
         "language": 0.4, "spam_penalty": 3.0}
    w.update(s.get("search.ranking") or {})
    region = s.get("search.region_priority") or {"iq": 1.0}
    lang_pri = {r["code"]: r["priority"] for r in db.fetchall("SELECT code, priority FROM language_metadata WHERE enabled")}
    return w, region, lang_pri, int(s.get("search.per_domain_limit", 3))


def _retrieve(q: Query, tsq: str, filters: dict, safe: str, limit=CANDIDATES):
    where = ["d.tsv @@ to_tsquery('simple', %(tsq)s)", "d.duplicate_of IS NULL", "dm.status <> 'blocked'"]
    p = {"tsq": tsq, "limit": limit, "qnorm": " ".join(T.words(q.raw))[:200]}
    if safe in ("strict", "moderate") and not (safe == "moderate" and q.adult):
        where.append("NOT d.is_adult")
    if safe == "strict":
        where.append("d.spam_score < 0.5")
    if q.site:
        where.append("(dm.host = %(site)s OR dm.host LIKE %(site_sub)s)")
        p["site"], p["site_sub"] = q.site, "%." + q.site
    if filters.get("lang"):
        where.append("d.lang = %(lang)s")
        p["lang"] = filters["lang"]
    if filters.get("category"):
        cats = {"gov": ["gov"], "academic": ["academic"], "news": ["news"], "docs": ["document"], "tech": ["tech"]}
        where.append("d.category = ANY(%(cats)s)")
        p["cats"] = cats.get(filters["category"], [filters["category"]])
    if filters.get("since_days"):
        where.append("COALESCE(d.published_at, d.indexed_at) > now() - make_interval(days => %(since)s)")
        p["since"] = int(filters["since_days"])
    sql = f"""
        SELECT d.page_id, d.url, d.title, d.description, d.body, d.lang, d.category, d.doc_type, d.quality,
               d.spam_score, d.indexed_at, d.published_at, dm.host, dm.is_iraqi, dm.authority, dm.reputation,
               ts_rank_cd(d.tsv, to_tsquery('simple', %(tsq)s), 32) AS text_rank,
               similarity(d.title_norm, %(qnorm)s) AS title_sim
        FROM indexed_documents d JOIN domains dm ON dm.id = d.domain_id
        WHERE {' AND '.join(where)}
        ORDER BY ts_rank_cd(d.tsv, to_tsquery('simple', %(tsq)s), 32) DESC
        LIMIT %(limit)s"""
    return db.fetchall(sql, p)


def _score(r, q: Query, w, region, lang_pri, now):
    age_days = (now - (r["published_at"] or r["indexed_at"]).timestamp()) / 86400
    title_toks = set(T.tokens(r["title"]))
    body_toks = set(T.tokens((r["description"] or "") + " " + r["body"][:30000]))
    cover = sum(1 for c in q.concepts if any(tok.startswith(t) for t in c.terms for tok in title_toks | body_toks))
    in_title = sum(1 for c in q.concepts if any(tok.startswith(t) for t in c.terms for tok in title_toks))
    n = max(len(q.concepts), 1)
    relevance = w["text"] * r["text_rank"] * 4 + w["title"] * (in_title / n) + 1.5 * (cover / n) + w["title"] * 0.5 * r["title_sim"]
    # التفضيل العراقي يضاعف الصلة ولا يضاف لها، فلا ترتفع صفحة عراقية غير ذات صلة فوق صفحة مفيدة
    regional = w["iraqi"] * region.get("iq", 1.0) * (1 if r["is_iraqi"] else 0)
    language = w["language"] * (lang_pri.get(r["lang"], 0.5) if (q.lang and r["lang"] == q.lang) else 0)
    components = {
        "relevance": relevance,
        "regional_boost": relevance * regional * 0.3,
        "language_boost": relevance * language * 0.3,
        "authority": w["authority"] * (0.6 * r["authority"] + 0.4 * r["reputation"]),
        "quality": w["quality"] * r["quality"],
        "freshness": w["freshness"] * math.exp(-max(age_days, 0) / 365),
        "spam_penalty": -w["spam_penalty"] * r["spam_score"],
    }
    return sum(components.values()), components, cover


def snippet(text: str, concepts, width: int = 240):
    terms = [t for c in concepts for t in c.terms]
    best, best_hits = "", -1
    for sent in _SENT.split(text[:80_000]):
        sent = " ".join(sent.split())
        if len(sent) < 25:
            continue
        toks = set(T.tokens(sent))
        hits = sum(1 for c in concepts if any(tok.startswith(t) for t in c.terms for tok in toks))
        if hits > best_hits:
            best, best_hits = sent, hits
            if hits == len(concepts):
                break
    if not best:
        best = " ".join(text.split())[:width]
    if len(best) > width:
        best = best[:width].rsplit(" ", 1)[0] + "…"
    return highlight(best, terms)


def highlight(text: str, terms):
    segs = []
    for word in re.split(r"(\s+)", text):
        w = T.words(word)
        hit = bool(w) and any(T.stem(w[0]).startswith(t) for t in terms if t)
        if segs and segs[-1][1] == hit:
            segs[-1] = (segs[-1][0] + word, hit)
        else:
            segs.append((word, hit))
    return [{"t": t, "h": h} for t, h in segs]


def search(raw: str, page: int = 1, filters: dict | None = None, safe: str = "moderate",
           sort: str = "relevance", explain: bool = False) -> dict:
    t0 = time.perf_counter()
    filters = filters or {}
    q = understand(raw)
    out = {"query": q.raw, "page": page, "results": [], "total": 0, "corrected": None, "did_you_mean": None,
           "understood": [{"raw": c.raw, "label": c.label, "kind": c.kind} for c in q.concepts if c.label],
           "related": [], "panel": None, "lang": q.lang}
    if not q.concepts and not q.phrases:
        out["took_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    rows = _retrieve(q, _tsquery(q.concepts, "and", q.phrases), filters, safe) if q.concepts or q.phrases else []
    if len(rows) < 5 and len(q.concepts) > 1 and not q.phrases:
        seen = {r["page_id"] for r in rows}
        rows = list(rows) + [r for r in _retrieve(q, _tsquery(q.concepts, "or"), filters, safe) if r["page_id"] not in seen]
    fixed = spelling(q.concepts)
    if fixed:
        out["did_you_mean"] = " ".join(c.label or c.raw for c in fixed)
        if not rows:
            q.concepts = fixed
            out["corrected"] = out["did_you_mean"]
            rows = _retrieve(q, _tsquery(fixed, "and"), filters, safe) or _retrieve(q, _tsquery(fixed, "or"), filters, safe)

    w, region, lang_pri, per_domain = _weights()
    now = time.time()
    scored = []
    for r in rows:
        s, comp, cover = _score(r, q, w, region, lang_pri, now)
        scored.append((s, comp, cover, r))
    if q.concepts:
        best_cover = max((x[2] for x in scored), default=0)
        scored = [x for x in scored if x[2] >= max(1, best_cover - 1)]
    if sort == "date":
        scored.sort(key=lambda x: (x[3]["published_at"] or x[3]["indexed_at"]), reverse=True)
    else:
        scored.sort(key=lambda x: x[0], reverse=True)
    counts, diverse = Counter(), []
    for x in scored:
        if counts[x[3]["host"]] < per_domain or q.site:
            diverse.append(x)
            counts[x[3]["host"]] += 1
    out["total"] = len(diverse)
    start = (page - 1) * PAGE_SIZE
    for s, comp, cover, r in diverse[start:start + PAGE_SIZE]:
        item = {
            "url": r["url"], "title": r["title"] or r["url"], "host": r["host"], "lang": r["lang"],
            "category": r["category"], "doc_type": r["doc_type"],
            "indexed_at": r["indexed_at"].isoformat(), "published_at": r["published_at"].isoformat() if r["published_at"] else None,
            "title_hl": highlight(r["title"] or r["url"], [t for c in q.concepts for t in c.terms]),
            "snippet": snippet((r["description"] or "") + "\n" + r["body"], q.concepts),
            "iraqi": r["is_iraqi"],
        }
        if explain:
            item["score"] = round(s, 4)
            item["explain"] = {k: round(v, 4) for k, v in comp.items()} | {
                "text_rank": round(r["text_rank"], 4), "title_similarity": round(r["title_sim"], 4),
                "concepts_matched": cover, "authority": round(r["authority"], 3), "reputation": round(r["reputation"], 3),
                "quality": round(r["quality"], 3), "spam_score": round(r["spam_score"], 3)}
        out["results"].append(item)

    if page == 1 and diverse:
        out["related"] = related(q, [x[3] for x in diverse[:15]])
        top = diverse[0][3]
        if top["category"] in ("gov", "academic") and top["reputation"] >= 0.7 and diverse[0][2] == len(q.concepts):
            out["panel"] = {"title": top["title"], "description": top["description"] or snippet(top["body"], q.concepts),
                            "url": top["url"], "host": top["host"], "category": top["category"],
                            "verified": top["host"].endswith((".gov.iq", ".edu.iq"))}
    out["took_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


def related(q: Query, rows) -> list[str]:
    qterms = {t for c in q.concepts for t in c.terms}
    cnt = Counter()
    for r in rows:
        for w in set(T.words(r["title"])):
            if w in T.STOPWORDS or len(w) < 3 or any(T.stem(w).startswith(t) for t in qterms):
                continue
            cnt[w] += 1
    base = " ".join(c.raw for c in q.concepts[:3])
    return [f"{base} {w}" for w, n in cnt.most_common(6) if n >= 1][:6]


def suggest(prefix: str, limit: int = 8) -> list[str]:
    """اقتراحات من محتوى الفهرس (العناوين والمصطلحات)، وليس من استعلامات المستخدمين."""
    p = " ".join(T.words(prefix))[:100]
    if len(p) < 2:
        return []
    rows = db.fetchall(
        "SELECT DISTINCT ON (title_norm) title, similarity(title_norm, %s) AS s FROM indexed_documents "
        "WHERE duplicate_of IS NULL AND NOT is_adult AND (title_norm LIKE %s OR title_norm %% %s) "
        "ORDER BY title_norm, s DESC LIMIT 50", (p, "%" + p.replace("%", "") + "%", p))
    titles = sorted(rows, key=lambda r: -r["s"])
    out = []
    for r in titles:
        t = " ".join(r["title"].split())
        if 3 <= len(t) <= 80 and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def search_images(raw: str, page: int = 1, size: str | None = None, fmt: str | None = None, safe: str = "moderate"):
    t0 = time.perf_counter()
    q = understand(raw)
    if not q.concepts:
        return {"results": [], "total": 0, "took_ms": 0}
    tsq = _tsquery(q.concepts, "or")
    where = ["i.status = 'ok'", "i.tsv @@ to_tsquery('simple', %(tsq)s)"]
    p = {"tsq": tsq, "off": (page - 1) * 40}
    if safe != "off":
        where.append("NOT i.is_adult")
    if size == "small":
        where.append("i.width < 400")
    elif size == "medium":
        where.append("i.width BETWEEN 400 AND 1200")
    elif size == "large":
        where.append("i.width > 1200")
    if fmt:
        where.append("i.format = %(fmt)s")
        p["fmt"] = fmt
    rows = db.fetchall(
        f"SELECT i.id, i.image_url, i.width, i.height, i.format, i.alt, d.host, pg.url AS page_url, "
        f"ts_rank_cd(i.tsv, to_tsquery('simple', %(tsq)s)) AS r, count(*) OVER () AS total "
        f"FROM image_index i LEFT JOIN domains d ON d.id = i.domain_id LEFT JOIN crawled_pages pg ON pg.id = i.page_id "
        f"WHERE {' AND '.join(where)} ORDER BY r DESC LIMIT 40 OFFSET %(off)s", p)
    return {"total": rows[0]["total"] if rows else 0, "took_ms": round((time.perf_counter() - t0) * 1000, 1),
            "results": [{"id": r["id"], "image_url": r["image_url"], "width": r["width"], "height": r["height"],
                         "format": r["format"], "alt": r["alt"], "host": r["host"], "page_url": r["page_url"]} for r in rows]}


def inspect_url(raw: str) -> dict:
    """معلومات من الفهرس فقط. لا يؤدي لأي زحف (الفحص ليس إذناً بالوصول)."""
    u = normalize_url(raw if "://" in raw else "https://" + raw)
    if not u:
        raise ValueError("رابط غير صالح")
    host = urlsplit(u).hostname
    dom = db.fetchone("SELECT id, host, is_iraqi, status, category, reputation, authority, page_count, "
                      "first_seen_at, last_crawled_at, robots_fetched_at, robots_crawl_delay, "
                      "robots_txt IS NOT NULL AND robots_txt <> '' AS has_robots FROM domains WHERE host = %s", (host,))
    if not dom:
        return {"url": u, "host": host, "known": False}
    page = db.fetchone(
        "SELECT p.url, p.status, p.http_status, p.last_crawled_at, p.canonical_url, d.title, d.description, d.lang, "
        "d.category, d.indexed_at, d.word_count, m.meta FROM crawled_pages p "
        "LEFT JOIN indexed_documents d ON d.page_id = p.id LEFT JOIN document_metadata m ON m.page_id = p.id "
        "WHERE p.url = %s", (u,))
    pages = db.fetchall("SELECT url, title, indexed_at FROM indexed_documents WHERE domain_id = %s AND duplicate_of IS NULL "
                        "ORDER BY indexed_at DESC LIMIT 20", (dom["id"],))
    stats = db.fetchone("SELECT count(*) AS indexed, count(DISTINCT lang) AS langs FROM indexed_documents WHERE domain_id = %s",
                        (dom["id"],))
    inbound = db.fetchone("SELECT count(DISTINCT src_page_id) AS n FROM page_links WHERE dst_domain_id = %s", (dom["id"],))
    return {"url": u, "host": host, "known": True, "domain": _plain(dom), "page": _plain(page) if page else None,
            "indexed_pages": stats["indexed"], "inbound_links": inbound["n"], "recent_pages": [_plain(r) for r in pages]}


def _plain(row):
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(row).items()}
