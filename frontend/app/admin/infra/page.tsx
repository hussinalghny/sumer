"use client";

import { AlertTriangle, CheckCircle2, DatabaseBackup, RotateCw, XCircle } from "lucide-react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, bytes, Card, ErrorNote, Gauge, PageHead, Stat, Table, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Infra = {
  system: { cpu_percent: number; ram_percent: number; disk_percent: number; ram_used_mb: number; ram_total_mb: number; disk_used_gb: number; disk_total_gb: number; net_rx_kbps: number; net_tx_kbps: number; host: string };
  database: { ok: boolean; version?: string; size_mb?: number; connections?: number; error?: string };
  redis: { ok: boolean; version?: string; latency_ms?: number; used_memory_mb?: number; clients?: number; uptime_s?: number; error?: string };
  index: { ok: boolean; probe_ms?: number; gin_index_mb?: number; active_version?: { label: string } | null; error?: string };
  workers: Record<string, unknown>[]; queues: Record<string, unknown>[];
  docker: { available: boolean; reason?: string; containers?: Record<string, unknown>[] };
  backups: Record<string, unknown>[]; backup_encryption: { configured: boolean; algorithm: string; pg_dump_available: boolean };
  alerts: { level: string; key: string; value?: number }[]; version: string; migrations: { name: string; applied_at: string | null; pending: boolean }[]; env: string;
};

function Health({ name, ok, detail }: { name: string; ok: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-surface-200 p-4 dark:border-night-300">
      <div><div className="font-medium">{name}</div><div className="text-xs text-ink-muted">{detail}</div></div>
      {ok ? <CheckCircle2 className="h-6 w-6 text-emerald-500" /> : <XCircle className="h-6 w-6 text-red-500" />}
    </div>
  );
}

export default function Infra() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const { data: d, error, reload } = useAdmin<Infra>("/infra", 10000);
  const alive = d?.workers.filter((w) => w.alive).length ?? 0;
  return (
    <>
      <PageHead title={L("البنية التحتية", "System infrastructure")} desc={d ? `v${d.version} · ${d.env}` : undefined}
        actions={can("infra.control") && <>
          <Btn variant="outline" disabled={busy} onClick={() => run(() => admin("/infra/restart", { body: { service: "workers" } }), { ok: L("أُرسلت إشارة إعادة التشغيل للعمّال", "Restart signal sent to workers"),
            confirm: { title: L("إعادة تشغيل عمّال الزحف؟", "Restart crawler workers?"), body: L("ينهي كل عامل مهامه الحالية ثم يعيد Docker/systemd تشغيله.", "Each worker finishes its tasks, then Docker/systemd restarts it.") } })}><RotateCw className="h-4 w-4" />{L("إعادة تشغيل العمّال", "Restart workers")}</Btn>
          <Btn disabled={busy || !d?.backup_encryption.configured} title={!d?.backup_encryption.configured ? "SUMER_BACKUP_KEY" : undefined}
            onClick={() => run(() => admin("/backups", { body: {} }), { ok: L("بدأ النسخ الاحتياطي المشفّر", "Encrypted backup started") }).then(reload)}><DatabaseBackup className="h-4 w-4" />{L("نسخة احتياطية الآن", "Back up now")}</Btn></>} />
      <ErrorNote error={error} />
      {d && d.alerts.length > 0 && <div className="mb-5 space-y-2">{d.alerts.map((a) => <div key={a.key} className="flex items-center gap-2 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"><AlertTriangle className="h-4 w-4" />{a.key}{a.value != null && ` · ${a.value}`} <Badge value={a.level} /></div>)}</div>}
      {d && (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Health name="PostgreSQL" ok={d.database.ok} detail={d.database.ok ? `${d.database.version} · ${d.database.size_mb} MB · ${d.database.connections} conn` : d.database.error} />
            <Health name="Redis" ok={d.redis.ok} detail={d.redis.ok ? `v${d.redis.version} · ${d.redis.latency_ms} ms · ${d.redis.used_memory_mb} MB` : d.redis.error} />
            <Health name={L("فهرس البحث", "Search index")} ok={d.index.ok} detail={d.index.ok ? `${d.index.active_version?.label} · ${d.index.gin_index_mb} MB · ${d.index.probe_ms} ms` : d.index.error} />
            <Health name={L("عمّال الزحف", "Crawler workers")} ok={alive > 0} detail={`${alive} ${L("متصل", "online")}`} />
          </div>
          <div className="mt-5 grid gap-5 lg:grid-cols-3">
            <Card title={L("موارد الخادم", "Server resources")}>
              <div className="space-y-4">
                <Gauge label="CPU" value={d.system.cpu_percent} />
                <Gauge label="RAM" value={d.system.ram_percent} detail={`${bytes(d.system.ram_used_mb * 2 ** 20)} / ${bytes(d.system.ram_total_mb * 2 ** 20)}`} />
                <Gauge label={L("التخزين", "Storage")} value={d.system.disk_percent} detail={`${d.system.disk_used_gb} / ${d.system.disk_total_gb} GB`} />
                <div className="text-xs text-ink-muted">↓ {d.system.net_rx_kbps} KB/s · ↑ {d.system.net_tx_kbps} KB/s · <span className="ltr-text">{d.system.host}</span></div>
              </div>
            </Card>
            <Card title={L("الطوابير", "Queues")} className="lg:col-span-2">
              <Table rows={d.queues} cols={[{ key: "kind", label: L("النوع", "Kind") }, { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> }, { key: "n", label: L("العدد", "Count") }, { key: "oldest", label: L("الأقدم", "Oldest") }]} />
            </Card>
          </div>
          <Card title={L("حاويات Docker", "Docker containers")} className="mt-5">
            {d.docker.available ? <Table rows={d.docker.containers} cols={[{ key: "name", label: L("الاسم", "Name") }, { key: "image", label: L("الصورة", "Image") }, { key: "state", label: L("الحالة", "State"), render: (r) => <Badge value={String(r.state)} map={{ running: "good", exited: "bad" }} /> }, { key: "status", label: L("التفاصيل", "Details") }]} />
              : <p className="text-sm text-ink-muted">{d.docker.reason}</p>}
          </Card>
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Card title={L("النسخ الاحتياطية", "Backups")} actions={<Badge value={d.backup_encryption.configured ? d.backup_encryption.algorithm : "encryption not configured"} map={{ "encryption not configured": "bad" }} />}>
              <Table rows={d.backups} rowKey={(r) => Number(r.id)} cols={[{ key: "created_at", label: L("الوقت", "Time") }, { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> },
                { key: "bytes", label: L("الحجم", "Size"), render: (r) => bytes(r.bytes as number) }, { key: "encrypted", label: L("مشفّرة", "Encrypted") },
                { key: "sha256", label: "SHA-256", render: (r) => <code className="ltr-text text-[10px]">{String(r.sha256 ?? "").slice(0, 16)}</code> }, { key: "error", label: L("الخطأ", "Error") }]} />
              <p className="mt-2 text-xs text-ink-faint">{L("الاستعادة متعمدة من سطر الأوامر فقط: python -m sumer restore FILE --yes", "Restore is CLI-only by design: python -m sumer restore FILE --yes")}</p>
            </Card>
            <Card title={L("ترحيلات قاعدة البيانات", "Database migrations")}>
              <Table rows={d.migrations as unknown as Record<string, unknown>[]} cols={[{ key: "name", label: L("الملف", "File") }, { key: "pending", label: L("الحالة", "State"), render: (r) => <Badge value={r.pending ? "pending" : "applied"} map={{ applied: "good" }} /> }, { key: "applied_at", label: L("طُبّق", "Applied") }]} />
            </Card>
          </div>
          <div className="mt-5"><Stat label={L("إصدار التطبيق", "Application version")} value={`v${d.version}`} hint={d.env} /></div>
        </>
      )}
    </>
  );
}
