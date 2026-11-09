"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Loader2, Search, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { admin, ApiError } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";

export function useL() {
  const { lang } = usePrefs();
  return (ar: string, en: string) => (lang === "ar" ? ar : en);
}

// ===================== جلب البيانات =====================
export function useAdmin<T>(path: string | null, refreshMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!path) return;
    try { setData(await admin<T>(path)); setError(""); }
    catch (e) { setError(errText(e)); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => { setLoading(true); load(); }, [load]);
  useEffect(() => {
    if (!refreshMs) return;
    const id = setInterval(load, refreshMs);
    return () => clearInterval(id);
  }, [load, refreshMs]);
  return { data, error, loading, reload: load, setData };
}

export function errText(e: unknown) {
  if (e instanceof ApiError) {
    const map: Record<string, string> = { forbidden: "لا تملك صلاحية لهذا الإجراء", csrf_failed: "انتهت صلاحية الجلسة، أعد تحميل الصفحة",
      unauthenticated: "يجب تسجيل الدخول", rate_limited: "محاولات كثيرة، انتظر قليلاً", rebuild_in_progress: "إعادة البناء جارية بالفعل" };
    return map[e.detail] ?? e.detail;
  }
  return (e as Error).message;
}

// ===================== الإشعارات =====================
type Toast = { id: number; kind: "ok" | "err"; text: string };
type Confirm = { title: string; body?: string; danger?: boolean; typed?: string; resolve: (ok: boolean) => void };
const UiCtx = createContext<{ toast: (text: string, kind?: "ok" | "err") => void; confirm: (c: Omit<Confirm, "resolve">) => Promise<boolean> } | null>(null);

export function UiProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [conf, setConf] = useState<Confirm | null>(null);
  const [typed, setTyped] = useState("");
  const L = useL();
  const toast = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const confirm = useCallback((c: Omit<Confirm, "resolve">) => new Promise<boolean>((resolve) => { setTyped(""); setConf({ ...c, resolve }); }), []);
  const close = (ok: boolean) => { conf?.resolve(ok); setConf(null); };
  return (
    <UiCtx.Provider value={{ toast, confirm }}>
      {children}
      <div className="fixed bottom-5 start-5 z-50 flex flex-col gap-2" aria-live="polite">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className={`flex items-center gap-2 rounded-2xl px-4 py-3 text-sm text-white shadow-soft ${t.kind === "ok" ? "bg-ink dark:bg-night-300" : "bg-red-600"}`}>
              {t.kind === "ok" ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <XCircle className="h-4 w-4" />}{t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <AnimatePresence>
        {conf && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={() => close(false)}>
            <motion.div initial={{ scale: .96 }} animate={{ scale: 1 }} role="alertdialog" aria-modal onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl dark:bg-night-200">
              <div className="flex items-start gap-3">
                {conf.danger && <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-red-50 text-red-600 dark:bg-red-950/50"><AlertTriangle className="h-5 w-5" /></span>}
                <div><h3 className="text-lg font-semibold">{conf.title}</h3>{conf.body && <p className="mt-1 text-sm text-ink-muted">{conf.body}</p>}</div>
              </div>
              {conf.typed && (
                <label className="mt-4 block text-sm">{L("اكتب", "Type")} <b className="ltr-text">{conf.typed}</b> {L("للتأكيد", "to confirm")}
                  <input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} className="input mt-1" /></label>
              )}
              <div className="mt-6 flex justify-end gap-2">
                <Btn variant="ghost" onClick={() => close(false)}>{L("إلغاء", "Cancel")}</Btn>
                <Btn variant={conf.danger ? "danger" : "primary"} disabled={!!conf.typed && typed !== conf.typed} onClick={() => close(true)}>{L("تأكيد", "Confirm")}</Btn>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </UiCtx.Provider>
  );
}

export function useUi() {
  const c = useContext(UiCtx);
  if (!c) throw new Error("UiProvider missing");
  return c;
}

/** ينفّذ إجراء خلفي مع تأكيد اختياري وإشعار بالنتيجة */
export function useAction() {
  const { toast, confirm } = useUi();
  const [busy, setBusy] = useState(false);
  const run = useCallback(async <T,>(fn: () => Promise<T>, opts: { ok?: string; confirm?: Omit<Confirm, "resolve"> } = {}) => {
    if (opts.confirm && !(await confirm(opts.confirm))) return undefined;
    setBusy(true);
    try { const r = await fn(); if (opts.ok) toast(opts.ok); return r; }
    catch (e) { toast(errText(e), "err"); return undefined; }
    finally { setBusy(false); }
  }, [toast, confirm]);
  return { run, busy };
}

// ===================== مكوّنات =====================
export function Btn({ variant = "primary", size = "md", className = "", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "outline"; size?: "sm" | "md" }) {
  const v = { primary: "bg-lapis-600 text-white hover:bg-lapis-700", ghost: "hover:bg-surface-100 dark:hover:bg-night-300",
    danger: "bg-red-600 text-white hover:bg-red-700", outline: "border border-surface-300 hover:bg-surface-100 dark:border-night-400 dark:hover:bg-night-300" }[variant];
  return <button {...p} className={`inline-flex items-center justify-center gap-1.5 rounded-xl font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${size === "sm" ? "px-2.5 py-1 text-xs" : "px-4 py-2 text-sm"} ${v} ${className}`} />;
}

export function Card({ title, actions, children, className = "" }: { title?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl border border-surface-200 bg-white p-5 dark:border-night-300 dark:bg-night-100 ${className}`}>
      {(title || actions) && <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 className="text-base font-semibold">{title}</h2><div className="flex flex-wrap gap-2">{actions}</div></div>}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "good" | "warn" | "bad" }) {
  const c = tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-gold-600" : tone === "bad" ? "text-red-600" : "";
  return (
    <div className="rounded-2xl border border-surface-200 bg-white p-4 dark:border-night-300 dark:bg-night-100">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${c}`}>{value ?? "—"}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-faint">{hint}</div>}
    </div>
  );
}

export function Badge({ value, map }: { value: string | boolean | null | undefined; map?: Record<string, "good" | "warn" | "bad" | "info"> }) {
  const v = String(value);
  const auto: Record<string, "good" | "warn" | "bad" | "info"> = { ok: "good", true: "good", active: "good", done: "good", running: "good", ready: "good", live: "good",
    pending: "info", paused: "warn", idle: "warn", missing_model: "warn", missing_package: "warn", not_modified: "info", redirect: "info", duplicate: "warn",
    failed: "bad", error: "bad", broken: "bad", blocked: "bad", suspended: "bad", stopped: "bad", false: "bad", critical: "bad", high: "bad", medium: "warn", low: "info",
    robots_blocked: "warn", noindex: "info", excluded: "info", cancelled: "info", retired: "info", building: "info" };
  const tone = (map ?? {})[v] ?? auto[v] ?? "info";
  const cls = { good: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300", warn: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    bad: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300", info: "bg-surface-100 text-ink-muted dark:bg-night-300" }[tone];
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
    <span className={`h-1.5 w-1.5 rounded-full ${{ good: "bg-emerald-500", warn: "bg-amber-500", bad: "bg-red-500", info: "bg-ink-faint" }[tone]}`} />{v}</span>;
}

export type Col<T> = { key: string; label: string; render?: (row: T) => React.ReactNode; className?: string };

export function Table<T extends Record<string, unknown>>({ cols, rows, empty, rowKey }: { cols: Col<T>[]; rows: T[] | undefined | null; empty?: string; rowKey?: (r: T) => string | number }) {
  const L = useL();
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead><tr className="border-b border-surface-200 text-start text-xs text-ink-muted dark:border-night-300">
          {cols.map((c) => <th key={c.key} className={`whitespace-nowrap px-3 py-2.5 text-start font-medium ${c.className ?? ""}`}>{c.label}</th>)}
        </tr></thead>
        <tbody>
          {!rows ? <tr><td colSpan={cols.length} className="py-10 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin text-lapis-600" /></td></tr>
            : rows.length === 0 ? <tr><td colSpan={cols.length} className="py-10 text-center text-ink-faint">{empty ?? L("لا توجد بيانات", "No data")}</td></tr>
            : rows.map((r, i) => (
              <tr key={rowKey ? rowKey(r) : i} className="border-b border-surface-100 last:border-0 hover:bg-surface-50 dark:border-night-200 dark:hover:bg-night-200/60">
                {cols.map((c) => <td key={c.key} className={`px-3 py-2.5 align-top ${c.className ?? ""}`}>{c.render ? c.render(r) : fmt(r[c.key])}</td>)}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pager({ page, total, size = 25, onPage }: { page: number; total: number; size?: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  const L = useL();
  return (
    <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
      <span>{L("المجموع", "Total")}: {total.toLocaleString()}</span>
      <div className="flex items-center gap-1">
        <Btn variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="prev"><ChevronRight className="h-4 w-4 rtl:rotate-0 ltr:rotate-180" /></Btn>
        <span className="tabular-nums">{page} / {pages}</span>
        <Btn variant="ghost" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="next"><ChevronLeft className="h-4 w-4 rtl:rotate-0 ltr:rotate-180" /></Btn>
      </div>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  const [v, setV] = useState(value);
  const t = useRef<ReturnType<typeof setTimeout>>(undefined);
  return (
    <label className="relative block">
      <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
      <input value={v} placeholder={placeholder} aria-label={placeholder} className="input ps-9"
        onChange={(e) => { setV(e.target.value); clearTimeout(t.current); const x = e.target.value; t.current = setTimeout(() => onChange(x), 300); }} />
    </label>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (b: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 py-1.5 text-sm">
      <span>{label}</span>
      <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition disabled:opacity-50 ${checked ? "bg-lapis-600" : "bg-surface-300 dark:bg-night-400"}`}>
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${checked ? "start-[22px]" : "start-0.5"}`} />
      </button>
    </label>
  );
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <label className="block text-sm"><span className="mb-1 block text-ink-muted">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-ink-faint">{hint}</span>}</label>;
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={onClose}>
          <motion.div initial={{ y: 12 }} animate={{ y: 0 }} role="dialog" aria-modal aria-label={title} onClick={(e) => e.stopPropagation()}
            className={`max-h-[88vh] w-full overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl dark:bg-night-200 ${wide ? "max-w-3xl" : "max-w-lg"}`}>
            <div className="mb-4 flex items-center justify-between"><h3 className="text-lg font-semibold">{title}</h3><Btn variant="ghost" size="sm" onClick={onClose} aria-label="close"><X className="h-4 w-4" /></Btn></div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function ErrorNote({ error }: { error: string }) {
  if (!error) return null;
  return <div role="alert" className="mb-4 rounded-2xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{error}</div>;
}

export function PageHead({ title, desc, actions }: { title: string; desc?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-2xl font-bold tracking-tight">{title}</h1>{desc && <p className="mt-1 text-sm text-ink-muted">{desc}</p>}</div>
      <div className="flex flex-wrap gap-2">{actions}</div>
    </div>
  );
}

export function fmt(v: unknown): React.ReactNode {
  if (v === null || v === undefined || v === "") return <span className="text-ink-faint">—</span>;
  if (typeof v === "boolean") return <Badge value={v} />;
  if (typeof v === "number") return <span className="tabular-nums">{Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3)}</span>;
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v)) return <span className="whitespace-nowrap tabular-nums">{new Date(v).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}</span>;
  if (typeof v === "object") return <code className="ltr-text text-xs text-ink-muted">{JSON.stringify(v).slice(0, 120)}</code>;
  return String(v);
}

export function Url({ v }: { v: unknown }) {
  return <a href={String(v)} rel="noreferrer noopener" className="ltr-text block max-w-[22rem] truncate text-lapis-600 hover:underline">{String(v)}</a>;
}

export function bytes(n: number | null | undefined) {
  if (n == null) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; let x = n;
  while (x >= 1024 && i < u.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(x < 10 && i ? 1 : 0)} ${u[i]}`;
}

export function Gauge({ label, value, detail }: { label: string; value: number; detail?: string }) {
  const tone = value > 90 ? "bg-red-500" : value > 75 ? "bg-amber-500" : "bg-lapis-600";
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="text-ink-muted">{label}</span><span className="tabular-nums">{value.toFixed(0)}%{detail ? ` · ${detail}` : ""}</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-100 dark:bg-night-300"><div className={`h-full rounded-full ${tone} transition-all`} style={{ width: `${Math.min(100, value)}%` }} /></div>
    </div>
  );
}
