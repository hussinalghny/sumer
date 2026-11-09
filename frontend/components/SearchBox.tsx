"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Camera, Clock, Loader2, Mic, MicOff, Search, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { post, upload, type PublicConfig } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";

type Props = {
  value: string; onChange: (v: string) => void; onSubmit: (q: string) => void;
  onImage?: (f: File) => void; config: PublicConfig | null; size?: "lg" | "md"; autoFocus?: boolean; placeholder?: string;
};

export function SearchBox({ value, onChange, onSubmit, onImage, config, size = "lg", autoFocus, placeholder }: Props) {
  const { t, history, historyOn, clearHistory, lang } = usePrefs();
  const [open, setOpen] = useState(false);
  const [sugs, setSugs] = useState<string[]>([]);
  const [active, setActive] = useState(-1);
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceErr, setVoiceErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const big = size === "lg";

  // الاقتراحات من محتوى الفهرس فقط، مع تأخير بسيط
  useEffect(() => {
    if (!open || value.trim().length < 2) { setSugs([]); return; }
    const ctl = new AbortController();
    const id = setTimeout(() => {
      post<{ suggestions: string[] }>("/api/suggest", { q: value }, ctl.signal).then((r) => setSugs(r.suggestions)).catch(() => {});
    }, 160);
    return () => { clearTimeout(id); ctl.abort(); };
  }, [value, open]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const items = value.trim().length >= 2 ? sugs : historyOn ? history.slice(0, 8) : [];
  const showHistory = value.trim().length < 2;

  const submit = (q: string) => { if (!q.trim()) return; setOpen(false); setActive(-1); onSubmit(q.trim()); };

  async function toggleVoice() {
    setVoiceErr("");
    if (rec) { rec.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setRec(null);
        setVoiceBusy(true);
        try {
          const f = new FormData();
          f.append("file", new Blob(chunks, { type: r.mimeType }), "voice.webm");
          f.append("language", lang === "ar" ? "ar" : "en");
          const res = await upload<{ text: string }>("/api/voice", f);
          onChange(res.text);   // المستخدم يراجع النص ويعدّله قبل البحث
        } catch (e) { setVoiceErr((e as Error).message); }
        finally { setVoiceBusy(false); }
      };
      r.start();
      setRec(r);
      setTimeout(() => r.state === "recording" && r.stop(), 15000);
    } catch (e) { setVoiceErr((e as Error).message); }
  }

  const voiceOk = !!config?.features.voice;

  return (
    <div ref={boxRef} className="relative w-full">
      <form role="search" onSubmit={(e) => { e.preventDefault(); submit(active >= 0 ? items[active] : value); }}
        className={`group flex items-center gap-1 rounded-full border bg-white transition-all dark:bg-night-200
          ${open && items.length ? "border-lapis-600/40 shadow-ring" : "border-surface-200 shadow-soft dark:border-night-300"}
          focus-within:border-lapis-600/50 focus-within:shadow-ring ${big ? "p-2" : "p-1"}`}>
        <Search className={`ms-3 shrink-0 text-ink-faint ${big ? "h-5 w-5" : "h-4 w-4"}`} aria-hidden />
        <input id={`q-${size}`} value={value} autoFocus={autoFocus} autoComplete="off" spellCheck={false} maxLength={300}
          aria-label={t.search} placeholder={placeholder ?? t.placeholder}
          onFocus={() => setOpen(true)} onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(-1); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, -1)); }
            if (e.key === "Escape") setOpen(false);
          }}
          className={`min-w-0 flex-1 bg-transparent px-2 outline-none focus-visible:outline-none placeholder:text-ink-faint ${big ? "py-2.5 text-lg" : "py-1.5 text-base"}`} />
        {value && (
          <button type="button" onClick={() => onChange("")} aria-label={t.clear}
            className="rounded-full p-2 text-ink-faint hover:bg-surface-100 dark:hover:bg-night-300"><X className="h-4 w-4" /></button>
        )}
        <span className="mx-1 hidden h-6 w-px bg-surface-200 dark:bg-night-300 sm:block" aria-hidden />
        <button type="button" onClick={toggleVoice} disabled={!voiceOk || voiceBusy}
          title={voiceOk ? (rec ? t.voiceListening : t.voice) : t.voiceUnavailable} aria-label={t.voice}
          className={`rounded-full p-2 transition ${rec ? "animate-pulse bg-red-500 text-white" : "text-lapis-600 hover:bg-lapis-50 dark:text-lapis-400 dark:hover:bg-night-300"} disabled:cursor-not-allowed disabled:text-ink-faint/60 disabled:hover:bg-transparent`}>
          {voiceBusy ? <Loader2 className="h-5 w-5 animate-spin" /> : rec ? <Square className="h-5 w-5" /> : voiceOk ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
        </button>
        {onImage && (
          <>
            <button type="button" onClick={() => fileRef.current?.click()} title={t.imageSearch} aria-label={t.imageSearch}
              className="rounded-full p-2 text-lapis-600 hover:bg-lapis-50 dark:text-lapis-400 dark:hover:bg-night-300"><Camera className="h-5 w-5" /></button>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onImage(f); e.target.value = ""; }} />
          </>
        )}
        <button type="submit" aria-label={t.search} className={`shrink-0 rounded-full bg-lapis-600 font-semibold text-white transition hover:bg-lapis-700 active:scale-[.97] ${big ? "px-6 py-2.5" : "px-3 py-1.5 text-sm sm:px-4"}`}>
          {big ? t.search : <><Search className="h-4 w-4 sm:hidden" /><span className="hidden sm:inline">{t.search}</span></>}
        </button>
      </form>
      {voiceErr && <p role="alert" className="mt-2 text-center text-sm text-red-600">{voiceErr}</p>}

      <AnimatePresence>
        {open && items.length > 0 && (
          <motion.ul initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: .14 }}
            role="listbox" className="absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-3xl border border-surface-200 bg-white py-2 shadow-soft dark:border-night-300 dark:bg-night-200">
            {showHistory && (
              <li className="flex items-center justify-between px-5 pb-1 pt-1 text-xs text-ink-faint">
                <span>{t.history}</span>
                <button type="button" className="hover:text-lapis-600" onClick={clearHistory}>{t.clear}</button>
              </li>
            )}
            {items.map((s, i) => (
              <li key={s} role="option" aria-selected={i === active}>
                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => { onChange(s); submit(s); }}
                  className={`flex w-full items-center gap-3 px-5 py-2.5 text-start ${i === active ? "bg-surface-100 dark:bg-night-300" : "hover:bg-surface-100 dark:hover:bg-night-300"}`}>
                  {showHistory ? <Clock className="h-4 w-4 shrink-0 text-ink-faint" /> : <Search className="h-4 w-4 shrink-0 text-ink-faint" />}
                  <span className="truncate">{s}</span>
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
