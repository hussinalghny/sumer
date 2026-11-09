"use client";

import { RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, bytes, Card, ErrorNote, PageHead, Pager, Stat, Table, Url, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

export default function Images() {
  const L = useL();
  const { can } = useMe();
  const { run } = useAction();
  const stats = useAdmin<{ by_status: { status: string; n: number }[]; by_format: { format: string; n: number }[]; queue: number }>("/images/stats", 10000);
  const [status, setStatus] = useState(""); const [page, setPage] = useState(1);
  const list = useAdmin<{ total: number; rows: Record<string, unknown>[] }>(`/images?status=${status}&page=${page}`);
  const n = (s: string) => stats.data?.by_status.find((x) => x.status === s)?.n ?? 0;
  return (
    <>
      <PageHead title={L("إدارة بحث الصور", "Image search")} desc={L("بصمة dHash للبحث العكسي وكشف التكرار، والمصغّرات تُخدم من خوادمنا", "dHash fingerprints for reverse search and dedupe; thumbnails served from our servers")}
        actions={can("images.manage") && <>
          <Btn variant="outline" onClick={() => run(() => admin<{ retried: number }>("/images/retry-failed", { body: {} }), { ok: L("أُعيدت الصور الفاشلة", "Failed images re-queued") }).then(() => { stats.reload(); list.reload(); })}><RotateCcw className="h-4 w-4" />{L("إعادة الفاشلة", "Retry failed")}</Btn>
          <Btn variant="outline" onClick={() => run(() => admin("/images/duplicates/purge", { body: {} }), { ok: L("حُذفت المكررات", "Duplicates removed"), confirm: { title: L("حذف كل الصور المكررة؟", "Remove all duplicate images?"), danger: true } }).then(() => { stats.reload(); list.reload(); })}><Trash2 className="h-4 w-4" />{L("حذف المكررات", "Remove duplicates")}</Btn></>} />
      <ErrorNote error={stats.error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label={L("مفهرسة", "Indexed")} value={n("ok")} tone="good" /><Stat label={L("طابور المعالجة", "Processing queue")} value={stats.data?.queue} />
        <Stat label={L("بانتظار", "Pending")} value={n("pending")} /><Stat label={L("فاشلة", "Failed")} value={n("failed")} tone={n("failed") ? "bad" : undefined} />
        <Stat label={L("مكررة", "Duplicates")} value={n("duplicate")} />
      </div>
      <Card title={L("حسب الصيغة", "By format")} className="mt-5">
        <div className="flex flex-wrap gap-2">{stats.data?.by_format.map((f) => <span key={f.format} className="rounded-full bg-surface-100 px-3 py-1 text-sm dark:bg-night-300">{f.format}: <b>{f.n}</b></span>)}</div>
      </Card>
      <Card title={L("الصور والبيانات الوصفية", "Images & metadata")} className="mt-5" actions={
        <select className="input w-36" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>{["", "ok", "pending", "failed", "duplicate", "blocked"].map((s) => <option key={s} value={s}>{s || L("الكل", "All")}</option>)}</select>}>
        <Table rows={list.data?.rows} rowKey={(r) => Number(r.id)} cols={[
          // eslint-disable-next-line @next/next/no-img-element
          { key: "thumb", label: "", render: (r) => r.status === "ok" || r.status === "duplicate" ? <img src={`/api/images/thumb/${r.id}`} alt="" className="h-10 w-14 rounded-lg object-cover" /> : null },
          { key: "image_url", label: "URL", render: (r) => <Url v={r.image_url} /> }, { key: "alt", label: L("النص البديل", "Alt") },
          { key: "dims", label: L("الأبعاد", "Size"), render: (r) => r.width ? `${r.width}×${r.height}` : "—" }, { key: "format", label: L("الصيغة", "Format") },
          { key: "bytes", label: L("الحجم", "Bytes"), render: (r) => bytes(r.bytes as number) }, { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> },
          { key: "error", label: L("الخطأ", "Error"), render: (r) => <span className="text-xs text-red-600">{String(r.error ?? "")}</span> }]} />
        {list.data && <Pager page={page} total={list.data.total} onPage={setPage} />}
      </Card>
    </>
  );
}
