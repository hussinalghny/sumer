"use client";

import { Save, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Btn, Card, ErrorNote, Field, PageHead, Switch, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Site = { "site.name_ar": string; "site.name_en": string; "site.tagline_ar": string; "site.tagline_en": string; "site.default_lang": string;
  "site.default_theme": string; "site.maintenance": boolean; "site.announcement": { enabled: boolean; ar: string; en: string }; "site.logo_path": string | null };

export default function Settings() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const { data, error, reload } = useAdmin<Site>("/settings/site");
  const [d, setD] = useState<Site | null>(null);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => { if (data) setD(data); }, [data]);
  const manage = can("settings.manage");
  if (!d) return <ErrorNote error={error} />;
  const { "site.logo_path": _logo, ...values } = d;
  const save = () => run(() => admin("/settings/site", { method: "PUT", body: { values } }), {
    ok: L("حُفظت الإعدادات", "Settings saved"),
    confirm: d["site.maintenance"] && !data?.["site.maintenance"] ? { title: L("تفعيل وضع الصيانة؟", "Enable maintenance mode?"), body: L("يتوقف البحث العام فوراً لكل المستخدمين.", "Public search stops immediately for everyone."), danger: true } : undefined,
  }).then(reload);
  const txt = (k: keyof Site, label: string, ltr?: boolean) => (
    <Field label={label}><input className={`input ${ltr ? "ltr-text" : ""}`} disabled={!manage} maxLength={300} value={String(d[k] ?? "")} onChange={(e) => setD({ ...d, [k]: e.target.value })} /></Field>
  );
  return (
    <>
      <PageHead title={L("الإعدادات والصيانة", "Configuration & maintenance")} actions={manage && <Btn onClick={save} disabled={busy}><Save className="h-4 w-4" />{L("حفظ", "Save")}</Btn>} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={L("هوية المحرك", "Branding")}>
          <div className="grid gap-3">
            {txt("site.name_ar", L("الاسم بالعربية", "Name (Arabic)"))}{txt("site.name_en", L("الاسم بالإنكليزية", "Name (English)"), true)}
            {txt("site.tagline_ar", L("الشعار بالعربية", "Tagline (Arabic)"))}{txt("site.tagline_en", L("الشعار بالإنكليزية", "Tagline (English)"), true)}
            <div className="flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {d["site.logo_path"] ? <img src={`/api/public/logo?v=${d["site.logo_path"]}`} alt="" className="h-14 w-14 rounded-2xl object-cover" /> : <div className="grid h-14 w-14 place-items-center rounded-2xl bg-surface-100 text-xs text-ink-faint dark:bg-night-300">{L("افتراضي", "Default")}</div>}
              {manage && <><Btn variant="outline" onClick={() => file.current?.click()}><Upload className="h-4 w-4" />{L("رفع شعار", "Upload logo")}</Btn>
                <input ref={file} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => {
                  const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append("file", f);
                  run(() => admin("/settings/logo", { form: fd }), { ok: L("حُدّث الشعار", "Logo updated") }).then(reload); e.target.value = ""; }} /></>}
            </div>
            <p className="text-xs text-ink-faint">{L("يُعاد ترميز الشعار PNG على الخادم، ولا يُقبل SVG لمنع تضمين سكربتات.", "The logo is re-encoded to PNG server-side; SVG is rejected to prevent script injection.")}</p>
          </div>
        </Card>
        <Card title={L("اللغة والسمة", "Language & theme")}>
          <div className="grid gap-3">
            <Field label={L("اللغة الافتراضية", "Default language")}><select className="input" disabled={!manage} value={d["site.default_lang"]} onChange={(e) => setD({ ...d, "site.default_lang": e.target.value })}>
              <option value="ar">العربية</option><option value="en">English</option><option value="ckb">کوردی</option></select></Field>
            <Field label={L("السمة الافتراضية", "Default theme")}><select className="input" disabled={!manage} value={d["site.default_theme"]} onChange={(e) => setD({ ...d, "site.default_theme": e.target.value })}>
              <option value="system">{L("حسب الجهاز", "System")}</option><option value="light">{L("فاتح", "Light")}</option><option value="dark">{L("داكن", "Dark")}</option></select></Field>
          </div>
        </Card>
        <Card title={L("وضع الصيانة", "Maintenance mode")}>
          <Switch label={L("إيقاف البحث العام مؤقتاً للصيانة", "Temporarily stop public search for maintenance")} disabled={!manage} checked={d["site.maintenance"]} onChange={(b) => setD({ ...d, "site.maintenance": b })} />
        </Card>
        <Card title={L("إعلان على الصفحة الرئيسية", "Homepage announcement")}>
          <Switch label={L("إظهار الإعلان", "Show announcement")} disabled={!manage} checked={d["site.announcement"].enabled} onChange={(b) => setD({ ...d, "site.announcement": { ...d["site.announcement"], enabled: b } })} />
          <div className="mt-3 grid gap-3">
            <Field label={L("النص بالعربية", "Arabic text")}><input className="input" disabled={!manage} maxLength={200} value={d["site.announcement"].ar} onChange={(e) => setD({ ...d, "site.announcement": { ...d["site.announcement"], ar: e.target.value } })} /></Field>
            <Field label={L("النص بالإنكليزية", "English text")}><input className="input ltr-text" disabled={!manage} maxLength={200} value={d["site.announcement"].en} onChange={(e) => setD({ ...d, "site.announcement": { ...d["site.announcement"], en: e.target.value } })} /></Field>
          </div>
        </Card>
      </div>
      <p className="mt-5 text-sm text-ink-muted">{L("النسخ الاحتياطي وحالة الترحيلات وإصدار التطبيق في صفحة البنية التحتية.", "Backups, migration status and application version are on the Infrastructure page.")}</p>
    </>
  );
}
