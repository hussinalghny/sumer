"use client";

import { Pause, Pencil, Play, Plus, RotateCcw, Square, Trash2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, Card, ErrorNote, Field, Modal, PageHead, Pager, SearchInput, Stat, Switch, Table, Url, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Status = { state: string; concurrency: number; follow_external: boolean; default_depth: number; discovery_mode: string; new_domain_budget: number; max_pending_per_domain: number;
  discovery: { domains_total: number; discovered_24h: number; iraqi_total: number; crawled_domains: number };
  workers: Record<string, unknown>[]; progress: Record<string, number>; robots: Record<string, number>; hourly: { hour: string; fetched: number; errors: number }[] };
type Domain = { id: number; host: string; is_iraqi: boolean; status: string; block_reason: string | null; category: string | null; reputation: number; authority: number;
  crawl_depth: number; crawl_frequency_h: number; min_delay_ms: number; max_pages: number; render_js: boolean; excluded_paths: string[]; page_count: number; error_count: number; last_crawled_at: string | null };
type Paged<T> = { total: number; rows: T[] };

export default function Crawler() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const st = useAdmin<Status>("/crawler/status", 8000);
  const seeds = useAdmin<Record<string, unknown>[]>("/crawler/seeds");
  const [dq, setDq] = useState(""); const [dstatus, setDstatus] = useState(""); const [dpage, setDpage] = useState(1);
  const domains = useAdmin<Paged<Domain>>(`/domains?q=${encodeURIComponent(dq)}&status=${dstatus}&page=${dpage}`);
  const [jstatus, setJstatus] = useState("failed"); const [jpage, setJpage] = useState(1);
  const jobs = useAdmin<Paged<Record<string, unknown>>>(`/crawler/jobs?status=${jstatus}&page=${jpage}`);
  const [lev, setLev] = useState(""); const [lpage, setLpage] = useState(1);
  const logs = useAdmin<Paged<Record<string, unknown>>>(`/crawler/logs?level=${lev}&page=${lpage}`, 15000);
  const [seed, setSeed] = useState("");
  const [edit, setEdit] = useState<Domain | null>(null);
  const [cfg, setCfg] = useState({ concurrency: 8, default_depth: 3, discovery_mode: "iraq", new_domain_budget: 200, max_pending_per_domain: 500 });
  useEffect(() => { if (st.data) setCfg({ concurrency: st.data.concurrency, default_depth: st.data.default_depth, discovery_mode: st.data.discovery_mode,
    new_domain_budget: st.data.new_domain_budget, max_pending_per_domain: st.data.max_pending_per_domain }); },
    [st.data?.concurrency, st.data?.default_depth, st.data?.discovery_mode, st.data?.new_domain_budget, st.data?.max_pending_per_domain]); // eslint-disable-line

  const setState = (state: string) => run(() => admin("/crawler/state", { body: { state } }), {
    ok: L("تم تغيير حالة الزاحف", "Crawler state changed"),
    confirm: state === "stopped" ? { title: L("إيقاف الزاحف بالكامل؟", "Stop the crawler completely?"), body: L("العمّال يتوقفون عن كل المهام، بما فيها الصيانة.", "Workers stop claiming all jobs, including maintenance."), danger: true } : undefined,
  }).then(() => st.reload());

  const p = st.data?.progress ?? {};
  const r = st.data?.robots ?? {};
  return (
    <>
      <PageHead title={L("إدارة الزاحف", "Crawler management")} desc={L("يحترم robots.txt وcrawl-delay ومحمي من SSRF", "Respects robots.txt and crawl-delay; SSRF-protected")}
        actions={can("crawler.control") && <>
          <Btn variant={st.data?.state === "running" ? "primary" : "outline"} onClick={() => setState("running")} disabled={busy}><Play className="h-4 w-4" />{L("تشغيل", "Start")}</Btn>
          <Btn variant="outline" onClick={() => setState("paused")} disabled={busy}><Pause className="h-4 w-4" />{L("إيقاف مؤقت", "Pause")}</Btn>
          <Btn variant="outline" onClick={() => setState("stopped")} disabled={busy}><Square className="h-4 w-4" />{L("إيقاف", "Stop")}</Btn></>} />
      <ErrorNote error={st.error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Stat label={L("الحالة", "State")} value={st.data && <Badge value={st.data.state} />} />
        <Stat label={L("عمّال متصلون", "Workers online")} value={st.data?.workers.filter((w) => w.alive).length} />
        <Stat label={L("في الطابور", "Queued")} value={p.pending?.toLocaleString()} />
        <Stat label={L("قيد التنفيذ", "Running")} value={p.running} />
        <Stat label={L("منجزة 24س", "Done 24h")} value={p.done_24h?.toLocaleString()} />
        <Stat label={L("ممنوعة بـ robots (7 أيام)", "robots.txt blocked (7d)")} value={r.blocked_by_robots} />
        <Stat label={L("طلبات SSRF محجوبة", "SSRF blocked")} value={r.ssrf_blocked} tone={r.ssrf_blocked ? "warn" : undefined} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={L("وضع الاكتشاف", "Discovery mode")} value={st.data && <Badge value={st.data.discovery_mode === "open" ? L("الويب كله", "Whole web") : L("العراق", "Iraq")} map={{ "الويب كله": "good", "Whole web": "good" }} />} />
        <Stat label={L("مواقع معروفة", "Known sites")} value={st.data?.discovery.domains_total.toLocaleString()} hint={`${st.data?.discovery.iraqi_total ?? 0} .iq`} />
        <Stat label={L("مواقع زُحفت", "Sites crawled")} value={st.data?.discovery.crawled_domains.toLocaleString()} />
        <Stat label={L("اكتُشفت آخر 24 ساعة", "Discovered last 24h")} value={st.data?.discovery.discovered_24h.toLocaleString()} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title={L("الأداء خلال 24 ساعة", "Last 24 hours")} className="lg:col-span-2">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={(st.data?.hourly ?? []).map((h) => ({ ...h, hour: new Date(h.hour).getHours() + ":00" }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#8884" vertical={false} /><XAxis dataKey="hour" fontSize={11} /><YAxis fontSize={11} allowDecimals={false} />
                <Tooltip /><Bar dataKey="fetched" name={L("صفحات", "Pages")} fill="#2447c8" radius={[4, 4, 0, 0]} /><Bar dataKey="errors" name={L("أخطاء", "Errors")} fill="#dc2626" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title={L("الإعدادات العامة", "Global settings")}>
          <div className="space-y-3">
            <Field label={L("عدد المهام المتزامنة لكل عامل", "Concurrent tasks per worker")}><input type="number" min={1} max={256} className="input" disabled={!can("crawler.manage")} value={cfg.concurrency} onChange={(e) => setCfg({ ...cfg, concurrency: Number(e.target.value) })} /></Field>
            <Field label={L("العمق الافتراضي للنطاقات الجديدة", "Default depth for new domains")}><input type="number" min={0} max={20} className="input" disabled={!can("crawler.manage")} value={cfg.default_depth} onChange={(e) => setCfg({ ...cfg, default_depth: Number(e.target.value) })} /></Field>
            <Field label={L("وضع الاكتشاف", "Discovery mode")} hint={cfg.discovery_mode === "open"
              ? L("يتبع الروابط لأي موقع بالعالم، مثل Google. المواقع العراقية تأخذ أولوية أعلى بالطابور.", "Follows links to any site, like Google. Iraqi sites get higher queue priority.")
              : L("يزحف المواقع العراقية (.iq) وروابط البداية فقط.", "Crawls Iraqi (.iq) sites and seed URLs only.")}>
              <select className="input" disabled={!can("crawler.manage")} value={cfg.discovery_mode} onChange={(e) => setCfg({ ...cfg, discovery_mode: e.target.value })}>
                <option value="iraq">{L("العراق وروابط البداية", "Iraq + seeds")}</option>
                <option value="open">{L("الويب كله (اكتشاف تلقائي)", "Whole web (auto-discovery)")}</option>
              </select></Field>
            <Field label={L("ميزانية أولية لكل موقع مكتشف (صفحات)", "Initial budget per discovered site (pages)")} hint={L("تكبر تلقائياً مع سلطة الموقع", "Grows automatically with site authority")}>
              <input type="number" min={1} className="input" disabled={!can("crawler.manage")} value={cfg.new_domain_budget} onChange={(e) => setCfg({ ...cfg, new_domain_budget: Number(e.target.value) })} /></Field>
            <Field label={L("أقصى مهام معلّقة لكل موقع", "Max pending jobs per site")}>
              <input type="number" min={10} className="input" disabled={!can("crawler.manage")} value={cfg.max_pending_per_domain} onChange={(e) => setCfg({ ...cfg, max_pending_per_domain: Number(e.target.value) })} /></Field>
            {can("crawler.manage") && <Btn onClick={() => run(() => admin("/crawler/config", { method: "PUT", body: cfg }), { ok: L("حُفظت", "Saved"), confirm: cfg.discovery_mode === "open" && st.data?.discovery_mode !== "open" ? { title: L("تفعيل الاكتشاف التلقائي للويب كله؟", "Enable whole-web discovery?"),
              body: L("الزاحف سيتبع الروابط لأي موقع بالعالم. يحتاج سعة تخزين وباندويث أكبر بكثير.", "The crawler will follow links to any site. This needs far more storage and bandwidth.") } : undefined }).then(() => st.reload())}>{L("حفظ", "Save")}</Btn>}
          </div>
        </Card>
      </div>

      <Card title={L("روابط البداية (Seeds)", "Seed URLs")} className="mt-5">
        {can("crawler.manage") && (
          <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); run(() => admin("/crawler/seeds", { body: { url: seed } }), { ok: L("أُضيف وبدأ زحفه", "Added and queued") }).then(() => { setSeed(""); seeds.reload(); }); }}>
            <input value={seed} onChange={(e) => setSeed(e.target.value)} className="input ltr-text" placeholder="https://www.example.gov.iq/" required />
            <Btn disabled={busy}><Plus className="h-4 w-4" />{L("إضافة", "Add")}</Btn>
          </form>
        )}
        <Table rows={seeds.data} rowKey={(r) => Number(r.id)} cols={[{ key: "url", label: "URL", render: (r) => <Url v={r.url} /> }, { key: "page_count", label: L("صفحات", "Pages") },
          { key: "added_at", label: L("أُضيف", "Added") },
          { key: "x", label: "", render: (r) => can("crawler.manage") && <Btn variant="ghost" size="sm" aria-label="remove" onClick={() => run(() => admin(`/crawler/seeds/${r.id}`, { method: "DELETE" }),
            { ok: L("حُذف", "Removed"), confirm: { title: L("حذف رابط البداية؟", "Remove seed?"), body: String(r.url) } }).then(() => seeds.reload())}><Trash2 className="h-4 w-4" /></Btn> }]} />
      </Card>

      <Card title={L("النطاقات", "Domains")} className="mt-5" actions={<>
        <div className="w-56"><SearchInput value={dq} onChange={(v) => { setDq(v); setDpage(1); }} placeholder={L("بحث بالنطاق", "Search host")} /></div>
        <select className="input w-36" value={dstatus} onChange={(e) => { setDstatus(e.target.value); setDpage(1); }}>
          <option value="">{L("كل الحالات", "All")}</option><option value="active">active</option><option value="paused">paused</option><option value="blocked">blocked</option></select></>}>
        <Table rows={domains.data?.rows as unknown as Record<string, unknown>[] | undefined} rowKey={(r) => Number(r.id)} cols={[
          { key: "host", label: L("النطاق", "Host"), render: (r) => <span className="ltr-text font-medium">{String(r.host)}{r.is_iraqi ? " 🇮🇶" : ""}</span> },
          { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> },
          { key: "page_count", label: L("صفحات", "Pages") }, { key: "reputation", label: L("السمعة", "Reputation") },
          { key: "crawl_depth", label: L("العمق", "Depth") }, { key: "crawl_frequency_h", label: L("التكرار (س)", "Freq (h)") },
          { key: "min_delay_ms", label: L("مهلة (مللي)", "Delay ms") }, { key: "error_count", label: L("أخطاء", "Errors") },
          { key: "last_crawled_at", label: L("آخر زحف", "Last crawl") },
          { key: "x", label: "", render: (r) => can("crawler.manage") && <Btn variant="ghost" size="sm" onClick={() => setEdit(r as unknown as Domain)} aria-label="edit"><Pencil className="h-4 w-4" /></Btn> }]} />
        {domains.data && <Pager page={dpage} total={domains.data.total} onPage={setDpage} />}
      </Card>

      <Card title={L("مهام الزحف", "Crawl jobs")} className="mt-5" actions={<>
        <select className="input w-36" value={jstatus} onChange={(e) => { setJstatus(e.target.value); setJpage(1); }}>
          {["failed", "pending", "running", "done", "cancelled", ""].map((s) => <option key={s} value={s}>{s || L("الكل", "All")}</option>)}</select>
        {can("crawler.control") && <Btn variant="outline" size="sm" onClick={() => run(() => admin<{ retried: number }>("/crawler/jobs/retry", { body: { all_failed: true } }), { ok: L("أُعيدت المهام الفاشلة للطابور", "Failed jobs re-queued") }).then(() => jobs.reload())}>
          <RotateCcw className="h-3.5 w-3.5" />{L("إعادة كل الفاشلة", "Retry all failed")}</Btn>}</>}>
        <Table rows={jobs.data?.rows} rowKey={(r) => Number(r.id)} cols={[{ key: "id", label: "#" }, { key: "kind", label: L("النوع", "Kind") },
          { key: "url", label: "URL", render: (r) => r.url ? <Url v={r.url} /> : "—" }, { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> },
          { key: "attempts", label: L("محاولات", "Attempts") }, { key: "error", label: L("الخطأ", "Error"), render: (r) => <span className="line-clamp-2 max-w-xs text-xs text-red-600">{String(r.error ?? "")}</span> },
          { key: "scheduled_at", label: L("موعد", "Scheduled") },
          { key: "x", label: "", render: (r) => can("crawler.control") && (r.status === "failed" || r.status === "cancelled"
            ? <Btn variant="ghost" size="sm" onClick={() => run(() => admin("/crawler/jobs/retry", { body: { ids: [r.id] } }), { ok: L("أُعيدت", "Re-queued") }).then(() => jobs.reload())}><RotateCcw className="h-4 w-4" /></Btn>
            : r.status === "pending" ? <Btn variant="ghost" size="sm" onClick={() => run(() => admin("/crawler/jobs/cancel", { body: { ids: [r.id] } }), { ok: L("أُلغيت", "Cancelled") }).then(() => jobs.reload())}><XCircle className="h-4 w-4" /></Btn> : null) }]} />
        {jobs.data && <Pager page={jpage} total={jobs.data.total} onPage={setJpage} />}
      </Card>

      <Card title={L("سجل الزاحف والأخطاء", "Crawler log & errors")} className="mt-5" actions={
        <select className="input w-32" value={lev} onChange={(e) => { setLev(e.target.value); setLpage(1); }}><option value="">{L("الكل", "All")}</option><option value="error">error</option><option value="warn">warn</option><option value="info">info</option></select>}>
        <Table rows={logs.data?.rows} rowKey={(r) => Number(r.id)} cols={[{ key: "ts", label: L("الوقت", "Time") }, { key: "level", label: L("المستوى", "Level"), render: (r) => <Badge value={String(r.level)} map={{ error: "bad", warn: "warn", info: "info" }} /> },
          { key: "event", label: L("الحدث", "Event") }, { key: "url", label: "URL", render: (r) => r.url ? <Url v={r.url} /> : "—" }, { key: "http_status", label: "HTTP" },
          { key: "duration_ms", label: "ms" }, { key: "message", label: L("التفاصيل", "Details"), render: (r) => <span className="text-xs text-ink-muted">{String(r.message ?? "")}</span> }]} />
        {logs.data && <Pager page={lpage} total={logs.data.total} onPage={setLpage} />}
      </Card>

      <DomainEditor domain={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); domains.reload(); }} />
    </>
  );
}

function DomainEditor({ domain, onClose, onSaved }: { domain: Domain | null; onClose: () => void; onSaved: () => void }) {
  const L = useL();
  const { run, busy } = useAction();
  const [d, setD] = useState<Domain | null>(domain);
  const [paths, setPaths] = useState("");
  useEffect(() => { setD(domain); setPaths(domain?.excluded_paths.join("\n") ?? ""); }, [domain]);
  if (!d) return <Modal open={false} onClose={onClose} title="">{null}</Modal>;
  const num = (k: keyof Domain, label: string, min: number, max: number) => (
    <Field label={label}><input type="number" min={min} max={max} className="input" value={Number(d[k])} onChange={(e) => setD({ ...d, [k]: Number(e.target.value) })} /></Field>
  );
  return (
    <Modal open={!!domain} onClose={onClose} title={d.host} wide>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={L("الحالة", "Status")}><select className="input" value={d.status} onChange={(e) => setD({ ...d, status: e.target.value })}>
          <option value="active">{L("نشط", "Active")}</option><option value="paused">{L("موقوف مؤقتاً", "Paused")}</option><option value="blocked">{L("محظور", "Blocked")}</option></select></Field>
        <Field label={L("سبب الحظر", "Block reason")}><input className="input" value={d.block_reason ?? ""} onChange={(e) => setD({ ...d, block_reason: e.target.value })} /></Field>
        {num("crawl_depth", L("عمق الزحف", "Crawl depth"), 0, 20)}
        {num("crawl_frequency_h", L("تكرار الزحف (ساعات)", "Crawl frequency (hours)"), 1, 8760)}
        {num("min_delay_ms", L("أقل مهلة بين الطلبات (مللي ثانية)", "Min delay between requests (ms)"), 100, 600000)}
        {num("max_pages", L("أقصى عدد صفحات", "Max pages"), 1, 10000000)}
        <Field label={L("التصنيف", "Category")}><select className="input" value={d.category ?? ""} onChange={(e) => setD({ ...d, category: e.target.value || null })}>
          <option value="">{L("تلقائي", "Automatic")}</option>{["gov", "academic", "news", "tech", "business", "local"].map((c) => <option key={c}>{c}</option>)}</select></Field>
        <div className="pt-6"><Switch label={L("تصيير JavaScript (Playwright)", "Render JavaScript (Playwright)")} checked={d.render_js} onChange={(b) => setD({ ...d, render_js: b })} /></div>
        <Field label={L("مسارات مستثناة (سطر لكل مسار)", "Excluded paths (one per line)")} hint="/admin/  /login">
          <textarea rows={4} className="input ltr-text" value={paths} onChange={(e) => setPaths(e.target.value)} /></Field>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Btn variant="ghost" onClick={onClose}>{L("إلغاء", "Cancel")}</Btn>
        <Btn disabled={busy} onClick={() => run(() => admin(`/domains/${d.id}`, { method: "PATCH", body: {
          status: d.status, block_reason: d.block_reason, category: d.category ?? "", crawl_depth: d.crawl_depth, crawl_frequency_h: d.crawl_frequency_h,
          min_delay_ms: d.min_delay_ms, max_pages: d.max_pages, render_js: d.render_js, excluded_paths: paths.split("\n").map((s) => s.trim()).filter(Boolean) } }),
          { ok: L("حُفظ النطاق", "Domain saved"), confirm: d.status === "blocked" && domain?.status !== "blocked" ? { title: L("حظر النطاق؟", "Block this domain?"), body: L("تُلغى كل مهامه المعلّقة.", "All its pending jobs are cancelled."), danger: true } : undefined }).then((r) => r !== undefined && onSaved())}>
          {L("حفظ", "Save")}</Btn>
      </div>
    </Modal>
  );
}
