"use client";

import { motion } from "framer-motion";
import { ArrowLeftRight, BadgeCheck, ExternalLink, FileText, SlidersHorizontal, ImageIcon, Info, Languages, Loader2, Lock, Sparkles, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, post, upload, type PublicConfig, type Result, type SearchResponse } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { Segs } from "./Chrome";


function fmtDate(iso: string, lang: string) {
  try { return new Date(iso).toLocaleDateString(lang === "ar" ? "ar-IQ" : "en-GB", { year: "numeric", month: "short", day: "numeric" }); }
  catch { return ""; }
}

export function Spinner() {
  return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-lapis-600" /></div>;
}

export function ErrorBox({ err }: { err: string }) {
  return <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">{err}</div>;
}

// ============================ نتائج الويب ============================
type WebFilters = { category: string; lang: string; since: string; sort: string; safe: string };

export function WebResults({ q, config, onSearch }: { q: string; config: PublicConfig | null; onSearch: (q: string) => void }) {
  const { t, lang } = usePrefs();
  const [f, setF] = useState<WebFilters>({ category: "", lang: "", since: "", sort: "relevance", safe: "" });
  const [pages, setPages] = useState<SearchResponse[]>([]);
  const [page, setPage] = useState(1);
  const infinite = false;
  const [toolsOpen, setToolsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const sentinel = useRef<HTMLDivElement>(null);

  const load = useCallback(async (p: number, append: boolean) => {
    setLoading(true); setErr("");
    try {
      const r = await post<SearchResponse>("/api/search", {
        q, page: p, category: f.category || null, lang: f.lang || null, since_days: f.since ? Number(f.since) : null,
        sort: f.sort, safe: f.safe || null });
      setPages((prev) => (append ? [...prev, r] : [r]));
      setPage(p);
      if (!append) window.scrollTo({ top: 0 });
    } catch (e) {
      const a = e as ApiError;
      setErr(a.status === 429 ? "طلبات كثيرة، انتظر دقيقة" : a.status === 503 ? (a.detail === "maintenance" ? "سومر تحت الصيانة حالياً" : "البحث متوقف مؤقتاً") : a.message);
    } finally { setLoading(false); }
  }, [q, f]);

  useEffect(() => { load(1, false); }, [load]);

  const first = pages[0];
  const results: Result[] = infinite ? pages.flatMap((p) => p.results) : pages[pages.length - 1]?.results ?? [];
  const total = first?.total ?? 0;
  const lastPage = Math.min(20, Math.ceil(total / 10));

  useEffect(() => {
    if (!infinite || !sentinel.current) return;
    const io = new IntersectionObserver((es) => { if (es[0].isIntersecting && !loading && page < lastPage) load(page + 1, true); });
    io.observe(sentinel.current);
    return () => io.disconnect();
  }, [infinite, loading, page, lastPage, load]);

  const chip = (k: keyof typeof t.categories, v: string) => (
    <button key={k} onClick={() => setF({ ...f, category: v })}
      className={`whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition ${f.category === v ? "bg-ink text-white dark:bg-surface-100 dark:text-ink" : "text-ink-muted hover:bg-surface-100 dark:hover:bg-night-200"}`}>
      {t.categories[k]}
    </button>
  );
  const sel = "rounded-full border border-surface-200 bg-transparent px-3 py-1.5 text-sm text-ink-muted dark:border-night-300";

  return (
    <div className="grid min-w-0 gap-10 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0">
        <div className="mb-3 flex items-center gap-2">
        <div className="no-scrollbar flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {chip("all", "")}{chip("gov", "gov")}{chip("academic", "academic")}{chip("news", "news")}{chip("docs", "docs")}{chip("tech", "tech")}
        </div>
          <button onClick={() => setToolsOpen((o) => !o)} aria-expanded={toolsOpen}
            aria-label={t.tools} className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition ${toolsOpen || f.lang || f.since || f.sort !== "relevance" || f.safe ? "text-lapis-700 dark:text-lapis-400" : "text-ink-muted"} hover:bg-surface-100 dark:hover:bg-night-200`}>
            <SlidersHorizontal className="h-4 w-4" /><span className="hidden sm:inline">{t.tools}</span>
          </button>
        </div>
        {toolsOpen && <div className="mb-4 flex flex-wrap items-center gap-2">
          <select aria-label="language" className={sel} value={f.lang} onChange={(e) => setF({ ...f, lang: e.target.value })}>
            <option value="">{t.filters.any}</option>
            {config?.languages.map((l) => <option key={l.code} value={l.code}>{l.native_name}</option>)}
          </select>
          <select aria-label="time" className={sel} value={f.since} onChange={(e) => setF({ ...f, since: e.target.value })}>
            <option value="">{t.filters.time}</option><option value="1">{t.filters.day}</option><option value="7">{t.filters.week}</option>
            <option value="30">{t.filters.month}</option><option value="365">{t.filters.year}</option>
          </select>
          <select aria-label="sort" className={sel} value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value })}>
            <option value="relevance">{t.filters.relevance}</option><option value="date">{t.filters.date}</option>
          </select>
          <select aria-label={t.filters.safe} className={sel} value={f.safe} onChange={(e) => setF({ ...f, safe: e.target.value })}>
            <option value="">{t.filters.safe}</option><option value="strict">{t.filters.strict}</option>
            <option value="moderate">{t.filters.moderate}</option><option value="off">{t.filters.off}</option>
          </select>
        </div>}

        {first && (
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-muted">
            <span>{first.web_provider ? t.webNote(first.local_total ?? 0, first.web_provider) : t.results(total, Math.max(1, Math.round(first.took_ms)))}</span>
            <span className="flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400"><Lock className="h-3.5 w-3.5" />{t.notStored}</span>
          </div>
        )}
        {first && first.understood.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-1.5 text-sm text-ink-muted">
            <Sparkles className="h-4 w-4 text-gold-500" />{t.understood}
            {first.understood.map((u) => (
              <span key={u.raw} className="rounded-lg bg-lapis-50 px-2 py-0.5 text-lapis-700 dark:bg-lapis-900/40 dark:text-lapis-200">
                <span className="text-ink-faint">{u.raw}</span> ← {u.label}
              </span>
            ))}
          </div>
        )}
        {first?.corrected && <p className="mb-3 text-sm">{t.showingFor} <b className="text-lapis-600">{first.corrected}</b></p>}
        {first?.did_you_mean && !first.corrected && (
          <p className="mb-3 text-sm">{t.didYouMean} <button className="font-semibold text-lapis-600 hover:underline" onClick={() => onSearch(first.did_you_mean!)}>{first.did_you_mean}</button></p>
        )}
        {err && <ErrorBox err={err} />}
        {loading && !results.length && <Spinner />}

        {!loading && first && !results.length && !err && (
          <div className="py-16"><h2 className="text-2xl font-semibold">{t.noResults(q)}</h2><p className="mt-2 text-ink-muted">{t.noResultsHint}</p></div>
        )}

        <ol className="divide-y divide-surface-200 dark:divide-night-300">
          {results.map((r, i) => (
            <motion.li key={r.url} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 10) * .03, duration: .3 }} className="py-5">
              <div className="flex items-center gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-surface-200 bg-white text-xs font-semibold text-ink-soft dark:border-night-300 dark:bg-night-200" aria-hidden>
                  {r.doc_type === "pdf" ? <FileText className="h-3.5 w-3.5" /> : (r.host.replace(/^www\./, "")[0] ?? "").toUpperCase()}
                </span>
                <div className="min-w-0 leading-tight">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <span className="ltr-text truncate">{r.host.replace(/^www\./, "")}</span>
                    {r.source === "web" && <span className="rounded-md bg-gold-500/15 px-1.5 py-0.5 text-[11px] font-semibold text-gold-600 dark:text-gold-400">{t.fromWeb}</span>}
                    {r.category !== "web" && <span className="rounded-md bg-surface-100 px-1.5 py-0.5 text-[11px] font-semibold text-ink-muted dark:bg-night-300">{t.cat[r.category] ?? r.category}</span>}
                    {r.lang && <span className="text-[11px] text-ink-faint">{t.langs[r.lang] ?? r.lang}</span>}
                  </div>
                  <div className="ltr-text truncate text-xs text-ink-faint">{r.url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "").split("/").join(" › ")}</div>
                </div>
              </div>
              <h3 className="mt-2 text-xl font-medium leading-snug">
                <a href={r.url} rel="noreferrer noopener" className="text-lapis-700 hover:underline dark:text-lapis-400"><Segs segs={r.title_hl} /></a>
              </h3>
              <p className="mt-1 text-[15.5px] leading-7 text-ink-soft dark:text-surface-300"><Segs segs={r.snippet} /></p>
              {(r.published_at ?? r.indexed_at) && <p className="mt-1 text-xs text-ink-faint">{t.indexed} {fmtDate((r.published_at ?? r.indexed_at)!, lang)}</p>}
            </motion.li>
          ))}
        </ol>

        {infinite ? <div ref={sentinel} className="h-10">{loading && results.length > 0 && <Spinner />}</div> : lastPage > 1 && (
          <nav className="mt-6 flex flex-wrap items-center gap-1.5" aria-label="pagination">
            {Array.from({ length: lastPage }, (_, i) => i + 1).map((n) => (
              <button key={n} onClick={() => load(n, false)} aria-current={n === page ? "page" : undefined}
                className={`h-10 min-w-10 rounded-xl px-3 text-sm ${n === page ? "bg-lapis-600 text-white" : "hover:bg-surface-100 dark:hover:bg-night-200"}`}>{n.toLocaleString(lang === "ar" ? "ar-IQ" : "en")}</button>
            ))}
          </nav>
        )}
      </div>

      <aside className="space-y-6">
        {first?.panel && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl border border-surface-200 bg-white p-6 shadow-soft dark:border-night-300 dark:bg-night-200">
            {first.panel.verified && <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-emerald-600"><BadgeCheck className="h-4 w-4" />{t.verified}</div>}
            <h3 className="text-xl font-semibold">{first.panel.title}</h3>
            <p className="mt-2 text-sm leading-6 text-ink-soft dark:text-surface-300">
              {typeof first.panel.description === "string" ? first.panel.description : <Segs segs={first.panel.description} />}
            </p>
            <a href={first.panel.url} rel="noreferrer noopener" className="ltr-text mt-3 inline-flex items-center gap-1 text-sm text-lapis-600 hover:underline">{first.panel.host}<ExternalLink className="h-3.5 w-3.5" /></a>
          </motion.div>
        )}
        {first && first.related.length > 0 && (
          <div>
            <h4 className="mb-3 text-sm font-semibold text-ink-muted">{t.related}</h4>
            <div className="flex flex-wrap gap-2">
              {first.related.map((r) => (
                <button key={r} onClick={() => onSearch(r)} className="rounded-full border border-surface-200 px-3.5 py-1.5 text-sm hover:border-lapis-600 hover:text-lapis-600 dark:border-night-300">{r}</button>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

// ============================ الصور ============================
type Img = { id: number; image_url: string; page_url: string | null; host: string | null; width: number; height: number; format: string; alt: string; thumb: string; distance?: number };

export function ImageResults({ q, file }: { q: string; file: File | null }) {
  const { t } = usePrefs();
  const [size, setSize] = useState("");
  const [fmt, setFmt] = useState("");
  const [items, setItems] = useState<Img[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true); setErr("");
    const run = file
      ? (() => { const fd = new FormData(); fd.append("file", file); return upload<{ results: Img[] }>("/api/images/reverse", fd).then((r) => ({ results: r.results, total: r.results.length })); })()
      : q ? post<{ results: Img[]; total: number }>("/api/images", { q, size: size || null, format: fmt || null }) : Promise.resolve({ results: [], total: 0 });
    run.then((r) => { if (alive) { setItems(r.results); setTotal(r.total); } })
      .catch((e: ApiError) => alive && setErr(e.status === 422 ? "الملف ليس صورة صالحة" : e.message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [q, file, size, fmt]);

  const sel = "rounded-full border border-surface-200 bg-transparent px-3 py-1.5 text-sm text-ink-muted dark:border-night-300";
  return (
    <div>
      {!file && (
        <div className="mb-5 flex flex-wrap gap-2">
          <select aria-label={t.images.size} className={sel} value={size} onChange={(e) => setSize(e.target.value)}>
            <option value="">{t.images.any}</option><option value="small">{t.images.small}</option><option value="medium">{t.images.medium}</option><option value="large">{t.images.large}</option>
          </select>
          <select aria-label={t.images.type} className={sel} value={fmt} onChange={(e) => setFmt(e.target.value)}>
            <option value="">{t.images.allTypes}</option>{["jpeg", "png", "webp", "gif"].map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}
          </select>
        </div>
      )}
      {file && <p className="mb-4 flex items-center gap-2 text-sm text-ink-muted"><Upload className="h-4 w-4" />{t.images.similar} · {t.images.uploadHint}</p>}
      {err && <ErrorBox err={err} />}
      {loading ? <Spinner /> : !items.length && !err ? (
        <div className="py-16 text-center text-ink-muted"><ImageIcon className="mx-auto mb-3 h-8 w-8" />{t.noResults(file ? file.name : q)}</div>
      ) : (
        <>
          {!file && <p className="mb-3 text-sm text-ink-muted">{total.toLocaleString()} · <span className="text-emerald-600">{t.notStored}</span></p>}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {items.map((im) => (
              <a key={im.id} href={im.page_url ?? im.image_url} rel="noreferrer noopener" className="group overflow-hidden rounded-2xl border border-surface-200 bg-white dark:border-night-300 dark:bg-night-200">
                {/* المصغّرة من خادمنا: المتصفح لا يتصل بالموقع الأصلي */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={im.thumb} alt={im.alt} loading="lazy" className="aspect-[4/3] w-full object-cover transition group-hover:scale-[1.03]" />
                <div className="p-2.5 text-xs">
                  <div className="truncate font-medium">{im.alt || im.host}</div>
                  <div className="ltr-text mt-0.5 flex justify-between text-ink-faint"><span className="truncate">{im.host}</span><span>{im.width}×{im.height} {im.format}</span></div>
                  {im.distance !== undefined && <div className="mt-1 text-lapis-600">{t.images.distance} {Math.round((1 - im.distance / 64) * 100)}%</div>}
                </div>
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ============================ فحص الرابط ============================
type Inspect = {
  url: string; host: string; known: boolean; indexed_pages?: number; inbound_links?: number;
  domain?: { is_iraqi: boolean; status: string; category: string | null; reputation: number; authority: number; last_crawled_at: string | null; has_robots: boolean; robots_crawl_delay: number | null; first_seen_at: string };
  page?: { status: string; http_status: number; title: string | null; description: string | null; lang: string | null; indexed_at: string | null; last_crawled_at: string } | null;
  recent_pages?: { url: string; title: string; indexed_at: string }[];
};

export function UrlInspect({ initial }: { initial: string }) {
  const { t, lang } = usePrefs();
  const [url, setUrl] = useState(initial);
  const [data, setData] = useState<Inspect | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const run = useCallback(async (u: string) => {
    if (!u.trim()) return;
    setLoading(true); setErr("");
    try { setData(await post<Inspect>("/api/inspect", { url: u.trim() })); }
    catch (e) { setErr((e as Error).message); setData(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (initial) run(initial); }, [initial, run]);

  const stat = (label: string, v: React.ReactNode) => (
    <div className="rounded-2xl bg-surface-100 p-4 dark:bg-night-200"><div className="text-xs text-ink-muted">{label}</div><div className="mt-1 text-xl font-semibold">{v}</div></div>
  );
  return (
    <div className="max-w-3xl">
      <form onSubmit={(e) => { e.preventDefault(); run(url); }} className="flex gap-2">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={t.url.placeholder} aria-label={t.url.placeholder}
          className="ltr-text min-w-0 flex-1 rounded-full border border-surface-200 bg-white px-5 py-3 outline-none focus:border-lapis-600/50 focus:shadow-ring dark:border-night-300 dark:bg-night-200" />
        <button className="rounded-full bg-lapis-600 px-6 font-semibold text-white hover:bg-lapis-700">{t.url.inspect}</button>
      </form>
      <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-faint"><Info className="h-3.5 w-3.5" />{t.url.note}</p>
      {err && <div className="mt-4"><ErrorBox err={err} /></div>}
      {loading && <Spinner />}
      {data && !loading && (
        <div className="mt-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="ltr-text text-2xl font-semibold">{data.host}</h2>
            <a href={data.url} rel="noreferrer noopener" className="inline-flex items-center gap-1.5 text-sm text-lapis-600 hover:underline">{t.url.open}<ExternalLink className="h-4 w-4" /></a>
          </div>
          {!data.known ? <p className="text-ink-muted">{t.url.unknown}</p> : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {stat(t.url.indexedPages, data.indexed_pages?.toLocaleString())}
                {stat(t.url.inbound, data.inbound_links?.toLocaleString())}
                {stat(t.url.reputation, `${Math.round((data.domain?.reputation ?? 0) * 100)}%`)}
                {stat(t.url.lastCrawl, data.domain?.last_crawled_at ? fmtDate(data.domain.last_crawled_at, lang) : "—")}
              </div>
              <div className="flex flex-wrap gap-2 text-sm">
                <span className="rounded-full bg-surface-100 px-3 py-1 dark:bg-night-200">{t.url.robots}: {data.domain?.has_robots ? "✓" : "—"}{data.domain?.robots_crawl_delay ? ` · ${data.domain.robots_crawl_delay}s` : ""}</span>
                {data.domain?.is_iraqi && <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">.iq</span>}
                {data.domain?.category && <span className="rounded-full bg-surface-100 px-3 py-1 dark:bg-night-200">{t.cat[data.domain.category] ?? data.domain.category}</span>}
              </div>
              {data.page && (
                <div className="rounded-3xl border border-surface-200 p-5 dark:border-night-300">
                  <div className="text-xs font-semibold text-gold-600">{t.url.page} · {t.url.status}: {data.page.status} ({data.page.http_status})</div>
                  <div className="mt-1 text-lg font-semibold">{data.page.title}</div>
                  <p className="mt-1 text-sm text-ink-muted">{data.page.description}</p>
                </div>
              )}
              {!!data.recent_pages?.length && (
                <div>
                  <h3 className="mb-2 font-semibold">{t.url.recent}</h3>
                  <ul className="divide-y divide-surface-200 dark:divide-night-300">
                    {data.recent_pages.map((p) => (
                      <li key={p.url} className="py-2.5"><a href={p.url} rel="noreferrer noopener" className="text-lapis-700 hover:underline dark:text-lapis-400">{p.title || p.url}</a>
                        <div className="ltr-text truncate text-xs text-ink-faint">{p.url}</div></li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ============================ الترجمة ============================
const TR_LANGS = ["ar", "ckb", "kmr", "en", "tr", "fa", "fr", "de", "es", "ru", "zh"];
const TR_NAMES: Record<string, string> = { ar: "العربية", ckb: "کوردی", kmr: "Kurmancî", en: "English", tr: "Türkçe", fa: "فارسی", fr: "Français", de: "Deutsch", es: "Español", ru: "Русский", zh: "中文" };

export function Translate({ initial, available }: { initial: string; available: boolean }) {
  const { t, lang } = usePrefs();
  const [text, setText] = useState(initial);
  const [src, setSrc] = useState("");
  const [dst, setDst] = useState(lang === "ar" ? "en" : "ar");
  const [out, setOut] = useState("");
  const [detected, setDetected] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!text.trim()) { setDetected(""); return; }
    const id = setTimeout(() => post<{ language: string | null }>("/api/detect-language", { q: text.slice(0, 300) }).then((r) => setDetected(r.language ?? "")).catch(() => {}), 300);
    return () => clearTimeout(id);
  }, [text]);

  async function go() {
    setLoading(true); setErr(""); setOut("");
    try { setOut((await post<{ text: string }>("/api/translate", { text, source: src || null, target: dst })).text); }
    catch (e) { const a = e as ApiError; setErr(a.status === 503 ? t.tr.unavailable : a.message); }
    finally { setLoading(false); }
  }
  const sel = "rounded-full border border-surface-200 bg-transparent px-3 py-1.5 text-sm dark:border-night-300";
  return (
    <div>
      {!available && <div className="mb-4 flex items-start gap-2 rounded-2xl bg-gold-400/10 p-4 text-sm text-gold-600"><Languages className="mt-0.5 h-4 w-4 shrink-0" />{t.tr.unavailable}</div>}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select aria-label={t.tr.source} className={sel} value={src} onChange={(e) => setSrc(e.target.value)}>
          <option value="">{t.tr.auto}{detected && !src ? ` · ${TR_NAMES[detected] ?? detected}` : ""}</option>
          {TR_LANGS.map((l) => <option key={l} value={l}>{TR_NAMES[l]}</option>)}
        </select>
        <button aria-label="swap" onClick={() => { if (src) { setSrc(dst); setDst(src); setText(out); setOut(""); } }} className="rounded-full p-2 hover:bg-surface-100 dark:hover:bg-night-200"><ArrowLeftRight className="h-4 w-4" /></button>
        <select aria-label={t.tr.target} className={sel} value={dst} onChange={(e) => setDst(e.target.value)}>
          {TR_LANGS.map((l) => <option key={l} value={l}>{TR_NAMES[l]}</option>)}
        </select>
        <button onClick={go} disabled={!text.trim() || loading} className="ms-auto rounded-full bg-lapis-600 px-6 py-2 font-semibold text-white hover:bg-lapis-700 disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : t.tr.go}
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={5000} rows={9} aria-label={t.tr.source}
          className="rounded-3xl border border-surface-200 bg-white p-5 text-lg outline-none focus:border-lapis-600/50 focus:shadow-ring dark:border-night-300 dark:bg-night-200" />
        <div className="min-h-[14rem] rounded-3xl bg-surface-100 p-5 text-lg dark:bg-night-200" aria-live="polite">{out}</div>
      </div>
      {err && <div className="mt-3"><ErrorBox err={err} /></div>}
    </div>
  );
}
