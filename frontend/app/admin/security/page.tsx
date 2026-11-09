"use client";

import { Brush, CheckCircle2, LogOut, Save, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, Card, ErrorNote, Field, PageHead, Pager, Switch, Table, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Sec = Record<string, number | boolean> & { privacy_guarantees: Record<string, boolean>; backup_encryption: { configured: boolean; algorithm: string; pg_dump_available: boolean } };
type Paged = { total: number; rows: Record<string, unknown>[] };

const KEYS: [string, string, string][] = [
  ["retention.crawl_logs_days", "الاحتفاظ بسجلات الزاحف (أيام)", "Crawler logs retention (days)"],
  ["retention.security_events_days", "الاحتفاظ بالأحداث الأمنية (أيام)", "Security events retention (days)"],
  ["retention.audit_logs_days", "الاحتفاظ بسجل التدقيق (أيام)", "Audit log retention (days)"],
  ["retention.ops_metrics_days", "الاحتفاظ بالتحليلات المجمّعة (أيام)", "Aggregate analytics retention (days)"],
  ["retention.temp_files_minutes", "حذف الملفات المؤقتة بعد (دقائق)", "Delete temp files after (minutes)"],
  ["ratelimit.search_per_minute", "حد البحث لكل عميل بالدقيقة", "Search rate limit per client/min"],
  ["ratelimit.upload_per_minute", "حد الرفع لكل عميل بالدقيقة", "Upload rate limit per client/min"],
  ["ratelimit.admin_login_per_15m", "محاولات دخول المشرفين لكل 15 دقيقة", "Admin login attempts per 15 min"],
];
const GUAR: Record<string, [string, string]> = {
  search_queries_stored: ["حفظ نصوص البحث", "Search queries stored"], visitor_ip_stored: ["حفظ عناوين IP للزوار", "Visitor IPs stored"],
  cookies_for_visitors: ["كوكيز للزوار", "Visitor cookies"], third_party_requests: ["طلبات لأطراف ثالثة", "Third-party requests"],
  uploads_written_to_disk: ["كتابة الصور المرفوعة على القرص", "Uploads written to disk"], audio_retained: ["الاحتفاظ بالصوت", "Audio retained"],
};

export default function Security() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const s = useAdmin<Sec>("/security/settings");
  const sessions = useAdmin<Record<string, unknown>[]>("/security/sessions", 15000);
  const [ep, setEp] = useState(1); const events = useAdmin<Paged>(`/security/events?page=${ep}`);
  const [ap, setAp] = useState(1); const access = useAdmin<Paged>(`/security/access-history?page=${ap}`);
  const [up, setUp] = useState(1); const [act, setAct] = useState("");
  const auditLog = useAdmin<Paged>(can("audit.view") ? `/audit?page=${up}&action=${act}` : null);
  const [draft, setDraft] = useState<Record<string, number | boolean>>({});
  useEffect(() => { if (s.data) setDraft(Object.fromEntries([...KEYS.map(([k]) => [k, s.data![k]]), ["security.require_2fa", !!s.data["security.require_2fa"]]])); }, [s.data]);
  const manage = can("security.manage");

  return (
    <>
      <PageHead title={L("مركز الخصوصية والأمن", "Privacy & security center")} actions={manage && <>
        <Btn variant="outline" onClick={() => run(() => admin<{ temp_files_deleted: number }>("/security/cleanup", { body: {} }), { ok: L("نُفّذ التنظيف وسياسات الاحتفاظ", "Cleanup and retention applied") })}><Brush className="h-4 w-4" />{L("تنظيف الآن", "Clean up now")}</Btn>
        <Btn disabled={busy} onClick={() => run(() => admin("/security/settings", { method: "PUT", body: { values: draft } }), { ok: L("حُفظت", "Saved") }).then(() => s.reload())}><Save className="h-4 w-4" />{L("حفظ", "Save")}</Btn></>} />
      <ErrorNote error={s.error} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title={L("ضمانات الخصوصية المفروضة تقنياً", "Technically enforced guarantees")}>
          <ul className="space-y-2 text-sm">
            {s.data && Object.entries(s.data.privacy_guarantees).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between gap-2"><span>{L(...(GUAR[k] ?? [k, k]))}</span>
                {v ? <XCircle className="h-5 w-5 text-red-500" /> : <span className="flex items-center gap-1 text-emerald-600"><CheckCircle2 className="h-5 w-5" />{L("لا", "No")}</span>}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-faint">{L("لا توجد في هذه اللوحة أي ميزة لعرض سجل بحث فرد أو بناء ملف عن مستخدم، ولا يوجد ما يُعرض أصلاً.", "This panel has no feature to view an individual's searches or profile a user, and there is no such data to show.")}</p>
        </Card>
        <Card title={L("الاحتفاظ وتحديد المعدل", "Retention & rate limits")} className="lg:col-span-2">
          <div className="grid gap-3 sm:grid-cols-2">
            {KEYS.map(([k, ar, en]) => (
              <Field key={k} label={L(ar, en)}><input type="number" min={1} className="input" disabled={!manage} value={Number(draft[k] ?? 0)} onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })} /></Field>
            ))}
          </div>
          <div className="mt-3 border-t border-surface-200 pt-3 dark:border-night-300">
            <Switch label={L("إلزام كل المشرفين بالتحقق بخطوتين", "Require two-factor for all administrators")} disabled={!manage} checked={!!draft["security.require_2fa"]} onChange={(b) => setDraft({ ...draft, "security.require_2fa": b })} />
            <div className="mt-2 flex items-center gap-2 text-sm">{L("تشفير النسخ الاحتياطية", "Backup encryption")}: <Badge value={s.data?.backup_encryption.configured ? `${s.data.backup_encryption.algorithm}` : "not configured"} map={{ "not configured": "bad" }} /></div>
          </div>
        </Card>
      </div>

      <Card title={L("جلسات المشرفين النشطة", "Active admin sessions")} className="mt-5">
        <Table rows={sessions.data} rowKey={(r) => String(r.id)} cols={[{ key: "email", label: L("المشرف", "Admin") }, { key: "ip", label: "IP" }, { key: "user_agent", label: L("المتصفح", "Browser"), render: (r) => <span className="line-clamp-1 max-w-xs text-xs">{String(r.user_agent)}</span> },
          { key: "mfa_passed", label: "2FA" }, { key: "created_at", label: L("بدأت", "Started") }, { key: "last_seen_at", label: L("آخر نشاط", "Last seen") },
          { key: "x", label: "", render: (r) => manage && <Btn variant="ghost" size="sm" onClick={() => run(() => admin(`/security/sessions/${r.id}`, { method: "DELETE" }), { ok: L("أُلغيت الجلسة", "Session revoked"), confirm: { title: L("إلغاء هذه الجلسة؟", "Revoke this session?"), danger: true } }).then(() => sessions.reload())}><LogOut className="h-4 w-4" /></Btn> }]} />
      </Card>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title={L("الأحداث الأمنية", "Security events")}>
          <Table rows={events.data?.rows} rowKey={(r) => Number(r.id)} cols={[{ key: "ts", label: L("الوقت", "Time") }, { key: "kind", label: L("الحدث", "Event"), render: (r) => <span className="flex items-center gap-1.5"><ShieldAlert className="h-3.5 w-3.5 text-ink-faint" />{String(r.kind)}</span> },
            { key: "severity", label: L("الخطورة", "Severity"), render: (r) => <Badge value={String(r.severity)} /> }, { key: "details", label: L("التفاصيل", "Details") }]} />
          {events.data && <Pager page={ep} total={events.data.total} onPage={setEp} />}
        </Card>
        <Card title={L("سجل دخول المشرفين", "Admin access history")}>
          <Table rows={access.data?.rows} rowKey={(r) => Number(r.id)} cols={[{ key: "ts", label: L("الوقت", "Time") }, { key: "admin_email", label: L("المشرف", "Admin") }, { key: "action", label: L("الإجراء", "Action") }, { key: "ip", label: "IP" }, { key: "success", label: L("نجح", "OK") }]} />
          {access.data && <Pager page={ap} total={access.data.total} onPage={setAp} />}
        </Card>
      </div>

      {can("audit.view") && (
        <Card title={L("سجل التدقيق", "Audit log")} className="mt-5" actions={<input className="input w-48" placeholder={L("تصفية بالإجراء", "Filter by action")} value={act} onChange={(e) => { setAct(e.target.value); setUp(1); }} />}>
          <Table rows={auditLog.data?.rows} rowKey={(r) => Number(r.id)} cols={[{ key: "ts", label: L("الوقت", "Time") }, { key: "admin_email", label: L("المشرف", "Admin") }, { key: "action", label: L("الإجراء", "Action") },
            { key: "target", label: L("الهدف", "Target") }, { key: "details", label: L("التفاصيل", "Details") }, { key: "ip", label: "IP" }, { key: "success", label: L("نجح", "OK") }]} />
          {auditLog.data && <Pager page={up} total={auditLog.data.total} onPage={setUp} />}
        </Card>
      )}
    </>
  );
}
