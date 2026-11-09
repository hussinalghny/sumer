"use client";
import { Page } from "@/components/Page";
import { usePrefs } from "@/lib/prefs";

export default function About() {
  const { t, lang } = usePrefs();
  return (
    <Page title={t.about}>
      <p>{t.aboutText}</p>
      {lang === "ar" ? (
        <ul className="list-disc space-y-2 ps-6">
          <li>زاحف خاص يحترم قواعد robots.txt ويعطي الأولوية للمواقع العراقية.</li>
          <li>فهرس وترتيب أصليان يفهمان العربية الفصحى واللهجة العراقية والكردية والإنكليزية.</li>
          <li>لا إعلانات، ولا حسابات، ولا تتبّع.</li>
        </ul>
      ) : (
        <ul className="list-disc space-y-2 ps-6">
          <li>Its own crawler, which respects robots.txt and prioritises Iraqi websites.</li>
          <li>Original index and ranking that understand Arabic, Iraqi Arabic, Kurdish and English.</li>
          <li>No ads, no accounts, no tracking.</li>
        </ul>
      )}
    </Page>
  );
}
