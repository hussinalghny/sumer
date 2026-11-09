"use client";

import { Play, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, Card, ErrorNote, Field, PageHead, Stat, Switch, Table, Url, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin, type SearchResponse } from "@/lib/api";

type Settings = Record<string, unknown> & { "search.ranking": Record<string, number>; "search.region_priority": Record<string, number> };
type Lang = { code: string; name: string; native_name: string; enabled: boolean; priority: number };
const WEIGHTS: [string, string, string][] = [
  ["text", "صلة النص", "Text relevance"], ["title", "صلة العنوان", "Title relevance"], ["authority", "سلطة الموقع", "Site authority"],
  ["quality", "جودة المحتوى", "Content quality"], ["freshness", "الحداثة", "Freshness"], ["iraqi", "الأولوية العراقية", "Iraqi relevance"],
  ["language", "تطابق اللغة", "Language match"], ["spam_penalty", "عقوبة السبام", "Spam penalty"]];

export default function SearchControl() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const s = useAdmin<Settings>("/search/settings");
  const langs = useAdmin<Lang[]>("/languages");
  const quality = useAdmin<{ searches_7d: number; zero_result_rate: number | null; spam_signals: Record<string, unknown>[]; top_spam: Record<string, unknown>[] }>("/search/quality");
  const evalSet = useAdmin<{ query: string; expected_url: string }[]>("/search/eval-set");
  const [draft, setDraft] = useState<Settings | null>(null);
  const [q, setQ] = useState("");
  const [test, setTest] = useState<SearchResponse | null>(null);
  const [items, setItems] = useState<{ query: string; expected_url: string }[]>([]);
  const [evalRes, setEvalRes] = useState<{ mrr: number; p_at_1: number; p_at_3: number; rows: { query: string; expected_url: string; rank: number | null; top: string[] }[] } | null>(null);
  const manage = can("search.manage");

  useEffect(() => { if (s.data) setDraft(s.data); }, [s.data]);
  useEffect(() => { if (evalSet.data) setItems(evalSet.data); }, [evalSet.data]);

  const save = () => run(() => admin("/search/settings", { method: "PUT", body: { values: draft } }), { ok: L("حُفظت الإعدادات وطُبّقت فوراً", "Saved and applied") }).then(() => s.reload());
  const setW = (group: "search.ranking" | "search.region_priority", k: string, v: number) =>
    setDraft((d) => d && { ...d, [group]: { ...d[group], [k]: v } });

  return (
    <>
      <PageHead title={L("التحكم بالبحث", "Search control")} desc={L("الأوزان تُطبّق على الترتيب فوراً بدون إعادة تشغيل", "Weights apply to ranking immediately")}
        actions={manage && <Btn onClick={save} disabled={busy || !draft}><Save className="h-4 w-4" />{L("حفظ", "Save")}</Btn>} />
      <ErrorNote error={s.error} />
      {draft && (
        <div className="grid gap-5 lg:grid-cols-3">
          <Card title={L("الخدمات", "Services")}>
            <Switch label={L("تفعيل البحث", "Search enabled")} checked={!!draft["search.enabled"]} disabled={!manage} onChange={(b) => setDraft({ ...draft, "search.enabled": b })} />
            <Switch label={L("تفعيل بحث الصور", "Image search enabled")} checked={!!draft["search.image_enabled"]} disabled={!manage} onChange={(b) => setDraft({ ...draft, "search.image_enabled": b })} />
            <div className="mt-3 grid gap-3">
              <Field label={L("البحث الآمن الافتراضي", "Default safe search")}>
                <select className="input" disabled={!manage} value={String(draft["search.safe_default"])} onChange={(e) => setDraft({ ...draft, "search.safe_default": e.target.value })}>
                  <option value="strict">{L("صارم", "Strict")}</option><option value="moderate">{L("معتدل", "Moderate")}</option><option value="off">{L("إيقاف", "Off")}</option>
                </select>
              </Field>
              <Field label={L("أقصى نتائج من نفس الموقع", "Max results per site")}>
                <input type="number" min={1} max={10} className="input" disabled={!manage} value={Number(draft["search.per_domain_limit"])} onChange={(e) => setDraft({ ...draft, "search.per_domain_limit": Number(e.target.value) })} />
              </Field>
            </div>
          </Card>
          <Card title={L("أوزان الترتيب", "Ranking weights")} className="lg:col-span-2">
            <div className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {WEIGHTS.map(([k, ar, en]) => (
                <label key={k} className="block text-sm">
                  <span className="flex justify-between"><span>{L(ar, en)}</span><span className="tabular-nums text-ink-muted">{(draft["search.ranking"][k] ?? 0).toFixed(1)}</span></span>
                  <input type="range" min={0} max={5} step={0.1} disabled={!manage} value={draft["search.ranking"][k] ?? 0} onChange={(e) => setW("search.ranking", k, Number(e.target.value))} className="w-full accent-lapis-600" />
                </label>
              ))}
            </div>
            <h3 className="mb-2 mt-5 text-sm font-semibold">{L("أولوية المناطق", "Regional priority")}</h3>
            <div className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
              {[["iq", "العراق", "Iraq"], ["arab", "الدول العربية", "Arab region"], ["global", "عالمي", "Global"]].map(([k, ar, en]) => (
                <label key={k} className="block text-sm">
                  <span className="flex justify-between"><span>{L(ar, en)}</span><span className="tabular-nums text-ink-muted">{(draft["search.region_priority"][k] ?? 0).toFixed(1)}</span></span>
                  <input type="range" min={0} max={3} step={0.1} disabled={!manage} value={draft["search.region_priority"][k] ?? 0} onChange={(e) => setW("search.region_priority", k, Number(e.target.value))} className="w-full accent-lapis-600" />
                </label>
              ))}
            </div>
            <p className="mt-3 text-xs text-ink-faint">{L("الأولوية العراقية تضاعف الصلة ولا تُضاف لها، فلا ترتفع صفحة عراقية ضعيفة فوق نتيجة مفيدة.", "Iraqi priority multiplies relevance rather than adding to it, so weak Iraqi pages never outrank useful results.")}</p>
          </Card>
        </div>
      )}

      <Card title={L("أولويات اللغات", "Language priorities")} className="mt-5">
        <Table rows={langs.data as unknown as Record<string, unknown>[] | undefined} rowKey={(r) => String(r.code)}
          cols={[{ key: "code", label: L("الرمز", "Code") }, { key: "native_name", label: L("اللغة", "Language") },
            { key: "enabled", label: L("مفعّلة", "Enabled"), render: (r) => <input type="checkbox" className="accent-lapis-600" disabled={!manage} defaultChecked={!!r.enabled}
              onChange={(e) => run(() => admin(`/languages/${r.code}`, { method: "PUT", body: { enabled: e.target.checked, priority: r.priority } }), { ok: L("حُدّثت", "Updated") })} /> },
            { key: "priority", label: L("الوزن", "Priority"), render: (r) => <input type="number" step={0.1} min={0} max={5} disabled={!manage} defaultValue={Number(r.priority)} className="input w-24"
              onBlur={(e) => run(() => admin(`/languages/${r.code}`, { method: "PUT", body: { enabled: r.enabled, priority: Number(e.target.value) } }), { ok: L("حُدّثت", "Updated") })} /> }]} />
      </Card>

      {can("search.test") && (
        <Card title={L("اختبار استعلام وشرح الترتيب", "Test a query & inspect ranking")} className="mt-5">
          <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); const r = await run(() => admin<SearchResponse>("/search/test", { body: { q } })); if (r) setTest(r); }}>
            <input value={q} onChange={(e) => setQ(e.target.value)} className="input" placeholder={L("مثال: شلون اطلع جواز", "e.g. passport renewal")} />
            <Btn disabled={!q || busy}><Play className="h-4 w-4" />{L("اختبار", "Test")}</Btn>
          </form>
          <p className="mt-2 text-xs text-ink-faint">{L("استعلامات الاختبار لا تُحفظ أيضاً.", "Test queries are not stored either.")}</p>
          {test && (
            <div className="mt-4">
              <div className="mb-2 text-sm text-ink-muted">{test.total} · {test.took_ms} ms {test.understood.length > 0 && `· ${test.understood.map((u) => `${u.raw}→${u.label}`).join("، ")}`}</div>
              <Table rows={test.results as unknown as Record<string, unknown>[]} cols={[
                { key: "title", label: L("النتيجة", "Result"), render: (r) => <div><div className="font-medium">{String(r.title)}</div><Url v={r.url} /></div> },
                { key: "score", label: L("النتيجة النهائية", "Score") },
                ...["relevance", "authority", "quality", "freshness", "regional_boost", "language_boost", "spam_penalty"].map((k) => ({
                  key: k, label: k, render: (r: Record<string, unknown>) => <span className="tabular-nums">{(r.explain as Record<string, number>)[k]?.toFixed(3)}</span> }))]} />
            </div>
          )}
        </Card>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title={L("تقييم جودة البحث", "Search quality evaluation")} actions={<>
          {manage && <Btn variant="outline" size="sm" onClick={() => setItems([...items, { query: "", expected_url: "" }])}><Plus className="h-3.5 w-3.5" />{L("إضافة", "Add")}</Btn>}
          {manage && <Btn variant="outline" size="sm" onClick={() => run(() => admin("/search/eval-set", { method: "PUT", body: { items: items.filter((i) => i.query && i.expected_url) } }), { ok: L("حُفظت المجموعة", "Saved") })}><Save className="h-3.5 w-3.5" /></Btn>}
          {can("search.test") && <Btn size="sm" onClick={async () => { const r = await run(() => admin<typeof evalRes>("/search/evaluate", { body: {} })); if (r) setEvalRes(r); }}><Play className="h-3.5 w-3.5" />{L("تقييم", "Evaluate")}</Btn>}
        </>}>
          <p className="mb-3 text-xs text-ink-muted">{L("استعلامات مرجعية يحددها الفريق مع الصفحة المتوقعة. تقيس MRR وP@1 وP@3.", "Reference queries with the expected page. Measures MRR, P@1 and P@3.")}</p>
          <div className="space-y-2">
            {items.map((it, i) => (
              <div key={i} className="flex gap-2">
                <input className="input" placeholder={L("الاستعلام", "Query")} value={it.query} disabled={!manage} onChange={(e) => setItems(items.map((x, j) => j === i ? { ...x, query: e.target.value } : x))} />
                <input className="input ltr-text" placeholder="https://" value={it.expected_url} disabled={!manage} onChange={(e) => setItems(items.map((x, j) => j === i ? { ...x, expected_url: e.target.value } : x))} />
                {manage && <Btn variant="ghost" size="sm" onClick={() => setItems(items.filter((_, j) => j !== i))} aria-label="remove"><Trash2 className="h-4 w-4" /></Btn>}
              </div>
            ))}
          </div>
          {evalRes && (
            <div className="mt-4">
              <div className="mb-3 grid grid-cols-3 gap-2"><Stat label="MRR" value={evalRes.mrr} /><Stat label="P@1" value={evalRes.p_at_1} /><Stat label="P@3" value={evalRes.p_at_3} /></div>
              <Table rows={evalRes.rows as unknown as Record<string, unknown>[]} cols={[{ key: "query", label: L("الاستعلام", "Query") },
                { key: "rank", label: L("الترتيب", "Rank"), render: (r) => r.rank ? <Badge value={`#${r.rank}`} map={{ "#1": "good" }} /> : <Badge value="miss" map={{ miss: "bad" }} /> }]} />
            </div>
          )}
        </Card>
        <Card title={L("مؤشرات الجودة والسبام", "Quality & spam")}>
          <div className="mb-4 grid grid-cols-2 gap-2">
            <Stat label={L("عمليات بحث 7 أيام", "Searches 7d")} value={quality.data?.searches_7d?.toLocaleString()} />
            <Stat label={L("نسبة بلا نتائج", "Zero-result rate")} value={quality.data?.zero_result_rate != null ? `${(quality.data.zero_result_rate * 100).toFixed(1)}%` : "—"} />
          </div>
          <Table rows={quality.data?.spam_signals} cols={[{ key: "signal", label: L("الإشارة", "Signal") }, { key: "n", label: L("صفحات", "Pages") }, { key: "avg_score", label: L("متوسط", "Avg") }]} />
          <h3 className="mb-2 mt-4 text-sm font-semibold">{L("أعلى صفحات بالسبام", "Top spam pages")}</h3>
          <Table rows={quality.data?.top_spam} cols={[{ key: "url", label: "URL", render: (r) => <Url v={r.url} /> }, { key: "spam_score", label: L("الدرجة", "Score") }]} />
        </Card>
      </div>
    </>
  );
}
