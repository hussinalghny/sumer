"use client";

import { Eye, FileWarning, Fingerprint, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Stats } from "@/lib/api";

export function Shield({ stats }: { stats: Stats }) {
  const n = (v?: number) => String(v ?? 0);
  const cards = [
    { v: n(stats.scanned), l: "رسالة فحصناها", c: "text-ink" },
    { v: n(stats.phishing), l: "رسالة تصيّد كشفناها", c: "text-danger-600" },
    { v: n(stats.trackers), l: "متتبّع فتح حجبناه", c: "text-lapis-600" },
    { v: n(stats.reported), l: "رسالة بلّغت عنها", c: "text-ok-600" },
  ];
  const feats = [
    { i: ShieldAlert, t: "كشف التصيّد والانتحال", d: "نفحص هوية المرسل، والنطاقات الشبيهة، والروابط المضلِّلة، ولغة الضغط بالعربي والإنكليزي." },
    { i: Eye, t: "حجب متتبّعات الفتح", d: "الصور الخارجية ما تنحمّل إلا إذا طلبت، فالمرسل ما يعرف متى فتحت رسالته." },
    { i: FileWarning, t: "فحص المرفقات", d: "البرامج والملفات المموّهة وصفحات الويب المرفقة تنحجب تلقائياً." },
    { i: Fingerprint, t: "بدون تخزين", d: "رسائلك ما تنحفظ عندنا. بيانات دخولك مشفّرة ومفتاحها بمتصفحك." },
  ];
  return (
    <div className="mx-auto w-full max-w-2xl flex-1 px-4 pb-28 pt-4 md:pt-6">
      <h1 className="text-[28px] font-bold md:text-3xl">الحماية</h1>
      <p className="mt-1 text-ink-muted">خلال هذه الجلسة</p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {cards.map((c) => <div key={c.l} className="card p-4"><b className={`block text-3xl ${c.c}`}>{c.v}</b><span className="text-sm text-ink-muted">{c.l}</span></div>)}
      </div>
      <h2 className="mb-2 mt-6 text-sm font-semibold text-ink-muted">الحماية التلقائية</h2>
      <ul className="card divide-y divide-surface-200 overflow-hidden dark:divide-night-300">
        {feats.map(({ i: I, t, d }) => (
          <li key={t} className="flex gap-3 p-4">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-lapis-50 text-lapis-600 dark:bg-lapis-900"><I className="h-5 w-5" /></span>
            <span><b className="block">{t}</b><span className="text-sm leading-6 text-ink-muted">{d}</span></span>
            <ShieldCheck className="ms-auto mt-1 h-5 w-5 shrink-0 text-ok-600" aria-label="مفعّل" />
          </li>
        ))}
      </ul>
    </div>
  );
}
