"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { dict, type Dict, type Lang } from "./i18n";

type Theme = "light" | "dark" | "system";
type Prefs = {
  lang: Lang; setLang: (l: Lang) => void; t: Dict; dir: "rtl" | "ltr";
  theme: Theme; setTheme: (t: Theme) => void;
  history: string[]; historyOn: boolean; setHistoryOn: (b: boolean) => void; remember: (q: string) => void; clearHistory: () => void;
};

const Ctx = createContext<Prefs | null>(null);

// التفضيلات تُحفظ على جهاز المستخدم فقط (localStorage)، ولا تُرسل للخادم أبداً
function read<T>(k: string, d: T): T {
  try { const v = localStorage.getItem(k); return v === null ? d : (JSON.parse(v) as T); } catch { return d; }
}
function write(k: string, v: unknown) {
  try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* المتصفح يمنع التخزين */ }
}

export function PrefsProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangS] = useState<Lang>("ar");
  const [theme, setThemeS] = useState<Theme>("system");
  const [history, setHistory] = useState<string[]>([]);
  const [historyOn, setHistoryOnS] = useState(true);

  useEffect(() => {
    setLangS(read<Lang>("sumer.lang", "ar"));
    setThemeS(read<Theme>("sumer.theme", "system"));
    setHistory(read<string[]>("sumer.history", []));
    setHistoryOnS(read<boolean>("sumer.historyOn", true));
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    const apply = () => {
      const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.classList.toggle("dark", dark);
    };
    apply();
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  const setLang = (l: Lang) => { setLangS(l); write("sumer.lang", l); };
  const setTheme = (t: Theme) => { setThemeS(t); write("sumer.theme", t); };
  const setHistoryOn = (b: boolean) => { setHistoryOnS(b); write("sumer.historyOn", b); if (!b) { setHistory([]); write("sumer.history", []); } };
  const remember = useCallback((q: string) => {
    if (!read<boolean>("sumer.historyOn", true)) return;
    setHistory((h) => { const n = [q, ...h.filter((x) => x !== q)].slice(0, 12); write("sumer.history", n); return n; });
  }, []);
  const clearHistory = () => { setHistory([]); write("sumer.history", []); };

  return (
    <Ctx.Provider value={{ lang, setLang, t: dict[lang], dir: lang === "ar" ? "rtl" : "ltr", theme, setTheme,
      history, historyOn, setHistoryOn, remember, clearHistory }}>
      {children}
    </Ctx.Provider>
  );
}

export function usePrefs() {
  const c = useContext(Ctx);
  if (!c) throw new Error("PrefsProvider missing");
  return c;
}
