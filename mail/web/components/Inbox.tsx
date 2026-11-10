"use client";

import { AlertCircle, Paperclip, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Account, type Folder, type Stats, type Summary } from "@/lib/api";
import { AccountBadge, Avatar, fmtTime, LevelBadge, Spinner } from "./ui";

const FOLDERS: Record<Folder, string> = { inbox: "البريد الوارد", sent: "المرسل", junk: "غير المرغوب", trash: "المحذوفات" };

export function Inbox({ accounts, folder, stats, onOpen, onError }: {
  accounts: Account[]; folder: Folder; stats: Stats; onOpen: (m: Summary) => void; onError: (e: ApiError) => void;
}) {
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Summary[] | null>(null);
  const [errors, setErrors] = useState<{ email: string; message: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const byId = Object.fromEntries(accounts.map((a) => [a.id, a]));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({ folder, account: filter, q: query });
      const r = await api.get<{ messages: Summary[]; errors: { email: string; message: string }[] }>(`/api/messages?${p}`);
      setItems(r.messages); setErrors(r.errors);
    } catch (e) { onError(e as ApiError); } finally { setLoading(false); }
  }, [folder, filter, query, onError]);
  useEffect(() => { setItems(null); load(); }, [load]);

  const danger = items?.filter((m) => m.analysis?.level === "danger").length ?? 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="sticky top-0 z-10 bg-surface-100/90 px-4 pb-2 pt-4 backdrop-blur-xl dark:bg-night/90 md:pt-6">
        <div className="flex items-center justify-between">
          <h1 className="text-[28px] font-bold md:text-3xl">{FOLDERS[folder]}</h1>
          <button onClick={load} aria-label="تحديث" className="grid h-11 w-11 place-items-center rounded-full hover:bg-surface-200 dark:hover:bg-night-300">
            <RefreshCw className={`h-5 w-5 ${loading ? "animate-spin" : ""}`} /></button>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }} className="mt-2">
          <label className="flex h-10 items-center gap-2 rounded-xl bg-surface-200 px-3 text-ink-muted dark:bg-night-300">
            <Search className="h-4 w-4" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ابحث في كل حساباتك"
              className="min-w-0 flex-1 bg-transparent text-base text-ink outline-none dark:text-surface-100" aria-label="بحث" /></label>
        </form>
        {accounts.length > 1 && (
          <div className="no-scrollbar mt-3 flex gap-2 overflow-x-auto">
            {[{ id: "all", label: "الكل" }, ...accounts.map((a) => ({ id: a.id, label: a.provider === "custom" ? a.email.split("@")[1] : a.provider_name }))].map((c) => (
              <button key={c.id} onClick={() => setFilter(c.id)} aria-pressed={filter === c.id}
                className={`min-h-[36px] whitespace-nowrap rounded-full px-3.5 text-sm ${filter === c.id ? "bg-ink font-semibold text-white dark:bg-surface-100 dark:text-ink" : "bg-surface-200 dark:bg-night-300"}`}>{c.label}</button>
            ))}
          </div>
        )}
      </header>

      {folder === "inbox" && items && (
        <div className={`mx-4 mb-2 flex items-center gap-2 rounded-xl px-3 py-2.5 text-[13px] font-medium ${danger ? "bg-danger-50 text-danger-700" : "bg-ok-50 text-ok-600"}`}>
          {danger ? <AlertCircle className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
          {danger ? `الحماية مفعّلة — ${danger} ${danger === 1 ? "رسالة خطرة" : "رسائل خطرة"}` : `الحماية مفعّلة — فحصنا ${stats.scanned ?? items.length} رسالة`}
        </div>
      )}
      {errors.map((e) => <p key={e.email} className="mx-4 mb-2 rounded-xl bg-warn-50 p-3 text-sm text-warn-700"><b dir="ltr">{e.email}</b>: {e.message}</p>)}

      {!items ? <Spinner label="نجيب رسائلك…" /> : items.length === 0 ? (
        <p className="px-6 py-16 text-center text-ink-muted">{query ? `ماكو نتائج لـ «${query}»` : "ماكو رسائل هنا."}</p>
      ) : (
        <ul className="bg-white dark:bg-night-100 md:mx-4 md:rounded-2xl md:overflow-hidden">
          {items.map((m) => {
            const lvl = m.analysis?.level;
            const acc = byId[m.account_id];
            return (
              <li key={`${m.account_id}-${m.uid}`}>
                <button onClick={() => onOpen(m)}
                  className={`flex w-full items-start gap-3 border-b border-surface-200 px-4 py-3.5 text-start dark:border-night-300 ${lvl === "danger" ? "bg-danger-50 dark:bg-danger-700/20" : "hover:bg-surface-50 dark:hover:bg-night-200"}`}>
                  <span className={`mt-4 h-2 w-2 shrink-0 rounded-full ${m.seen ? "" : "bg-lapis-600"}`} />
                  <Avatar name={folder === "sent" ? m.to[0]?.name ?? "" : m.from.name} email={folder === "sent" ? m.to[0]?.email ?? "" : m.from.email} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className={`truncate text-base ${m.seen ? "font-medium" : "font-bold"}`}>{folder === "sent" ? `إلى: ${m.to.map((t) => t.name).join("، ")}` : m.from.name}</span>
                      <span className="shrink-0 text-[13px] text-ink-muted">{fmtTime(m.date)}</span>
                    </span>
                    <span dir="auto" className={`block truncate text-start text-[15px] ${m.seen ? "" : "font-semibold"}`}>{m.subject}</span>
                    <span dir="auto" className="block truncate text-start text-sm text-ink-muted">{m.snippet}</span>
                    <span className="mt-1 flex items-center gap-1.5">
                      {lvl && <LevelBadge level={lvl} />}<AccountBadge acc={acc} />
                      {m.has_attachments && <Paperclip className="h-3.5 w-3.5 text-ink-muted" aria-label="مرفق" />}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
