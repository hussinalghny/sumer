"use client";

import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { Badge, bytes, Card, ErrorNote, Gauge, PageHead, Stat, Table, useAdmin, useL } from "@/components/admin/ui";

type Overview = {
  metrics: Record<string, number | null>;
  system: { cpu_percent: number; cpu_count: number; ram_used_mb: number; ram_total_mb: number; ram_percent: number; disk_used_gb: number;
    disk_total_gb: number; disk_percent: number; net_rx_kbps: number; net_tx_kbps: number; load_avg: number[]; host: string };
  uptime_s: number | null; workers: Record<string, string | boolean>[]; crawler_state: string;
  alerts: { level: string; key: string; value?: number }[]; health: Record<string, boolean>;
};

const ALERTS: Record<string, [string, string]> = {
  db_down: ["قاعدة البيانات لا تستجيب", "Database is down"], redis_down: ["Redis لا يستجيب", "Redis is down"],
  index_unhealthy: ["الفهرس غير سليم", "Index unhealthy"], disk_high: ["مساحة القرص مرتفعة", "Disk usage high"],
  ram_high: ["الذاكرة مرتفعة", "Memory usage high"], no_workers: ["لا يوجد عامل زحف يعمل", "No crawler workers running"],
  failed_jobs: ["مهام فاشلة كثيرة", "Many failed jobs"], index_rebuild_needed: ["مستندات تحتاج إعادة بناء الفهرس", "Documents need index rebuild"],
};

function uptime(s: number | null) {
  if (s == null) return "—";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

export default function Overview() {
  const L = useL();
  const { data, error } = useAdmin<Overview>("/overview", 10_000);
  const m = data?.metrics ?? {};
  const s = data?.system;
  return (
    <>
      <PageHead title={L("نظرة عامة", "Overview")} desc={L("تتحدّث كل 10 ثوانٍ من PostgreSQL وRedis والخادم", "Refreshes every 10 s from PostgreSQL, Redis and the host")}
        actions={data && <Badge value={data.crawler_state} />} />
      <ErrorNote error={error} />
      {data && data.alerts.length > 0 && (
        <div className="mb-5 space-y-2">
          {data.alerts.map((a) => (
            <div key={a.key} className={`flex items-center gap-2 rounded-2xl px-4 py-3 text-sm ${a.level === "critical" || a.level === "high" ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" : "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"}`}>
              <AlertTriangle className="h-4 w-4" />{L(...(ALERTS[a.key] ?? [a.key, a.key]))}{a.value != null && <b className="tabular-nums">· {a.value}</b>}
            </div>
          ))}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <Stat label={L("الصفحات المفهرسة", "Indexed pages")} value={m.indexed_pages?.toLocaleString()} />
        <Stat label={L("المواقع المفهرسة", "Indexed websites")} value={m.indexed_sites?.toLocaleString()} />
        <Stat label={L("نطاقات .iq", ".iq domains")} value={m.iraqi_domains?.toLocaleString()} />
        <Stat label={L("زُحف اليوم", "Crawled today")} value={m.crawled_today?.toLocaleString()} />
        <Stat label={L("فُهرس اليوم", "Indexed today")} value={m.indexed_today?.toLocaleString()} />
        <Stat label={L("مهام معلّقة", "Pending jobs")} value={m.pending_jobs?.toLocaleString()} hint={`${m.running_jobs ?? 0} ${L("قيد التنفيذ", "running")}`} />
        <Stat label={L("مهام فاشلة", "Failed jobs")} value={m.failed_jobs?.toLocaleString()} tone={(m.failed_jobs ?? 0) > 0 ? "bad" : undefined} />
        <Stat label={L("صور مفهرسة", "Indexed images")} value={m.indexed_images?.toLocaleString()} />
        <Stat label={L("مستندات PDF", "PDF documents")} value={m.indexed_documents?.toLocaleString()} />
        <Stat label={L("مدة التشغيل", "Uptime")} value={uptime(data?.uptime_s ?? null)} />
        <Stat label={L("متوسط زمن الاستجابة", "Avg response")} value={m.avg_response_ms != null ? `${m.avg_response_ms} ms` : "—"} hint={L("آخر 24 ساعة", "last 24h")} tone={m.avg_response_ms != null && m.avg_response_ms > 300 ? "warn" : "good"} />
        <Stat label={L("عمليات بحث 24س", "Searches 24h")} value={m.searches_24h?.toLocaleString()} hint={m.error_rate_24h != null ? `${L("أخطاء", "errors")} ${(m.error_rate_24h * 100).toFixed(2)}%` : undefined} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title={L("موارد الخادم", "Server resources")} className="lg:col-span-2">
          {s && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Gauge label={`CPU · ${s.cpu_count} cores`} value={s.cpu_percent} detail={`load ${s.load_avg.join(" / ")}`} />
              <Gauge label="RAM" value={s.ram_percent} detail={`${bytes(s.ram_used_mb * 2 ** 20)} / ${bytes(s.ram_total_mb * 2 ** 20)}`} />
              <Gauge label={L("القرص", "Disk")} value={s.disk_percent} detail={`${s.disk_used_gb} / ${s.disk_total_gb} GB`} />
              <div className="text-xs"><div className="mb-1 text-ink-muted">{L("الشبكة", "Network")}</div>
                <div className="tabular-nums">↓ {s.net_rx_kbps} KB/s · ↑ {s.net_tx_kbps} KB/s</div><div className="ltr-text mt-1 text-ink-faint">{s.host}</div></div>
            </div>
          )}
        </Card>
        <Card title={L("صحة الخدمات", "Service health")}>
          <ul className="space-y-2 text-sm">
            {data && Object.entries(data.health).map(([k, ok]) => (
              <li key={k} className="flex items-center justify-between"><span>{k}</span>{ok ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> : <XCircle className="h-5 w-5 text-red-500" />}</li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title={L("عمّال الزحف", "Crawler workers")} className="mt-5">
        <Table rows={data?.workers} empty={L("لا يوجد عامل متصل. شغّل: python -m sumer worker", "No worker connected. Run: python -m sumer worker")}
          cols={[{ key: "id", label: "ID", render: (r) => <span className="ltr-text">{String(r.id)}</span> },
            { key: "alive", label: L("الحالة", "State") }, { key: "active", label: L("مهام نشطة", "Active") },
            { key: "processed", label: L("منجزة", "Processed") }, { key: "seen", label: L("آخر نبضة", "Heartbeat"), render: (r) => new Date(Number(r.seen) * 1000).toLocaleTimeString() }]} />
      </Card>
    </>
  );
}
