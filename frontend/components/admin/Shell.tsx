"use client";

import { Activity, BarChart3, Bot, Cog, Database, Image as ImageIcon, KeyRound, LayoutDashboard, Loader2, LogOut, Menu,
  Search, Server, ShieldCheck, Spline, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Controls } from "@/components/Chrome";
import { Mark } from "@/components/Logo";
import { admin, ApiError, setCsrf } from "@/lib/api";
import { Btn, errText, Field, UiProvider, useL } from "./ui";

type Me = { user: { id: number; email: string; name: string; role: string; totp_enabled: boolean; must_change_pw: boolean };
  permissions: string[]; csrf: string; mfa_passed: boolean; require_2fa: boolean };
const MeCtx = createContext<{ me: Me; can: (p: string) => boolean; refresh: () => void } | null>(null);
export const useMe = () => { const c = useContext(MeCtx); if (!c) throw new Error("no me"); return c; };

const NAV = [
  { href: "/admin", icon: LayoutDashboard, ar: "نظرة عامة", en: "Overview", perm: "dashboard.view" },
  { href: "/admin/search", icon: Search, ar: "التحكم بالبحث", en: "Search control", perm: "search.view" },
  { href: "/admin/crawler", icon: Spline, ar: "الزاحف", en: "Crawler", perm: "crawler.view" },
  { href: "/admin/index", icon: Database, ar: "الفهرس", en: "Index", perm: "index.view" },
  { href: "/admin/images", icon: ImageIcon, ar: "بحث الصور", en: "Image search", perm: "images.view" },
  { href: "/admin/ai", icon: Bot, ar: "خدمات الذكاء", en: "AI services", perm: "ai.view" },
  { href: "/admin/security", icon: ShieldCheck, ar: "الخصوصية والأمن", en: "Privacy & security", perm: "security.view" },
  { href: "/admin/analytics", icon: BarChart3, ar: "التحليلات", en: "Analytics", perm: "analytics.view" },
  { href: "/admin/admins", icon: Users, ar: "المشرفون", en: "Administrators", perm: "admins.view" },
  { href: "/admin/infra", icon: Server, ar: "البنية التحتية", en: "Infrastructure", perm: "infra.view" },
  { href: "/admin/settings", icon: Cog, ar: "الإعدادات", en: "Settings", perm: "settings.view" },
  { href: "/admin/account", icon: KeyRound, ar: "حسابي", en: "My account", perm: "" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  return <UiProvider><Gate>{children}</Gate></UiProvider>;
}

function Gate({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<"loading" | "login" | "mfa" | "ok">("loading");
  const refresh = useCallback(async () => {
    try {
      const m = await admin<Me>("/auth/me");
      setCsrf(m.csrf); setMe(m); setState(m.mfa_passed ? "ok" : "mfa");
    } catch { setState("login"); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  if (state === "loading") return <div className="grid h-full place-items-center"><Loader2 className="h-6 w-6 animate-spin text-lapis-600" /></div>;
  if (state === "login") return <Login onDone={refresh} />;
  if (state === "mfa") return <Mfa onDone={refresh} />;
  const can = (p: string) => !p || me!.permissions.includes(p);
  return <MeCtx.Provider value={{ me: me!, can, refresh }}><Frame>{children}</Frame></MeCtx.Provider>;
}

function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-full place-items-center bg-surface-100 p-4 dark:bg-night">
      <div className="absolute end-4 top-4"><Controls /></div>
      <div className="w-full max-w-sm rounded-3xl bg-white p-8 shadow-soft dark:bg-night-100">
        <div className="mb-6 flex items-center gap-3"><Mark className="h-10 w-10" /><div><div className="text-lg font-bold">سومر</div><div className="text-xs text-ink-muted">{title}</div></div></div>
        {children}
      </div>
    </div>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const L = useL();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <AuthCard title={L("لوحة التحكم", "Control center")}>
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setErr("");
        try { const r = await admin<{ csrf: string }>("/auth/login", { body: { email, password } }); setCsrf(r.csrf); onDone(); }
        catch (e) { setErr(e instanceof ApiError && e.status === 401 ? L("البريد أو كلمة المرور غير صحيحة", "Invalid email or password") : errText(e)); }
        finally { setBusy(false); }
      }}>
        <Field label={L("البريد الإلكتروني", "Email")}><input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} className="input ltr-text" /></Field>
        <Field label={L("كلمة المرور", "Password")}><input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} className="input" /></Field>
        {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
        <Btn className="w-full" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : L("دخول", "Sign in")}</Btn>
      </form>
    </AuthCard>
  );
}

function Mfa({ onDone }: { onDone: () => void }) {
  const L = useL();
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  return (
    <AuthCard title={L("التحقق بخطوتين", "Two-factor verification")}>
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault(); setErr("");
        try { await admin("/auth/mfa", { body: { code } }); onDone(); } catch (e) { setErr(errText(e) === "invalid_code" ? L("الرمز غير صحيح", "Invalid code") : errText(e)); }
      }}>
        <Field label={L("الرمز من تطبيق المصادقة", "Code from your authenticator app")}>
          <input id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={8} required value={code} onChange={(e) => setCode(e.target.value)} className="input ltr-text text-center text-2xl tracking-[.4em]" />
        </Field>
        {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
        <Btn className="w-full">{L("تحقق", "Verify")}</Btn>
      </form>
    </AuthCard>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  const { me, can } = useMe();
  const L = useL();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => setOpen(false), [path]);
  const logout = async () => { try { await admin("/auth/logout", { body: {} }); } finally { location.reload(); } };

  const nav = (
    <nav className="flex flex-col gap-0.5">
      {NAV.filter((n) => can(n.perm)).map((n) => {
        const active = n.href === "/admin" ? path === "/admin" : path?.startsWith(n.href);
        return (
          <Link key={n.href} href={n.href} title={collapsed ? L(n.ar, n.en) : undefined}
            className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${active ? "bg-lapis-50 font-semibold text-lapis-700 dark:bg-lapis-900/40 dark:text-lapis-200" : "text-ink-soft hover:bg-surface-100 dark:text-surface-300 dark:hover:bg-night-200"}`}>
            <n.icon className="h-4 w-4 shrink-0" />{!collapsed && L(n.ar, n.en)}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-full bg-surface-50 dark:bg-night">
      <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-e border-surface-200 bg-white p-3 dark:border-night-300 dark:bg-night-50 lg:flex ${collapsed ? "w-[68px]" : "w-64"}`}>
        <button onClick={() => setCollapsed(!collapsed)} className="mb-5 flex items-center gap-2 px-2 pt-1 text-start" aria-label="collapse">
          <Mark className="h-8 w-8 shrink-0" />{!collapsed && <div><div className="font-bold leading-tight">سومر</div><div className="text-[11px] text-ink-muted">{L("مركز التحكم", "Control center")}</div></div>}
        </button>
        <div className="flex-1 overflow-y-auto">{nav}</div>
        <div className={`mt-3 border-t border-surface-200 pt-3 text-xs dark:border-night-300 ${collapsed ? "hidden" : ""}`}>
          <div className="truncate font-medium">{me.user.name}</div><div className="ltr-text truncate text-ink-muted">{me.user.email}</div>
          <div className="mt-0.5 text-ink-faint">{me.user.role}</div>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setOpen(false)}>
          <aside className="h-full w-72 bg-white p-4 dark:bg-night-50" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between"><span className="flex items-center gap-2 font-bold"><Mark className="h-7 w-7" />سومر</span><Btn variant="ghost" size="sm" onClick={() => setOpen(false)}><X className="h-4 w-4" /></Btn></div>
            {nav}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-0 z-30 flex items-center gap-2 border-b border-surface-200 px-4 py-2 dark:border-night-300">
          <Btn variant="ghost" size="sm" className="lg:hidden" onClick={() => setOpen(true)} aria-label="menu"><Menu className="h-5 w-5" /></Btn>
          <span className="flex items-center gap-1.5 text-xs text-ink-muted"><Activity className="h-3.5 w-3.5 text-emerald-500" />{L("بيانات حية من النظام", "Live system data")}</span>
          {!me.user.totp_enabled && <Link href="/admin/account" className="rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">{L("فعّل التحقق بخطوتين", "Enable two-factor")}</Link>}
          {me.user.must_change_pw && <Link href="/admin/account" className="rounded-full bg-red-50 px-3 py-1 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">{L("غيّر كلمة المرور المؤقتة", "Change your temporary password")}</Link>}
          <div className="ms-auto flex items-center gap-1"><Controls />
            <Btn variant="ghost" size="sm" onClick={logout}><LogOut className="h-4 w-4" />{L("خروج", "Sign out")}</Btn></div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
