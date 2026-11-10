"use client";

import { ChevronLeft, ExternalLink, KeyRound, Loader2, Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Account, type Provider } from "@/lib/api";

export function AddAccount({ onAdded, onCancel }: { onAdded: (a: Account) => void; onCancel?: () => void }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [p, setP] = useState<Provider | null>(null);
  const [f, setF] = useState({ email: "", password: "", display_name: "", username: "", imap_host: "", imap_port: "993", smtp_host: "", smtp_port: "465" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { api.get<{ providers: Provider[] }>("/api/providers").then((r) => setProviders(r.providers)).catch(() => {}); }, []);

  const custom = p?.id === "custom";
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const body: Record<string, unknown> = { email: f.email, password: f.password, provider: p!.id, display_name: f.display_name };
      if (custom) Object.assign(body, { username: f.username || null, imap_host: f.imap_host, imap_port: Number(f.imap_port), smtp_host: f.smtp_host, smtp_port: Number(f.smtp_port) });
      const r = await api.post<{ account: Account }>("/api/accounts", body);
      onAdded(r.account);
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  }

  if (!p) return (
    <div>
      <h2 className="mb-4 text-xl font-bold">اختار نوع البريد</h2>
      <div className="grid grid-cols-2 gap-3">
        {providers.map((x) => (
          <button key={x.id} onClick={() => !x.oauth_only && setP(x)} disabled={x.oauth_only}
            className="card flex min-h-[72px] flex-col items-start justify-center gap-0.5 border border-surface-200 px-4 py-3 text-start transition hover:border-lapis-600 disabled:opacity-60 dark:border-night-300">
            <span className="text-base font-semibold">{x.name}</span>
            {x.oauth_only && <span className="text-xs text-ink-muted">قريباً</span>}
            {x.id === "custom" && <span className="text-xs text-ink-muted">جامعة، مؤسسة، حكومي</span>}
          </button>
        ))}
        <div className="card flex min-h-[72px] flex-col items-start justify-center gap-0.5 border border-dashed border-gold-400/60 px-4 py-3">
          <span className="text-base font-semibold text-gold-600">سومر السيادي</span>
          <span className="text-xs text-ink-muted">قريباً: بريد مخزّن داخل العراق</span>
        </div>
      </div>
      {onCancel && <button onClick={onCancel} className="btn-ghost mt-4 w-full">إلغاء</button>}
    </div>
  );

  return (
    <form onSubmit={submit} className="space-y-3">
      <button type="button" onClick={() => { setP(null); setErr(""); }} className="flex min-h-[44px] items-center gap-1 text-lapis-600"><ChevronLeft className="h-5 w-5 rotate-180" />{p.name}</button>
      <div className="rounded-xl bg-lapis-50 p-3 text-sm leading-6 text-lapis-700 dark:bg-lapis-900 dark:text-lapis-100">
        <div className="flex items-start gap-2"><KeyRound className="mt-0.5 h-4 w-4 shrink-0" /><span>{p.help_ar}</span></div>
        {p.help_url && <a href={p.help_url} target="_blank" rel="noreferrer noopener" className="mt-1 inline-flex items-center gap-1 font-semibold underline">افتح الصفحة<ExternalLink className="h-3.5 w-3.5" /></a>}
      </div>
      <label className="block"><span className="mb-1 block text-sm font-medium">البريد الإلكتروني</span>
        <input className="field ltr text-left" dir="ltr" type="email" required autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="you@example.com" /></label>
      <label className="block"><span className="mb-1 block text-sm font-medium">{p.app_password ? "كلمة مرور التطبيق" : "كلمة المرور"}</span>
        <input className="field" dir="ltr" type="password" required autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
      <label className="block"><span className="mb-1 block text-sm font-medium">اسمك عند الإرسال <span className="text-ink-muted">(اختياري)</span></span>
        <input className="field" value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></label>
      {custom && (
        <div className="space-y-3 rounded-xl border border-surface-200 p-3 dark:border-night-300">
          <div className="grid grid-cols-[1fr_88px] gap-2">
            <label><span className="mb-1 block text-sm font-medium">خادم IMAP</span><input className="field" dir="ltr" required value={f.imap_host} onChange={(e) => setF({ ...f, imap_host: e.target.value })} placeholder="imap.uni.edu.iq" /></label>
            <label><span className="mb-1 block text-sm font-medium">المنفذ</span><input className="field" dir="ltr" inputMode="numeric" value={f.imap_port} onChange={(e) => setF({ ...f, imap_port: e.target.value })} /></label>
          </div>
          <div className="grid grid-cols-[1fr_88px] gap-2">
            <label><span className="mb-1 block text-sm font-medium">خادم SMTP</span><input className="field" dir="ltr" required value={f.smtp_host} onChange={(e) => setF({ ...f, smtp_host: e.target.value })} placeholder="smtp.uni.edu.iq" /></label>
            <label><span className="mb-1 block text-sm font-medium">المنفذ</span><input className="field" dir="ltr" inputMode="numeric" value={f.smtp_port} onChange={(e) => setF({ ...f, smtp_port: e.target.value })} /></label>
          </div>
          <label className="block"><span className="mb-1 block text-sm font-medium">اسم المستخدم <span className="text-ink-muted">(إذا يختلف عن البريد)</span></span>
            <input className="field" dir="ltr" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></label>
        </div>
      )}
      {err && <p role="alert" className="rounded-xl bg-danger-50 p-3 text-sm text-danger-700">{err}</p>}
      <button className="btn-primary w-full" disabled={busy}>{busy ? <Loader2 className="h-5 w-5 animate-spin" /> : null}{busy ? "نتحقق من الحساب…" : "أضف الحساب"}</button>
      <p className="flex items-start gap-2 text-xs leading-5 text-ink-muted"><Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" />كلمة المرور تنحفظ مشفّرة، ومفتاح فك تشفيرها موجود بس بمتصفحك. ما نخزن رسائلك أبداً.</p>
    </form>
  );
}
