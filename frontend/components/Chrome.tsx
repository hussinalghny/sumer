"use client";

import { Globe, Monitor, Moon, ShieldCheck, Sun } from "lucide-react";
import Link from "next/link";
import { usePrefs } from "@/lib/prefs";

export function Controls() {
  const { lang, setLang, theme, setTheme, t } = usePrefs();
  const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <div className="flex items-center gap-1">
      <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} aria-label="Language"
        className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-100 hover:text-ink dark:hover:bg-night-200 dark:hover:text-surface-100">
        <Globe className="h-4 w-4" />{lang === "ar" ? "English" : "العربية"}
      </button>
      <button onClick={() => setTheme(next)} aria-label={t.theme[theme]} title={t.theme[theme]}
        className="rounded-full p-2 text-ink-muted hover:bg-surface-100 hover:text-ink dark:hover:bg-night-200 dark:hover:text-surface-100">
        <Icon className="h-4 w-4" />
      </button>
    </div>
  );
}

export function Footer({ privacy = true, onInspect }: { privacy?: boolean; onInspect?: () => void }) {
  const { t } = usePrefs();
  return (
    <footer className="border-t border-surface-200 px-6 py-5 text-sm text-ink-muted dark:border-night-300">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
        {privacy ? <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-600" />{t.privacyLine}</span> : <span />}
        <nav className="flex flex-wrap gap-x-5 gap-y-2 whitespace-nowrap">
          <Link href="/about" className="hover:text-ink dark:hover:text-surface-100">{t.about}</Link>
          <Link href="/privacy" className="hover:text-ink dark:hover:text-surface-100">{t.privacy}</Link>
          <Link href="/contact" className="hover:text-ink dark:hover:text-surface-100">{t.contact}</Link>
          <Link href="/status" className="hover:text-ink dark:hover:text-surface-100">{t.status}</Link>
          {onInspect && <button onClick={onInspect} className="hover:text-ink dark:hover:text-surface-100">{t.inspectTool}</button>}
        </nav>
      </div>
    </footer>
  );
}

export function Segs({ segs }: { segs: { t: string; h: boolean }[] }) {
  return <>{segs.map((s, i) => (s.h ? <mark key={i}>{s.t}</mark> : <span key={i}>{s.t}</span>))}</>;
}
