"""اختبارات الزحف والفهرسة والبحث (صلة النتائج والامتثال)."""

from sumer import db, search
from sumer import text as T


# ---------------- معالجة النص ----------------
def test_normalization():
    assert T.normalize("أَحْمَد") == "احمد"
    assert T.normalize("مكتبة") == "مكتبه"
    assert T.normalize("٢٠٢٦") == "2026"
    assert T.normalize("كـــتاب") == "كتاب"


def test_language_detection():
    assert T.detect_language("هذا نص عربي عن العراق وبغداد") == "ar"
    assert T.detect_language("زانکۆی سلێمانی یەکێکە لە گەورەترین زانکۆکانی هەرێمی کوردستان") == "ckb"
    assert T.detect_language("Baghdad is the capital of Iraq and the river") == "en"


def test_stemming():
    assert T.stem("الجامعات") == "جامع"
    assert T.stem("universities") == "university"
    assert T.stem("searching") == "search"


def test_simhash_near_duplicates():
    a = T.simhash("لاستخراج جواز السفر العراقي يجب امتلاك البطاقة الوطنية الموحدة ثم الحجز الإلكتروني")
    b = T.simhash("لاستخراج جواز السفر العراقي يجب امتلاك البطاقة الوطنية الموحدة ثم الحجز الالكتروني")
    c = T.simhash("مطاعم السمك المسكوف في شارع أبو نؤاس المطلة على نهر دجلة")
    assert T.hamming(a, b) < T.hamming(a, c)


# ---------------- الزحف والامتثال ----------------
def status_of(path):
    r = db.fetchone("SELECT status FROM crawled_pages WHERE url LIKE %s", ("%" + path,))
    return r["status"] if r else None


def test_robots_respected(crawled):
    assert status_of("/private/secret.html") == "robots_blocked"
    assert not db.fetchone("SELECT 1 FROM indexed_documents WHERE url LIKE '%secret%'")


def test_noindex_respected(crawled):
    assert status_of("/draft.html") == "noindex"
    assert not db.fetchone("SELECT 1 FROM indexed_documents WHERE url LIKE '%draft%'")


def test_excluded_path(crawled):
    assert status_of("/admin-area/x.html") == "excluded"


def test_redirect_followed(crawled):
    assert status_of("/old.html") == "redirect"
    assert status_of("/jobs.html") == "ok"


def test_canonical(crawled):
    assert status_of("/canon-a.html") == "duplicate"
    assert status_of("/weather.html") == "ok"


def test_sitemap_discovery(crawled):
    assert status_of("/from-sitemap.html") == "ok"


def test_tracking_params_and_fragments_normalized(crawled):
    assert not db.fetchone("SELECT 1 FROM crawled_pages WHERE url LIKE '%utm_source%' OR url LIKE '%#%'")


def test_duplicate_detection(crawled):
    d = db.fetchone("SELECT duplicate_of FROM indexed_documents WHERE url LIKE '%/duplicate.html'")
    assert d and d["duplicate_of"] is not None


def test_spam_scored(crawled):
    s = db.fetchone("SELECT spam_score FROM indexed_documents WHERE url LIKE '%/spam.html'")
    assert s["spam_score"] >= 0.5


def test_languages_and_pdf(crawled):
    rows = {r["url"].rsplit("/", 1)[-1]: r for r in db.fetchall("SELECT url, lang, doc_type FROM indexed_documents")}
    assert rows["kurdish.html"]["lang"] == "ckb"
    assert rows["english.html"]["lang"] == "en"
    assert rows["report.pdf"]["doc_type"] == "pdf"


def test_images_indexed(crawled):
    rows = db.fetchall("SELECT status, width, format, dhash FROM image_index")
    assert len(rows) == 2 and all(r["status"] == "ok" and r["dhash"] is not None for r in rows)


def test_crawl_history_logged(crawled):
    events = {r["event"] for r in db.fetchall("SELECT DISTINCT event FROM crawl_logs")}
    assert {"fetched", "robots_blocked", "redirect", "canonical", "sitemap"} <= events


# ---------------- صلة النتائج ----------------
def top(q, **kw):
    r = search.search(q, **kw)
    assert r["results"], f"لا نتائج لـ {q}"
    return r["results"][0]["url"].rsplit("/", 1)[-1], r


def test_relevance_fusha():
    assert top("استخراج جواز السفر")[0] == "passport.html"


def test_relevance_iraqi_dialect():
    name, r = top("شلون اطلع جواز")
    assert name == "passport.html"
    assert any(u["kind"] == "dialect" for u in r["understood"])
    assert top("وين احسن مسكوف ببغداد")[0] == "restaurants.html"
    assert top("شكد سعر الامبير")[0] == "generator.html"


def test_relevance_arabizi():
    assert top("jawaz safar")[0] == "passport.html"
    assert top("ta3yeenat")[0] == "jobs.html"


def test_spelling_correction():
    name, r = top("جوااز")
    assert name == "passport.html" and r["corrected"]


def test_kurdish_english_pdf():
    assert top("زانکۆی سلێمانی")[0] == "kurdish.html"
    assert top("baghdad masgouf")[0] == "english.html"
    assert top("development plan")[0] == "report.pdf"


def test_phrase_and_site():
    name, r = top('"البطاقة الوطنية"')
    assert name == "national-id.html"
    assert top("site:127.0.0.1 طقس")[0] == "weather.html"


def test_duplicates_hidden_from_results():
    r = search.search("استخراج جواز السفر")
    assert not any(x["url"].endswith("/duplicate.html") for x in r["results"])


def test_spam_ranked_low():
    r = search.search("عروض رخيص بغداد مطاعم")
    urls = [x["url"].rsplit("/", 1)[-1] for x in r["results"]]
    if "spam.html" in urls and "restaurants.html" in urls:
        assert urls.index("restaurants.html") < urls.index("spam.html")


def test_highlight_and_snippet():
    _, r = top("السمك المسكوف")
    assert any(seg["h"] for seg in r["results"][0]["snippet"])


def test_explain():
    r = search.search("جواز", explain=True)
    assert "relevance" in r["results"][0]["explain"]


def test_suggest_from_index_content():
    assert any("جواز" in s for s in search.suggest("جواز"))


def test_image_text_search():
    r = search.search_images("مسكوف")
    assert r["results"] and "masgouf" in r["results"][0]["image_url"]


def test_inspect_url_reads_index_only(crawled):
    n_before = db.fetchone("SELECT count(*) AS n FROM crawl_jobs")["n"]
    info = search.inspect_url(crawled + "/passport.html")
    assert info["known"] and info["page"]["status"] == "ok"
    assert db.fetchone("SELECT count(*) AS n FROM crawl_jobs")["n"] == n_before   # لا زحف
