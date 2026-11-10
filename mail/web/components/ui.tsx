"use client";

import { AlertTriangle, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Account, Level } from "@/lib/api";

const PALETTE = ["#2447c8", "#a3742a", "#3a7d6b", "#7a4fb5", "#b4533a", "#2f6f9f", "#5f5f64"];
export function colorFor(s: string) {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function Avatar({ name, email, size = 42 }: { name: string; email: string; size?: number }) {
  const ch = (name || email || "?").trim().replace(/^["'(]/, "").charAt(0).toUpperCase();
  return (
    <span aria-hidden className="grid shrink-0 place-items-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, background: colorFor(email || name), fontSize: size * 0.4 }}>{ch}</span>
  );
}

export function AccountBadge({ acc }: { acc?: Account }) {
  if (!acc) return null;
  return acc.sovereign
    ? <span className="rounded-md bg-[#fbf3e2] px-1.5 py-px text-[11px] font-semibold text-gold-600">سومر · سيادي</span>
    : <span className="rounded-md bg-surface-200 px-1.5 py-px text-[11px] font-semibold text-ink-muted dark:bg-night-300">{acc.provider === "custom" ? acc.email.split("@")[1] : acc.provider_name}</span>;
}

export function LevelBadge({ level }: { level: Level }) {
  if (level === "danger") return <span className="inline-flex items-center gap-1 rounded-md bg-danger-100 px-1.5 py-px text-[11px] font-bold text-danger-600"><AlertTriangle className="h-3 w-3" />خطر</span>;
  if (level === "caution") return <span className="inline-flex items-center gap-1 rounded-md bg-warn-100 px-1.5 py-px text-[11px] font-bold text-warn-700"><ShieldAlert className="h-3 w-3" />احذر</span>;
  return null;
}

export function SafeTag() {
  return <span className="inline-flex items-center gap-1 text-xs text-ok-600"><ShieldCheck className="h-3.5 w-3.5" />تم الفحص</span>;
}

export function Spinner({ label }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-16 text-ink-muted"><Loader2 className="h-5 w-5 animate-spin" />{label}</div>;
}

export function fmtTime(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso), now = new Date();
  const same = d.toDateString() === now.toDateString();
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (same) return d.toLocaleTimeString("ar-IQ", { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === y.toDateString()) return "أمس";
  if (now.getTime() - d.getTime() < 6 * 864e5) return d.toLocaleDateString("ar-IQ", { weekday: "long" });
  return d.toLocaleDateString("ar-IQ", { day: "numeric", month: "short" });
}

export function fmtSize(n: number) {
  return n < 1024 ? `${n} بايت` : n < 1048576 ? `${Math.round(n / 1024)} ك.ب` : `${(n / 1048576).toFixed(1)} م.ب`;
}

export function Wordmark({ className = "" }: { className?: string }) {
  return <span className={`font-display font-bold ${className}`}>سومر <span className="text-lapis-600">بريد</span></span>;
}
