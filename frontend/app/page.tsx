"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Image as ImageIcon, Languages, Link2, Megaphone, Search, ShieldCheck, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Controls, Footer } from "@/components/Chrome";
import { Mark, Wordmark } from "@/components/Logo";
import { SearchBox } from "@/components/SearchBox";
import { ImageResults, Translate, UrlInspect, WebResults } from "@/components/Views";
import { get, type PublicConfig } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";

type Mode = "web" | "images" | "url" | "translate";
type View = { mode: Mode; q: string; active: boolean };

// الحالة تُحفظ في history.state فقط (ليس في الرابط)، فنص البحث لا يظهر في عنوان الصفحة أو السجلات
export default function Home() {
  const { t, lang, remember } = usePrefs();
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [view, setView] = useState<View>({ mode: "web", q: "", active: false });
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => { get<PublicConfig>("/api/public/config").then(setConfig).catch(() => {}); }, []);
  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const s = (e.state?.sumer as View) ?? { mode: "web", q: "", active: false };
      setView(s); setDraft(s.q); setFile(null);
    };
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && !(document.activeElement instanceof HTMLInputElement || document.activeElement instanceof HTMLTextAreaElement)) {
        e.preventDefault(); (document.getElementById("q-md") ?? document.getElementById("q-lg"))?.focus();
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);

  const go = useCallback((q: string, mode?: Mode) => {
    const next: View = { mode: mode ?? (view.mode === "translate" || view.mode === "url" ? view.mode : view.mode), q, active: true };
    setFile(null); setDraft(q); setView(next); remember(q);
    history.pushState({ sumer: next }, "");
    document.title = `${t.brand}`;
  }, [view.mode, remember, t.brand]);

  const goImage = (f: File) => {
    const next: View = { mode: "images", q: "", active: true };
    setFile(f); setView(next); history.pushState({ sumer: next }, "");
  };
  const setMode = (mode: Mode) => {
    const next: View = { ...view, mode, active: view.active || mode === "translate" || mode === "url" };
    setFile(null); setView(next); history.pushState({ sumer: next }, "");
  };
  const home = () => { const s: View = { mode: "web", q: "", active: false }; setView(s); setDraft(""); setFile(null); history.pushState({ sumer: s }, ""); };

  const allModes: { k: Mode; icon: typeof Search; label: string }[] = [
    { k: "web", icon: Search, label: t.modes.web }, { k: "images", icon: ImageIcon, label: t.modes.images },
    { k: "translate", icon: Languages, label: t.modes.translate },
  ];
  const modes = allModes.filter(({ k }) => (k !== "images" || !config || config.features.images) && (k !== "translate" || !!config?.features.translation) || view.mode === k);
  // فحص الصفحة أداة لأصحاب المواقع، مو نطاق بحث: تظهر كتبويب فقط وهي مفتوحة
  if (view.mode === "url") modes.push({ k: "url", icon: Link2, label: t.modes.url });
  const name = config ? (lang === "ar" ? config.name_ar : config.name_en) : t.brand;
  const ann = config?.announcement?.enabled ? (lang === "ar" ? config.announcement.ar : config.announcement.en) : "";

  const ModeTabs = ({ compact }: { compact?: boolean }) => modes.length < 2 ? null : (
    <div role="tablist" className={`no-scrollbar flex gap-1 overflow-x-auto ${compact ? "" : "justify-center"}`}>
      {modes.map(({ k, icon: Icon, label }) => (
        <button key={k} role="tab" aria-selected={view.mode === k} onClick={() => setMode(k)}
          className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition
            ${view.mode === k ? "bg-lapis-50 font-semibold text-lapis-700 dark:bg-lapis-900/40 dark:text-lapis-200" : "text-ink-muted hover:bg-surface-100 dark:hover:bg-night-200"}
`}>
          <Icon className="h-4 w-4" />{label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="flex min-h-full flex-col">
      {config?.maintenance && (
        <div className="flex items-center justify-center gap-2 bg-gold-400/15 px-4 py-2 text-sm text-gold-600"><Wrench className="h-4 w-4" />سومر تحت الصيانة حالياً</div>
      )}
      {ann && <div className="flex items-center justify-center gap-2 bg-lapis-50 px-4 py-2 text-sm text-lapis-700 dark:bg-lapis-900/30 dark:text-lapis-200"><Megaphone className="h-4 w-4" />{ann}</div>}

      <AnimatePresence mode="wait" initial={false}>
        {!view.active ? (
          <motion.main key="home" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .2 }} className="flex flex-1 flex-col">
            <div className="flex justify-end p-4"><Controls /></div>
            <section className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center px-5 pb-24 text-center">
              {config?.logo
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={config.logo} alt="" className="mb-4 h-20 w-20 rounded-3xl" /> : null}
              <h1><Wordmark name={name} /></h1>
              <p className="mt-6 text-lg text-ink-muted">{t.tagline}</p>
              <div className="mt-8 w-full"><SearchBox value={draft} onChange={setDraft} onSubmit={(q) => go(q, view.mode === "translate" ? "translate" : view.mode === "url" ? "url" : view.mode)} onImage={config?.features.images ? goImage : undefined} config={config} autoFocus /></div>
              <div className="mt-5"><ModeTabs /></div>
              <p className="mt-10 flex max-w-md items-center gap-2 text-sm text-ink-muted"><ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />{t.privacyLine}</p>
            </section>
            <Footer privacy={false} onInspect={() => setMode("url")} />
          </motion.main>
        ) : (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .2 }} className="flex flex-1 flex-col">
            <header className="glass sticky top-0 z-20 border-b border-surface-200 dark:border-night-300">
              <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-3 sm:px-5">
                <button onClick={home} className="flex shrink-0 items-center gap-2 text-xl font-bold" aria-label={name}><Mark className="h-8 w-8" /><span className="hidden font-display sm:inline">{name}</span></button>
                {view.mode !== "translate" && view.mode !== "url" && (
                  <div className="order-last w-full sm:order-none sm:w-auto sm:max-w-2xl sm:flex-1"><SearchBox value={draft} onChange={setDraft} onSubmit={(q) => go(q)} onImage={config?.features.images ? goImage : undefined} config={config} size="md" /></div>
                )}
                <div className="ms-auto"><Controls /></div>
              </div>
              <div className="mx-auto max-w-6xl px-4 py-2 sm:px-5"><ModeTabs compact /></div>
            </header>
            <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-6 sm:px-5">
              {view.mode === "web" && view.q && <WebResults key={view.q} q={view.q} config={config} onSearch={(q) => go(q, "web")} />}
              {view.mode === "web" && !view.q && <p className="text-ink-muted">{t.placeholder}</p>}
              {view.mode === "images" && <ImageResults q={view.q} file={file} />}
              {view.mode === "url" && <UrlInspect initial={/^https?:\/\/|\.[a-z]{2,}/i.test(view.q) ? view.q : ""} />}
              {view.mode === "translate" && <Translate initial={view.q} available={!!config?.features.translation} />}
            </main>
            <Footer onInspect={() => setMode("url")} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
