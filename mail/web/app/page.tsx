"use client";

import { Inbox as InboxIcon, Mail, PenSquare, Send, Shield as ShieldIcon, ShieldAlert, Trash2, UserRound, Lock, EyeOff, Layers } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Accounts } from "@/components/Accounts";
import { AddAccount } from "@/components/AddAccount";
import { Compose } from "@/components/Compose";
import { Inbox } from "@/components/Inbox";
import { MessageView } from "@/components/MessageView";
import { Shield } from "@/components/Shield";
import { Spinner, Wordmark } from "@/components/ui";
import { api, type ApiError, type Folder, type Message, type SessionInfo, type Summary } from "@/lib/api";

type Tab = "mail" | "shield" | "accounts";

export default function Home() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [tab, setTab] = useState<Tab>("mail");
  const [folder, setFolder] = useState<Folder>("inbox");
  const [open, setOpen] = useState<Summary | null>(null);
  const [compose, setCompose] = useState<{ reply?: Message | null } | null>(null);
  const [toast, setToast] = useState("");
  const [nonce, setNonce] = useState(0);

  const refresh = useCallback(() => api.get<SessionInfo>("/api/session").then(setSession).catch(() => setSession({ active: false, accounts: [], stats: {} })), []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(""), 3500); return () => clearTimeout(t); } }, [toast]);

  const onError = useCallback((e: ApiError) => {
    if (e.status === 401) { setSession({ active: false, accounts: [], stats: {} }); return; }
    setToast(e.message);
  }, []);
  const logout = async () => { await api.post("/api/session/logout").catch(() => {}); setOpen(null); setTab("mail"); setSession({ active: false, accounts: [], stats: {} }); };

  if (!session) return <Spinner />;
  if (!session.active) return <Welcome onAdded={() => refresh()} />;

  const acc = (id: string) => session.accounts.find((a) => a.id === id);
  const go = (t: Tab) => { setTab(t); setOpen(null); if (t !== "mail") refresh(); };

  const folders: { k: Folder; label: string; icon: typeof InboxIcon }[] = [
    { k: "inbox", label: "الوارد", icon: InboxIcon }, { k: "sent", label: "المرسل", icon: Send },
    { k: "junk", label: "غير المرغوب", icon: ShieldAlert }, { k: "trash", label: "المحذوفات", icon: Trash2 },
  ];

  return (
    <div className="flex min-h-full">
      {/* شريط جانبي للحاسبة */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-e border-surface-200 bg-surface-50 p-4 dark:border-night-300 dark:bg-night-100 md:flex">
        <Wordmark className="px-2 text-2xl" />
        <button onClick={() => setCompose({})} className="btn-primary mt-6 w-full"><PenSquare className="h-4 w-4" />رسالة جديدة</button>
        <nav className="mt-6 space-y-1" aria-label="المجلدات">
          {folders.map(({ k, label, icon: I }) => (
            <button key={k} onClick={() => { setFolder(k); go("mail"); }} aria-current={tab === "mail" && folder === k}
              className={`flex min-h-[44px] w-full items-center gap-3 rounded-xl px-3 text-start ${tab === "mail" && folder === k ? "bg-lapis-50 font-semibold text-lapis-700 dark:bg-lapis-900 dark:text-lapis-100" : "hover:bg-surface-200 dark:hover:bg-night-300"}`}>
              <I className="h-5 w-5" />{label}</button>
          ))}
        </nav>
        <nav className="mt-auto space-y-1">
          <button onClick={() => go("shield")} className={`flex min-h-[44px] w-full items-center gap-3 rounded-xl px-3 ${tab === "shield" ? "bg-lapis-50 font-semibold text-lapis-700 dark:bg-lapis-900" : "hover:bg-surface-200 dark:hover:bg-night-300"}`}><ShieldIcon className="h-5 w-5" />الحماية</button>
          <button onClick={() => go("accounts")} className={`flex min-h-[44px] w-full items-center gap-3 rounded-xl px-3 ${tab === "accounts" ? "bg-lapis-50 font-semibold text-lapis-700 dark:bg-lapis-900" : "hover:bg-surface-200 dark:hover:bg-night-300"}`}><UserRound className="h-5 w-5" />الحسابات</button>
        </nav>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        {tab === "mail" && (open
          ? <MessageView summary={open} account={acc(open.account_id)} onBack={() => setOpen(null)} onError={onError}
              onReply={(m) => setCompose({ reply: m })} onChanged={() => { setNonce((n) => n + 1); setToast("تم"); }} />
          : <>
              {/* مجلدات الموبايل */}
              <div className="no-scrollbar flex gap-2 overflow-x-auto px-4 pt-3 md:hidden">
                {folders.map(({ k, label }) => (
                  <button key={k} onClick={() => setFolder(k)} className={`min-h-[34px] whitespace-nowrap rounded-full px-3 text-sm ${folder === k ? "bg-lapis-600 font-semibold text-white" : "text-ink-muted"}`}>{label}</button>
                ))}
              </div>
              <Inbox key={`${folder}-${nonce}`} accounts={session.accounts} folder={folder} stats={session.stats} onError={onError}
                onOpen={(m) => setOpen(m)} />
            </>)}
        {tab === "shield" && <Shield stats={session.stats} />}
        {tab === "accounts" && <Accounts accounts={session.accounts} onChanged={refresh} onLogout={logout} onError={onError} />}
      </main>

      {/* زر الكتابة وشريط التبويب للموبايل */}
      {tab === "mail" && !open && (
        <button onClick={() => setCompose({})} aria-label="رسالة جديدة" className="fixed bottom-24 left-5 z-20 grid h-14 w-14 place-items-center rounded-full bg-lapis-600 text-white shadow-lg md:hidden"><PenSquare className="h-6 w-6" /></button>
      )}
      <nav aria-label="التنقل" className="fixed inset-x-0 bottom-0 z-20 flex justify-around border-t border-surface-200 bg-surface-50/95 pb-[env(safe-area-inset-bottom)] pt-1.5 backdrop-blur-xl dark:border-night-300 dark:bg-night-100/95 md:hidden">
        {([["mail", Mail, "البريد"], ["shield", ShieldIcon, "الحماية"], ["accounts", UserRound, "الحسابات"]] as const).map(([k, I, l]) => (
          <button key={k} onClick={() => go(k)} aria-current={tab === k}
            className={`flex min-h-[50px] min-w-[72px] flex-col items-center justify-center gap-0.5 text-[11px] ${tab === k ? "font-semibold text-lapis-600" : "text-ink-muted"}`}><I className="h-6 w-6" />{l}</button>
        ))}
      </nav>

      {compose && <Compose accounts={session.accounts} reply={compose.reply} onClose={() => setCompose(null)}
        onSent={() => { setCompose(null); setToast("انرسلت الرسالة"); }} />}
      {toast && <div role="status" className="fixed bottom-28 left-1/2 z-50 -translate-x-1/2 rounded-full bg-ink px-4 py-2.5 text-sm text-white shadow-lg dark:bg-surface-100 dark:text-ink md:bottom-8">{toast}</div>}
    </div>
  );
}

function Welcome({ onAdded }: { onAdded: () => void }) {
  const points = [
    { i: Layers, t: "كل بريدك بمكان واحد", d: "Gmail وYahoo وiCloud وبريد الجامعة أو الدائرة." },
    { i: ShieldAlert, t: "حماية من التصيّد", d: "ننبّهك بالعربي إذا المرسل منتحل أو الرابط مزيّف أو المرفق خطر." },
    { i: EyeOff, t: "بلا تتبّع", d: "نحجب الصور اللي تبلّغ المرسل إنك فتحت رسالته." },
    { i: Lock, t: "ما نخزن رسائلك", d: "بيانات دخولك مشفّرة، ومفتاحها بمتصفحك فقط." },
  ];
  return (
    <div className="mx-auto grid min-h-full max-w-5xl items-center gap-10 px-5 py-10 md:grid-cols-2">
      <section>
        <Wordmark className="text-5xl" />
        <p className="mt-4 text-lg leading-8 text-ink-muted">تطبيق عراقي يجمع كل بريدك، ويحميك من الاحتيال والتتبّع.</p>
        <ul className="mt-8 space-y-5">
          {points.map(({ i: I, t, d }) => (
            <li key={t} className="flex gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-lapis-50 text-lapis-600 dark:bg-lapis-900"><I className="h-5 w-5" /></span>
              <span><b className="block">{t}</b><span className="text-sm text-ink-muted">{d}</span></span>
            </li>
          ))}
        </ul>
      </section>
      <section className="card p-5 shadow-sm"><AddAccount onAdded={onAdded} /></section>
    </div>
  );
}
