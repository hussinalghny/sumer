"use client";
import { Page } from "@/components/Page";
import { usePrefs } from "@/lib/prefs";

export default function Contact() {
  const { t, lang } = usePrefs();
  return (
    <Page title={t.contact}>
      <p>{lang === "ar"
        ? "لأصحاب المواقع: لإيقاف زحف سومر لموقعك أو جزء منه، أضف قاعدة لـ SumerBot في ملف robots.txt. للاستفسارات، استخدم بريد التواصل الذي يحدده مشغّل الخدمة."
        : "Site owners: to stop Sumer from crawling your site or part of it, add a rule for SumerBot in robots.txt. For enquiries, use the contact address published by the operator."}</p>
      <pre className="ltr-text overflow-x-auto rounded-2xl bg-surface-100 p-4 text-sm dark:bg-night-200">{`User-agent: SumerBot\nDisallow: /private/`}</pre>
    </Page>
  );
}
