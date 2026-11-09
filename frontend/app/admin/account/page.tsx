"use client";

import QRCode from "qrcode";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Btn, Card, Field, PageHead, useAction, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

export default function Account() {
  const L = useL();
  const { me, refresh } = useMe();
  const { run, busy } = useAction();
  const [pw, setPw] = useState({ current: "", new: "", confirm: "" });
  const [setup, setSetup] = useState<{ secret: string; uri: string; qr: string } | null>(null);
  const [code, setCode] = useState("");

  return (
    <>
      <PageHead title={L("حسابي", "My account")} desc={`${me.user.name} · ${me.user.email} · ${me.user.role}`} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={L("تغيير كلمة المرور", "Change password")}>
          <form className="space-y-3" onSubmit={(e) => {
            e.preventDefault();
            if (pw.new !== pw.confirm) return;
            run(() => admin("/auth/password", { body: { current: pw.current, new: pw.new } }), { ok: L("تغيّرت كلمة المرور وأُلغيت جلساتك الأخرى", "Password changed; other sessions revoked") })
              .then((r) => { if (r) { setPw({ current: "", new: "", confirm: "" }); refresh(); } });
          }}>
            <Field label={L("الحالية", "Current")}><input type="password" autoComplete="current-password" required className="input" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></Field>
            <Field label={L("الجديدة", "New")} hint={L("12 حرفاً على الأقل، وتجمع 3 أنواع من: صغيرة، كبيرة، أرقام، رموز", "At least 12 characters mixing 3 of: lower, upper, digits, symbols")}>
              <input type="password" autoComplete="new-password" required minLength={12} className="input" value={pw.new} onChange={(e) => setPw({ ...pw, new: e.target.value })} /></Field>
            <Field label={L("تأكيد", "Confirm")}><input type="password" autoComplete="new-password" required className="input" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
            {pw.confirm && pw.new !== pw.confirm && <p className="text-sm text-red-600">{L("غير متطابقتين", "Passwords don't match")}</p>}
            <Btn disabled={busy}>{L("تغيير", "Change")}</Btn>
          </form>
        </Card>
        <Card title={L("التحقق بخطوتين", "Two-factor authentication")}>
          {me.user.totp_enabled && !setup ? (
            <div className="flex items-center gap-2 text-emerald-600"><ShieldCheck className="h-5 w-5" />{L("مفعّل على حسابك", "Enabled on your account")}</div>
          ) : !setup ? (
            <div className="space-y-3 text-sm">
              <p className="text-ink-muted">{L("استخدم أي تطبيق مصادقة (TOTP). السر يُخزّن مشفّراً على الخادم.", "Use any TOTP authenticator app. The secret is stored encrypted on the server.")}</p>
              <Btn onClick={async () => { const r = await run(() => admin<{ secret: string; uri: string }>("/auth/2fa/setup", { body: {} }));
                if (r) setSetup({ ...r, qr: await QRCode.toDataURL(r.uri, { margin: 1, width: 220 }) }); }}>{L("بدء الإعداد", "Start setup")}</Btn>
            </div>
          ) : (
            <div className="space-y-3 text-sm">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={setup.qr} alt="QR" className="rounded-xl bg-white p-2" width={220} height={220} />
              <p className="text-ink-muted">{L("أو أدخل السر يدوياً:", "Or enter the secret manually:")} <code className="ltr-text select-all">{setup.secret}</code></p>
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); run(() => admin("/auth/2fa/enable", { body: { code } }), { ok: L("فُعّل التحقق بخطوتين", "Two-factor enabled") }).then((r) => { if (r) { setSetup(null); refresh(); } }); }}>
                <input inputMode="numeric" maxLength={8} required placeholder="123456" className="input ltr-text w-40 text-center tracking-widest" value={code} onChange={(e) => setCode(e.target.value)} />
                <Btn disabled={busy}>{L("تأكيد", "Confirm")}</Btn>
              </form>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
