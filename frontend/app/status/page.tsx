"use client";
import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Page } from "@/components/Page";
import { get } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";

type S = Record<string, string | boolean>;
const LABELS: Record<string, [string, string]> = {
  search: ["البحث", "Search"], index: ["الفهرس", "Index"], cache: ["التخزين المؤقت", "Cache"], crawler: ["الزاحف", "Crawler"],
  voice: ["البحث الصوتي", "Voice"], translation: ["الترجمة", "Translation"],
};

export default function Status() {
  const { t, lang } = usePrefs();
  const [s, setS] = useState<S | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { get<S>("/api/status").then(setS).catch(() => setErr(true)); }, []);
  return (
    <Page title={t.status}>
      {err && <p className="text-red-600">{lang === "ar" ? "تعذّر الوصول للخادم" : "Server unreachable"}</p>}
      {s && (
        <ul className="divide-y divide-surface-200 rounded-3xl border border-surface-200 dark:divide-night-300 dark:border-night-300">
          {Object.entries(LABELS).map(([k, [a, e]]) => {
            const v = String(s[k]);
            const ok = v === "ok" || v === "ready";
            const Icon = ok ? CheckCircle2 : v === "idle" || v.startsWith("missing") ? CircleDashed : XCircle;
            return (
              <li key={k} className="flex items-center justify-between px-5 py-4 text-base">
                <span>{lang === "ar" ? a : e}</span>
                <span className={`flex items-center gap-2 ${ok ? "text-emerald-600" : v === "down" ? "text-red-600" : "text-ink-muted"}`}><Icon className="h-5 w-5" />{v}</span>
              </li>
            );
          })}
        </ul>
      )}
      {s && <p className="text-sm text-ink-faint">v{String(s.version)}</p>}
    </Page>
  );
}
