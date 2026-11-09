import type { Metadata, Viewport } from "next";
import "./globals.css";
import { PrefsProvider } from "@/lib/prefs";

export const metadata: Metadata = {
  title: "سومر · محرك بحث عراقي مستقل",
  description: "محرك بحث عراقي مستقل يحترم الخصوصية",
  referrer: "no-referrer",
  robots: { index: true, follow: true },
  icons: { icon: "/logo.svg" },
};
export const viewport: Viewport = { themeColor: [{ media: "(prefers-color-scheme: light)", color: "#fbfbfd" }, { media: "(prefers-color-scheme: dark)", color: "#000000" }] };

// يضبط اللغة والسمة قبل الرسم لتجنب الوميض (القيم من جهاز المستخدم فقط)
const boot = `try{var l=JSON.parse(localStorage.getItem('sumer.lang')||'"ar"');var t=JSON.parse(localStorage.getItem('sumer.theme')||'"system"');
document.documentElement.lang=l;document.documentElement.dir=l==='ar'?'rtl':'ltr';
if(t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark');}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: boot }} /></head>
      <body><PrefsProvider>{children}</PrefsProvider></body>
    </html>
  );
}
