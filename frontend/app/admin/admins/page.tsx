"use client";

import { Copy, KeyRound, LogOut, Plus, UserCheck, UserX } from "lucide-react";
import { useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, Card, ErrorNote, Field, Modal, PageHead, Table, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Role = { id: number; name: string; label_ar: string; label_en: string; permissions: string[] };

export default function Admins() {
  const L = useL();
  const { me, can } = useMe();
  const { run, busy } = useAction();
  const list = useAdmin<Record<string, unknown>[]>("/admins");
  const roles = useAdmin<Role[]>("/roles");
  const perms = useAdmin<string[]>("/permissions");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", name: "", role: "auditor" });
  const [temp, setTemp] = useState("");
  const manage = can("admins.manage");
  const isSuper = me.user.role === "super_admin";
  const roleLabel = (n: string) => { const r = roles.data?.find((x) => x.name === n); return r ? L(r.label_ar, r.label_en) : n; };

  const togglePerm = (r: Role, p: string) => {
    const next = r.permissions.includes(p) ? r.permissions.filter((x) => x !== p) : [...r.permissions, p];
    run(() => admin(`/roles/${r.id}`, { method: "PUT", body: { permissions: next } }), { ok: L("حُدّثت الصلاحيات", "Permissions updated") }).then(() => roles.reload());
  };

  return (
    <>
      <PageHead title={L("المشرفون والأدوار", "Administrators & roles")} desc={L("صلاحيات بمبدأ الحد الأدنى، تُفحص بالخلفية لكل طلب", "Least-privilege permissions, enforced server-side on every request")}
        actions={manage && <Btn onClick={() => { setForm({ email: "", name: "", role: "auditor" }); setTemp(""); setOpen(true); }}><Plus className="h-4 w-4" />{L("مشرف جديد", "New administrator")}</Btn>} />
      <ErrorNote error={list.error} />
      <Card>
        <Table rows={list.data} rowKey={(r) => Number(r.id)} cols={[
          { key: "name", label: L("الاسم", "Name"), render: (r) => <div><div className="font-medium">{String(r.name)}</div><div className="ltr-text text-xs text-ink-muted">{String(r.email)}</div></div> },
          { key: "role", label: L("الدور", "Role"), render: (r) => manage && r.id !== me.user.id && (isSuper || r.role !== "super_admin") ? (
            <select className="input w-44" defaultValue={String(r.role)} onChange={(e) => run(() => admin(`/admins/${r.id}`, { method: "PATCH", body: { role: e.target.value } }), { ok: L("تغيّر الدور", "Role changed") }).then(() => list.reload())}>
              {roles.data?.filter((x) => isSuper || x.name !== "super_admin").map((x) => <option key={x.name} value={x.name}>{L(x.label_ar, x.label_en)}</option>)}
            </select>) : roleLabel(String(r.role)) },
          { key: "status", label: L("الحالة", "Status"), render: (r) => <Badge value={String(r.status)} /> },
          { key: "totp_enabled", label: "2FA" }, { key: "active_sessions", label: L("جلسات", "Sessions") }, { key: "last_login_at", label: L("آخر دخول", "Last login") },
          { key: "x", label: "", render: (r) => manage && r.id !== me.user.id && (isSuper || r.role !== "super_admin") && (
            <div className="flex">
              {r.status === "active"
                ? <Btn variant="ghost" size="sm" title={L("تعليق", "Suspend")} onClick={() => run(() => admin(`/admins/${r.id}`, { method: "PATCH", body: { status: "suspended" } }), { ok: L("عُلّق الحساب وأُلغيت جلساته", "Suspended; sessions revoked"), confirm: { title: L("تعليق هذا المشرف؟", "Suspend this administrator?"), body: String(r.email), danger: true } }).then(() => list.reload())}><UserX className="h-4 w-4" /></Btn>
                : <Btn variant="ghost" size="sm" title={L("تفعيل", "Activate")} onClick={() => run(() => admin(`/admins/${r.id}`, { method: "PATCH", body: { status: "active" } }), { ok: L("فُعّل", "Activated") }).then(() => list.reload())}><UserCheck className="h-4 w-4" /></Btn>}
              <Btn variant="ghost" size="sm" title={L("إلغاء كل الجلسات", "Revoke all sessions")} onClick={() => run(() => admin(`/admins/${r.id}/revoke-sessions`, { body: {} }), { ok: L("أُلغيت الجلسات", "Sessions revoked") }).then(() => list.reload())}><LogOut className="h-4 w-4" /></Btn>
              <Btn variant="ghost" size="sm" title={L("إعادة ضبط 2FA", "Reset 2FA")} onClick={() => run(() => admin(`/admins/${r.id}/reset-2fa`, { body: {} }), { ok: L("أُعيد ضبط التحقق بخطوتين", "2FA reset"), confirm: { title: L("إعادة ضبط التحقق بخطوتين؟", "Reset two-factor?"), body: L("سيحتاج المشرف لإعداده من جديد.", "The admin will need to set it up again."), danger: true } }).then(() => list.reload())}><KeyRound className="h-4 w-4" /></Btn>
            </div>) }]} />
      </Card>

      <Card title={L("مصفوفة الصلاحيات", "Permission matrix")} className="mt-5">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-xs">
            <thead><tr><th className="p-2 text-start">{L("الصلاحية", "Permission")}</th>{roles.data?.map((r) => <th key={r.id} className="p-2 text-center font-medium">{L(r.label_ar, r.label_en)}</th>)}</tr></thead>
            <tbody>{perms.data?.map((p) => (
              <tr key={p} className="border-t border-surface-100 dark:border-night-200"><td className="ltr-text p-2 font-mono">{p}</td>
                {roles.data?.map((r) => <td key={r.id} className="p-2 text-center">
                  <input type="checkbox" aria-label={`${r.name} ${p}`} className="accent-lapis-600" checked={r.permissions.includes(p)} disabled={!isSuper || r.name === "super_admin" || busy} onChange={() => togglePerm(r, p)} />
                </td>)}</tr>))}</tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-faint">{L("المشرف الأعلى فقط يعدّل الصلاحيات، ودور المشرف الأعلى ثابت.", "Only a super administrator can edit permissions; the super administrator role is fixed.")}</p>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title={L("مشرف جديد", "New administrator")}>
        {temp ? (
          <div className="space-y-3 text-sm">
            <p>{L("أُنشئ الحساب. هذه كلمة المرور المؤقتة وتظهر مرة واحدة فقط، وسيُطلب تغييرها عند أول دخول:", "Account created. This temporary password is shown once and must be changed at first sign-in:")}</p>
            <div className="flex items-center gap-2 rounded-xl bg-surface-100 p-3 dark:bg-night-300"><code className="ltr-text flex-1 text-base">{temp}</code>
              <Btn variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(temp).catch(() => {})}><Copy className="h-4 w-4" /></Btn></div>
            <Btn className="w-full" onClick={() => setOpen(false)}>{L("تم", "Done")}</Btn>
          </div>
        ) : (
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const r = await run(() => admin<{ temporary_password: string }>("/admins", { body: form })); if (r) { setTemp(r.temporary_password); list.reload(); } }}>
            <Field label={L("البريد", "Email")}><input type="email" required className="input ltr-text" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label={L("الاسم", "Name")}><input required minLength={2} className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label={L("الدور", "Role")}><select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {roles.data?.filter((x) => isSuper || x.name !== "super_admin").map((x) => <option key={x.name} value={x.name}>{L(x.label_ar, x.label_en)}</option>)}</select></Field>
            <Btn className="w-full" disabled={busy}>{L("إنشاء", "Create")}</Btn>
          </form>
        )}
      </Modal>
    </>
  );
}
