"use client";

import { AlertTriangle, ChevronLeft, Download, ImageOff, Reply, ShieldAlert, ShieldCheck, ShieldX, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Account, type Message, type Summary } from "@/lib/api";
import { AccountBadge, Avatar, fmtSize, Spinner } from "./ui";

function frameDoc(html: string, text: string) {
  const body = html || `<pre style="white-space:pre-wrap;font:inherit;margin:0">${text.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]!))}</pre>`;
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data: https:; style-src 'unsafe-inline'"><base target="_blank">
<style>html,body{margin:0;padding:0;background:#fff;color:#1d1d1f;font:16px/1.65 -apple-system,"SF Arabic","Segoe UI","Noto Sans Arabic",Tahoma,sans-serif;word-wrap:break-word;overflow-wrap:anywhere}
body{padding:4px 2px}img{max-width:100%;height:auto}table{max-width:100%!important}a{color:#2447c8}a[data-blocked]{color:#8e8e93;text-decoration:line-through;cursor:not-allowed}blockquote{margin:0 8px;padding-inline-start:10px;border-inline-start:3px solid #e3e3e8;color:#5f5f64}</style>
</head><body dir="auto">${body}</body></html>`;
}

export function MessageView({ summary, account, onBack, onReply, onChanged, onError }: {
  summary: Summary; account?: Account; onBack: () => void; onReply: (m: Message) => void; onChanged: () => void; onError: (e: ApiError) => void;
}) {
  const [m, setM] = useState<Message | null>(null);
  const [images, setImages] = useState(false);
  const [busy, setBusy] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);
  const base = `/api/accounts/${summary.account_id}/messages/${summary.folder}/${summary.uid}`;

  useEffect(() => {
    let alive = true;
    setM(null);
    api.get<Message>(`${base}${images ? "?images=1" : ""}`).then((r) => { if (alive) setM(r); }).catch((e) => onError(e));
    if (!summary.seen) api.post(`${base}/flags`, { seen: true }).catch(() => {});
    return () => { alive = false; };
  }, [base, images, summary.seen, onError]);

  const fit = () => {
    const d = frame.current?.contentDocument;
    if (d && frame.current) frame.current.style.height = `${Math.max(120, d.documentElement.scrollHeight + 8)}px`;
  };

  async function moveTo(to: "trash" | "junk") {
    setBusy(to);
    try { await api.post(`${base}/move`, { to }); onChanged(); onBack(); } catch (e) { onError(e as ApiError); } finally { setBusy(""); }
  }

  if (!m) return <div className="flex-1"><Header onBack={onBack} account={account} /><Spinner label="نفحص الرسالة…" /></div>;
  const a = m.analysis;
  const danger = a.level === "danger", caution = a.level === "caution";

  return (
    <article className="flex-1 pb-28 md:pb-10">
      <Header onBack={onBack} account={account} />
      <div className="mx-auto max-w-3xl px-4">
        {(danger || caution) ? (
          <section aria-label="تحذير" className={`rounded-2xl border p-4 ${danger ? "border-danger-100 bg-danger-50" : "border-warn-100 bg-warn-50"}`}>
            <div className="flex items-center gap-3">
              <span className={`grid h-10 w-10 place-items-center rounded-xl text-white ${danger ? "bg-danger-600" : "bg-[#b54708]"}`}>
                {danger ? <ShieldX className="h-5 w-5" /> : <ShieldAlert className="h-5 w-5" />}</span>
              <div>
                <h2 className={`text-lg font-bold ${danger ? "text-danger-600" : "text-warn-700"}`}>{danger ? "رسالة تصيّد على الأغلب" : "انتبه لهاي الرسالة"}</h2>
                <p className="text-sm text-ink-soft">{danger ? "عطّلنا الروابط. لا تدخل بياناتك ولا تفتح المرفقات." : "بيها علامات مريبة. تأكد من المرسل قبل ما تتصرف."}</p>
              </div>
            </div>
            <ul className="mt-3 divide-y divide-black/5">
              {a.reasons.map((r) => (
                <li key={r.code} className="flex gap-2.5 py-2.5">
                  <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${r.severity === "high" ? "text-danger-600" : r.severity === "medium" ? "text-[#b54708]" : "text-ink-muted"}`} />
                  <span><b className="block text-[15px]">{r.title}</b><span className="text-sm text-ink-soft" dir="auto">{r.detail}</span></span>
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <div className="flex items-center gap-2 rounded-xl bg-ok-50 px-3 py-2 text-sm text-ok-600"><ShieldCheck className="h-4 w-4" />فحصنا الرسالة وما لكينا علامات تصيّد{a.trackers ? `، وحجبنا ${a.trackers} متتبّع` : ""}</div>
        )}

        <h1 className="mt-5 text-[22px] font-bold leading-snug" dir="auto">{m.subject}</h1>
        <div className="mt-3 flex items-center gap-3">
          <Avatar name={m.from.name} email={m.from.email} size={40} />
          <div className="min-w-0">
            <div className="font-semibold" dir="auto">{m.from.name}</div>
            <div className="truncate text-sm text-ink-muted" dir="ltr" style={{ textAlign: "right" }}>{m.from.email}</div>
          </div>
          <time className="ms-auto shrink-0 text-sm text-ink-muted">{m.date ? new Date(m.date).toLocaleString("ar-IQ", { dateStyle: "medium", timeStyle: "short" }) : ""}</time>
        </div>

        {m.remote_images > 0 && !m.images_shown && !danger && (
          <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-surface-200 px-3 py-2 text-sm dark:bg-night-300">
            <span className="flex items-center gap-2 text-ink-muted"><ImageOff className="h-4 w-4" />حجبنا {m.remote_images.toString()} صورة خارجية حتى المرسل ما يعرف إنك فتحت الرسالة.</span>
            <button onClick={() => setImages(true)} className="shrink-0 rounded-lg px-2 py-1 font-semibold text-lapis-600 hover:bg-white dark:hover:bg-night-200">اعرض الصور</button>
          </div>
        )}

        <div className="card mt-4 overflow-hidden p-3">
          <iframe ref={frame} title="محتوى الرسالة" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" onLoad={fit}
            srcDoc={frameDoc(m.html, m.text)} className="block w-full border-0" style={{ height: 200 }} />
        </div>

        {m.attachments.length > 0 && (
          <div className="mt-4 space-y-2">
            <h3 className="text-sm font-semibold text-ink-muted">المرفقات</h3>
            {m.attachments.map((x) => (
              <div key={x.index} className={`card flex items-center gap-3 p-3 ${x.risk === "danger" ? "ring-1 ring-danger-100" : ""}`}>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium" dir="ltr" style={{ textAlign: "right" }}>{x.filename}</div>
                  <div className="text-xs text-ink-muted">{fmtSize(x.size)}{x.risk === "danger" ? " · ملف خطر، لا تفتحه" : x.risk === "caution" ? " · افتحه بحذر" : ""}</div>
                </div>
                {x.risk === "danger"
                  ? <span className="rounded-lg bg-danger-100 px-2 py-1 text-xs font-bold text-danger-600">محجوب</span>
                  : <a href={`${base}/attachments/${x.index}`} className="btn-ghost min-h-[40px] px-3 text-sm" download><Download className="h-4 w-4" />تنزيل</a>}
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-2">
          {!danger && <button onClick={() => onReply(m)} className="btn-primary"><Reply className="h-4 w-4" />رد</button>}
          {(danger || caution) && <button onClick={() => moveTo("junk")} disabled={!!busy} className="btn bg-danger-600 text-white hover:bg-danger-700"><ShieldX className="h-4 w-4" />بلّغ وانقل لغير المرغوب</button>}
          <button onClick={() => moveTo("trash")} disabled={!!busy} className="btn-ghost"><Trash2 className="h-4 w-4" />حذف</button>
        </div>
      </div>
    </article>
  );
}

function Header({ onBack, account }: { onBack: () => void; account?: Account }) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between bg-surface-100/90 px-2 py-2 backdrop-blur-xl dark:bg-night/90">
      <button onClick={onBack} className="flex min-h-[44px] items-center gap-0.5 px-2 text-[17px] text-lapis-600"><ChevronLeft className="h-6 w-6 rotate-180" />رجوع</button>
      <span className="px-2"><AccountBadge acc={account} /></span>
    </header>
  );
}
