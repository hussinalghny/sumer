"use client";
import { Page } from "@/components/Page";
import { usePrefs } from "@/lib/prefs";

const AR = [
  ["لا نحفظ عمليات البحث", "نص البحث يُعالج بالذاكرة ثم يُنسى. لا يوجد في قاعدة البيانات أي جدول للاستعلامات."],
  ["لا نحفظ عنوان IP", "الحماية من الإساءة تستخدم بصمة مشفّرة تتغير كل ساعة ولا يمكن عكسها."],
  ["لا كوكيز ولا تتبّع", "لا أدوات تحليل، ولا خطوط أو سكربتات من أي جهة خارجية. سياسة أمان المحتوى تمنعها تقنياً."],
  ["البحث لا يظهر في الرابط", "نرسل البحث داخل الطلب المشفّر، فلا يظهر في عنوان الصفحة أو سجلات الوسطاء."],
  ["الصور والصوت لا تُخزّن", "الصورة المرفوعة تُعالج بالذاكرة داخل عملية معزولة، والصوت يُحذف فور تحويله لنص."],
  ["سجل البحث على جهازك فقط", "تستطيع إيقافه أو مسحه من صندوق البحث. لا يصل للخادم أبداً."],
  ["تحليلات مجمّعة فقط", "نعدّ عدد عمليات البحث بالساعة لمراقبة الأداء، بدون أي نص أو هوية."],
];
const EN = [
  ["We don't store searches", "Your query is processed in memory and forgotten. There is no query table in the database."],
  ["We don't store IP addresses", "Abuse protection uses an hourly-rotating keyed hash that cannot be reversed."],
  ["No cookies, no tracking", "No analytics, no third-party fonts or scripts. The content security policy enforces this."],
  ["Searches never appear in URLs", "Queries are sent inside the encrypted request body, not the address bar."],
  ["Images and audio are not kept", "Uploads are processed in memory in a sandboxed process; audio is deleted after transcription."],
  ["History stays on your device", "You can turn it off or clear it from the search box. It never reaches our servers."],
  ["Aggregate analytics only", "We count searches per hour to monitor performance, with no text or identity."],
];

export default function Privacy() {
  const { t, lang } = usePrefs();
  return (
    <Page title={t.privacy}>
      {(lang === "ar" ? AR : EN).map(([h, p]) => (
        <section key={h}><h2 className="text-xl font-semibold text-ink dark:text-surface-100">{h}</h2><p className="mt-1">{p}</p></section>
      ))}
    </Page>
  );
}
