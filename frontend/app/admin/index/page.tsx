"use client";

import { Eye, Hammer, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, bytes, Card, ErrorNote, Field, Modal, PageHead, Pager, SearchInput, Stat, Table, Url, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Paged = { total: number; rows: Record<string, unknown>[] };

export default function IndexPage() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const manage = can("index.manage");
  const [q, setQ] = useState(""); const [lang, setLang] = useState(""); const [page, setPage] = useState(1);
  const docs = useAdmin<Paged>(`/index/documents?q=${encodeURIComponent(q)}&lang=${lang}&page=${page}`);
  const versions = useAdmin<Record<string, unknown>[]>("/index/versions", 10000);
  const [dupPage, setDupPage] = useState(1);
  const dups = useAdmin<Paged>(`/index/duplicates?page=${dupPage}`);
  const [errPage, setErrPage] = useState(1);
  const errors = useAdmin<Paged>(`/index/errors?page=${errPage}`);
  const storage = useAdmin<{ database: { size_mb: number; tables: { table: string; bytes: number }[] }; index: { gin_index_mb: number; total_mb: number; probe_ms: number; docs_needing_rebuild: number; active_version: Record<string, unknown> | null } }>("/index/storage");
  const domains = useAdmin<Paged>("/domains?page=1");
  const queue = useAdmin<Paged>("/crawler/jobs?status=pending&page=1", 10000);
  const [view, setView] = useState<Record<string, unknown> | null>(null);
  const [domainId, setDomainId] = useState("");
  const [days, setDays] = useState(180);

  const open = async (id: unknown) => { const r = await run(() => admin<Record<string, unknown>>(`/index/documents/${id}`)); if (r) setView(r); };
  const job = (path: string, body: unknown, ok: string, confirm?: { title: string; body?: string; danger?: boolean; typed?: string }) =>
    run(() => admin(path, { body }), { ok, confirm }).then(() => { versions.reload(); queue.reload(); });

  const ix = storage.data?.index;
  return (
    <>
      <PageHead title={L("إدارة الفهرس", "Index management")} desc={L("فهرس مقلوب GIN على PostgreSQL مع إصدارات قابلة لإعادة البناء", "GIN inverted index on PostgreSQL with rebuildable versions")} />
      <ErrorNote error={docs.error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label={L("المستندات", "Documents")} value={docs.data?.total.toLocaleString()} />
        <Stat label={L("حجم الفهرس المقلوب", "Inverted index size")} value={ix ? `${ix.gin_index_mb} MB` : "—"} />
        <Stat label={L("حجم المستندات الكلي", "Total documents size")} value={ix ? `${ix.total_mb} MB` : "—"} />
        <Stat label={L("زمن فحص الفهرس", "Index probe")} value={ix ? `${ix.probe_ms} ms` : "—"} />
        <Stat label={L("تحتاج إعادة بناء", "Need rebuild")} value={ix?.docs_needing_rebuild} tone={ix?.docs_needing_rebuild ? "warn" : "good"} />
      </div>

      {manage && (
        <Card title={L("عمليات الفهرس", "Index operations")} className="mt-5">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Field label={L("إعادة فهرسة نطاق", "Re-index a domain")}>
                <select className="input" value={domainId} onChange={(e) => setDomainId(e.target.value)}>
                  <option value="">{L("اختر نطاقاً", "Choose a domain")}</option>
                  {docs && domains.data?.rows.map((d) => <option key={String(d.id)} value={String(d.id)}>{String(d.host)}</option>)}
                </select></Field>
              <Btn variant="outline" disabled={!domainId || busy} onClick={() => job("/index/reindex-domain", { domain_id: Number(domainId) }, L("أُضيفت مهمة إعادة الفهرسة", "Re-index queued"))}><RefreshCw className="h-4 w-4" />{L("إعادة فهرسة", "Re-index")}</Btn>
            </div>
            <div className="space-y-2">
              <Field label={L("حذف المحتوى القديم (أيام بلا تحديث)", "Delete outdated content (days)")}><input type="number" min={1} max={3650} className="input" value={days} onChange={(e) => setDays(Number(e.target.value))} /></Field>
              <Btn variant="outline" disabled={busy} onClick={() => job("/index/delete-outdated", { days }, L("أُضيفت مهمة الحذف", "Deletion queued"),
                { title: L("حذف المستندات القديمة؟", "Delete outdated documents?"), body: L(`يُحذف من الفهرس كل ما لم يُحدّث منذ ${days} يوماً والصفحات المعطلة.`, `Removes documents not refreshed in ${days} days and broken pages.`), danger: true })}><Trash2 className="h-4 w-4" />{L("حذف", "Delete")}</Btn>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-ink-muted">{L("إعادة بناء الفهرس كاملاً بإصدار جديد من المحلّل، من النص المخزّن بدون إعادة زحف.", "Rebuild the whole index with the current analyzer from stored text, without re-crawling.")}</p>
              <div className="flex flex-wrap gap-2">
                <Btn variant="danger" disabled={busy} onClick={() => job("/index/rebuild", {}, L("بدأت إعادة البناء", "Rebuild started"),
                  { title: L("إعادة بناء الفهرس؟", "Rebuild the index?"), body: L("يُنشأ إصدار جديد ويُفعّل عند الاكتمال. البحث يستمر أثناءها.", "A new version is built and activated on completion. Search keeps working."), danger: true, typed: "REBUILD" })}><Hammer className="h-4 w-4" />{L("إعادة بناء", "Rebuild")}</Btn>
                <Btn variant="outline" size="sm" disabled={busy} onClick={() => job("/index/maintenance/refresh_terms", {}, L("أُضيفت", "Queued"))}>{L("تحديث القاموس", "Refresh vocabulary")}</Btn>
                <Btn variant="outline" size="sm" disabled={busy} onClick={() => job("/index/maintenance/compute_authority", {}, L("أُضيفت", "Queued"))}>{L("حساب السلطة", "Compute authority")}</Btn>
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card title={L("المستندات المفهرسة", "Indexed documents")} className="mt-5" actions={<>
        <div className="w-64"><SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder={L("بحث بالعنوان أو الرابط", "Search title or URL")} /></div>
        <select className="input w-32" value={lang} onChange={(e) => { setLang(e.target.value); setPage(1); }}><option value="">{L("كل اللغات", "All langs")}</option>{["ar", "ckb", "kmr", "en"].map((l) => <option key={l}>{l}</option>)}</select></>}>
        <Table rows={docs.data?.rows} rowKey={(r) => Number(r.page_id)} cols={[
          { key: "title", label: L("العنوان", "Title"), render: (r) => <div className="max-w-md"><div className="truncate font-medium">{String(r.title || "—")}</div><Url v={r.url} /></div> },
          { key: "lang", label: L("اللغة", "Lang") }, { key: "category", label: L("التصنيف", "Category") }, { key: "doc_type", label: L("النوع", "Type") },
          { key: "quality", label: L("الجودة", "Quality") }, { key: "spam_score", label: L("سبام", "Spam") },
          { key: "duplicate_of", label: L("مكرر", "Dup"), render: (r) => r.duplicate_of ? <Badge value="duplicate" /> : "—" },
          { key: "indexed_at", label: L("فُهرس", "Indexed") },
          { key: "x", label: "", render: (r) => <div className="flex">
            <Btn variant="ghost" size="sm" onClick={() => open(r.page_id)} aria-label="view"><Eye className="h-4 w-4" /></Btn>
            {manage && <Btn variant="ghost" size="sm" aria-label="delete" onClick={() => run(() => admin(`/index/documents/${r.page_id}`, { method: "DELETE" }),
              { ok: L("حُذف", "Deleted"), confirm: { title: L("حذف المستند من الفهرس؟", "Delete document from index?"), body: String(r.url), danger: true } }).then(() => docs.reload())}><Trash2 className="h-4 w-4" /></Btn>}</div> }]} />
        {docs.data && <Pager page={page} total={docs.data.total} onPage={setPage} />}
      </Card>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title={L("إصدارات الفهرس", "Index versions")}>
          <Table rows={versions.data} rowKey={(r) => Number(r.id)} cols={[{ key: "label", label: L("الإصدار", "Version") }, { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> },
            { key: "analyzer_version", label: L("المحلّل", "Analyzer") }, { key: "doc_count", label: L("مستندات", "Docs") }, { key: "created_at", label: L("أُنشئ", "Created") }, { key: "notes", label: L("ملاحظات", "Notes") }]} />
        </Card>
        <Card title={L("طابور الفهرسة", "Indexing queue")}>
          <Table rows={queue.data?.rows.slice(0, 10)} rowKey={(r) => Number(r.id)} cols={[{ key: "kind", label: L("النوع", "Kind") }, { key: "url", label: "URL", render: (r) => r.url ? <Url v={r.url} /> : "—" }, { key: "priority", label: L("الأولوية", "Priority") }, { key: "scheduled_at", label: L("موعد", "Scheduled") }]} />
          {queue.data && <p className="mt-2 text-xs text-ink-muted">{L("المجموع في الطابور", "Total queued")}: {queue.data.total}</p>}
        </Card>
        <Card title={L("الصفحات المكررة", "Duplicate documents")} actions={manage && <Btn variant="outline" size="sm" onClick={() => run(() => admin<{ deleted: number }>("/index/duplicates/purge", { body: {} }),
          { ok: L("حُذفت المكررات", "Duplicates purged"), confirm: { title: L("حذف كل المكررات من الفهرس؟", "Purge all duplicates?"), danger: true } }).then(() => dups.reload())}><Trash2 className="h-3.5 w-3.5" />{L("حذف الكل", "Purge")}</Btn>}>
          <Table rows={dups.data?.rows} rowKey={(r) => Number(r.page_id)} cols={[{ key: "url", label: L("المكرر", "Duplicate"), render: (r) => <Url v={r.url} /> }, { key: "original_url", label: L("الأصل", "Original"), render: (r) => <Url v={r.original_url} /> }]} />
          {dups.data && <Pager page={dupPage} total={dups.data.total} onPage={setDupPage} />}
        </Card>
        <Card title={L("أخطاء الفهرسة", "Indexing errors")}>
          <Table rows={errors.data?.rows} rowKey={(r) => Number(r.id)} cols={[{ key: "url", label: "URL", render: (r) => <Url v={r.url} /> }, { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> }, { key: "http_status", label: "HTTP" }, { key: "error", label: L("الخطأ", "Error") }]} />
          {errors.data && <Pager page={errPage} total={errors.data.total} onPage={setErrPage} />}
        </Card>
      </div>

      <Card title={L("توزيع التخزين", "Storage allocation")} className="mt-5">
        <Table rows={storage.data?.database.tables as unknown as Record<string, unknown>[] | undefined} cols={[{ key: "table", label: L("الجدول", "Table") }, { key: "bytes", label: L("الحجم", "Size"), render: (r) => bytes(Number(r.bytes)) }]} />
        {storage.data && <p className="mt-2 text-xs text-ink-muted">{L("حجم قاعدة البيانات", "Database size")}: {storage.data.database.size_mb} MB</p>}
      </Card>

      <Modal open={!!view} onClose={() => setView(null)} title={L("تفاصيل المستند", "Document details")} wide>
        {view && (() => { const d = view.document as Record<string, unknown>; return (
          <div className="space-y-3 text-sm">
            <Url v={d.url} />
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{["lang", "category", "doc_type", "word_count", "quality", "spam_score", "http_status", "crawl_status", "crawl_count", "analyzer_version", "last_crawled_at", "canonical_url"].map((k) =>
              <div key={k} className="rounded-xl bg-surface-100 p-2 dark:bg-night-300"><div className="text-[11px] text-ink-muted">{k}</div><div className="truncate">{String(d[k] ?? "—")}</div></div>)}</div>
            <div><b>{String(d.title)}</b><p className="text-ink-muted">{String(d.description)}</p></div>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-surface-100 p-3 text-xs dark:bg-night-300">{String(d.body_preview)}</pre>
            {(view.spam_signals as unknown[]).length > 0 && <Table rows={view.spam_signals as Record<string, unknown>[]} cols={[{ key: "signal", label: "signal" }, { key: "score", label: "score" }, { key: "details", label: "details" }]} />}
          </div>); })()}
      </Modal>
    </>
  );
}
