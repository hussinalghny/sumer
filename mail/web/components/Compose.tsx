"use client";

import { Loader2, Send, X } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type Account, type Message } from "@/lib/api";

export function Compose({ accounts, reply, onClose, onSent }: { accounts: Account[]; reply?: Message | null; onClose: () => void; onSent: () => void }) {
  const quote = reply ? `\n\n\n— في ${reply.date ? new Date(reply.date).toLocaleString("ar-IQ") : ""} كتب ${reply.from.name}:\n` + (reply.text || "").split("\n").map((l) => "> " + l).join("\n") : "";
  const [f, setF] = useState({
    account_id: reply?.account_id ?? accounts[0]?.id ?? "",
    to: reply ? (reply.reply_to[0] || reply.from.email) : "",
    cc: "", subject: reply ? (/^(re|رد):/i.test(reply.subject) ? reply.subject : `رد: ${reply.subject}`) : "", body: quote,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const split = (s: string) => s.split(/[,،;\s]+/).map((x) => x.trim()).filter(Boolean);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await api.post("/api/send", { account_id: f.account_id, to: split(f.to), cc: split(f.cc), subject: f.subject, body: f.body,
        in_reply_to: reply?.message_id ?? "", references: reply?.references ?? "" });
      onSent();
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/30 md:items-center" role="dialog" aria-modal="true" aria-label="رسالة جديدة">
      <form onSubmit={send} className="flex h-[92dvh] w-full max-w-2xl flex-col rounded-t-3xl bg-white shadow-2xl dark:bg-night-200 md:h-[80vh] md:rounded-3xl">
        <div className="flex items-center justify-between border-b border-surface-200 px-3 py-2 dark:border-night-300">
          <button type="button" onClick={onClose} className="btn-ghost px-3"><X className="h-5 w-5" />إلغاء</button>
          <b>{reply ? "رد" : "رسالة جديدة"}</b>
          <button className="btn-primary px-4" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4 -scale-x-100" />}إرسال</button>
        </div>
        <div className="divide-y divide-surface-200 px-4 dark:divide-night-300">
          <label className="flex items-center gap-3 py-2"><span className="w-12 text-sm text-ink-muted">من</span>
            <select className="min-h-[40px] flex-1 bg-transparent outline-none" value={f.account_id} onChange={(e) => setF({ ...f, account_id: e.target.value })}>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.email}</option>)}
            </select></label>
          <label className="flex items-center gap-3 py-2"><span className="w-12 text-sm text-ink-muted">إلى</span>
            <input dir="ltr" required className="min-h-[40px] flex-1 bg-transparent text-left outline-none" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} /></label>
          <label className="flex items-center gap-3 py-2"><span className="w-12 text-sm text-ink-muted">نسخة</span>
            <input dir="ltr" className="min-h-[40px] flex-1 bg-transparent text-left outline-none" value={f.cc} onChange={(e) => setF({ ...f, cc: e.target.value })} /></label>
          <label className="flex items-center gap-3 py-2"><span className="w-12 text-sm text-ink-muted">الموضوع</span>
            <input className="min-h-[40px] flex-1 bg-transparent outline-none" value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} /></label>
        </div>
        <textarea aria-label="نص الرسالة" dir="auto" className="flex-1 resize-none bg-transparent px-4 py-3 text-base leading-7 outline-none" value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} autoFocus={!reply} />
        {err && <p role="alert" className="mx-4 mb-3 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">{err}</p>}
      </form>
    </div>
  );
}
