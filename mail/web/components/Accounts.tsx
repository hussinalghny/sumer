"use client";

import { LogOut, MapPin, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type Account } from "@/lib/api";
import { AddAccount } from "./AddAccount";
import { Avatar } from "./ui";

function where(a: Account) {
  if (a.sovereign) return "مخزّن داخل العراق";
  return ({ gmail: "مخزّن لدى Google · خارج العراق", yahoo: "مخزّن لدى Yahoo · خارج العراق", icloud: "مخزّن لدى Apple · خارج العراق" } as Record<string, string>)[a.provider] ?? `خادم ${a.imap_host}`;
}

export function Accounts({ accounts, onChanged, onLogout, onError }: { accounts: Account[]; onChanged: () => void; onLogout: () => void; onError: (e: ApiError) => void }) {
  const [adding, setAdding] = useState(false);
  async function remove(a: Account) {
    if (!confirm(`نشيل ${a.email} من سومر بريد؟ رسائلك تبقى بحسابك الأصلي.`)) return;
    try { const r = await api.del<{ session: boolean }>(`/api/accounts/${a.id}`); r.session ? onChanged() : onLogout(); } catch (e) { onError(e as ApiError); }
  }
  return (
    <div className="mx-auto w-full max-w-2xl flex-1 px-4 pb-28 pt-4 md:pt-6">
      <h1 className="text-[28px] font-bold md:text-3xl">الحسابات</h1>
      <section className="mt-4 rounded-3xl bg-lapis-900 p-5 text-white">
        <div className="flex items-center justify-between"><span className="font-display text-2xl">سومر بريد</span>
          <span className="rounded-md bg-gold-400 px-2 py-0.5 text-xs font-bold text-lapis-900">سيادي · قريباً</span></div>
        <p className="mt-2 text-sm leading-6 text-[#c7cdf0]">حساب بريد على <span dir="ltr">sumeriq.tech</span>، رسائله مخزّنة داخل العراق ومشفّرة. تكدر تنقل له بريدك القديم بضغطة.</p>
        <p className="mt-3 flex items-center gap-1.5 text-xs text-[#e3b04b]"><MapPin className="h-3.5 w-3.5" />قيد التجهيز</p>
      </section>
      <h2 className="mb-2 mt-6 text-sm font-semibold text-ink-muted">حسابات مربوطة</h2>
      <ul className="card divide-y divide-surface-200 overflow-hidden dark:divide-night-300">
        {accounts.map((a) => (
          <li key={a.id} className="flex items-center gap-3 p-4">
            <Avatar name={a.display_name || a.email} email={a.email} size={40} />
            <div className="min-w-0 flex-1">
              <div className="font-semibold">{a.provider === "custom" ? "بريد " + a.email.split("@")[1] : a.provider_name}</div>
              <div className="truncate text-sm text-ink-muted" dir="ltr" style={{ textAlign: "right" }}>{a.email}</div>
              <div className={`mt-0.5 flex items-center gap-1 text-xs ${a.sovereign ? "font-semibold text-gold-600" : "text-ink-muted"}`}><MapPin className="h-3 w-3" />{where(a)}</div>
            </div>
            <button onClick={() => remove(a)} aria-label={`إزالة ${a.email}`} className="grid h-11 w-11 place-items-center rounded-full text-ink-muted hover:bg-danger-50 hover:text-danger-600"><Trash2 className="h-5 w-5" /></button>
          </li>
        ))}
      </ul>
      {adding ? (
        <div className="card mt-4 p-4"><AddAccount onAdded={() => { setAdding(false); onChanged(); }} onCancel={() => setAdding(false)} /></div>
      ) : (
        <button onClick={() => setAdding(true)} className="btn mt-4 w-full border border-dashed border-surface-300 text-lapis-600 dark:border-night-400"><Plus className="h-5 w-5" />أضف حساباً</button>
      )}
      <p className="mt-4 text-xs leading-5 text-ink-muted">سومر بريد ما يخزّن رسائلك. بيانات الدخول محفوظة مشفّرة، ومفتاحها بمتصفحك فقط، وتنتهي الجلسة تلقائياً.</p>
      <button onClick={onLogout} className="btn-ghost mt-2 w-full text-danger-600"><LogOut className="h-4 w-4" />خروج من كل الحسابات</button>
    </div>
  );
}
