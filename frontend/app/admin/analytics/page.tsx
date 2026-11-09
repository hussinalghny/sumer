"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Btn, Card, ErrorNote, PageHead, Stat, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type A = {
  series: { hour: string; searches: number | null; errors: number | null; zero_results: number | null; avg_latency_ms: number | null }[];
  distribution: { metric: string; dim: string; n: number }[]; coverage: { category: string; lang: string | null; n: number }[];
  iraqi_share: { iraqi: number; total: number }; crawler: { hour: string; fetched: number; errors: number; avg_ms: number | null }[]; note: string;
};
const hh = (iso: string) => { const d = new Date(iso); return `${d.getDate()}/${d.getMonth() + 1} ${d.getHours()}:00`; };

function Chart({ data, keys, kind = "area", height = 220 }: { data: Record<string, unknown>[]; keys: { k: string; name: string; color: string }[]; kind?: "area" | "bar" | "line"; height?: number }) {
  const L = useL();
  if (!data.length) return <div className="grid place-items-center text-sm text-ink-faint" style={{ height }}>{L("لا توجد بيانات بعد لهذه الفترة", "No data for this period yet")}</div>;
  const axes = <><CartesianGrid strokeDasharray="3 3" stroke="#8884" vertical={false} /><XAxis dataKey="x" fontSize={11} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip /></>;
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        {kind === "bar" ? <BarChart data={data}>{axes}{keys.map((k) => <Bar key={k.k} dataKey={k.k} name={k.name} fill={k.color} radius={[4, 4, 0, 0]} />)}</BarChart>
          : kind === "line" ? <LineChart data={data}>{axes}{keys.map((k) => <Line key={k.k} dataKey={k.k} name={k.name} stroke={k.color} strokeWidth={2} dot={false} />)}</LineChart>
          : <AreaChart data={data}>{axes}{keys.map((k) => <Area key={k.k} dataKey={k.k} name={k.name} stroke={k.color} fill={k.color} fillOpacity={.15} strokeWidth={2} />)}</AreaChart>}
      </ResponsiveContainer>
    </div>
  );
}

export default function Analytics() {
  const L = useL();
  const { run } = useAction();
  const [hours, setHours] = useState(48);
  const { data, error, reload } = useAdmin<A>(`/analytics?hours=${hours}`, 30000);
  const total = data?.series.reduce((s, r) => s + (r.searches ?? 0), 0) ?? 0;
  const errs = data?.series.reduce((s, r) => s + (r.errors ?? 0), 0) ?? 0;
  const lat = data?.series.filter((r) => r.avg_latency_ms != null);
  const dist = (m: string) => (data?.distribution ?? []).filter((d) => d.metric === m).map((d) => ({ x: d.dim, n: d.n }));
  const cov = Object.entries((data?.coverage ?? []).reduce<Record<string, number>>((a, r) => ({ ...a, [r.category]: (a[r.category] ?? 0) + r.n }), {})).map(([x, n]) => ({ x, n }));
  const covLang = Object.entries((data?.coverage ?? []).reduce<Record<string, number>>((a, r) => ({ ...a, [r.lang ?? "?"]: (a[r.lang ?? "?"] ?? 0) + r.n }), {})).map(([x, n]) => ({ x, n }));
  return (
    <>
      <PageHead title={L("تحليلات بدون تتبّع", "Analytics without tracking")} desc={data?.note}
        actions={<>
          <select className="input w-36" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={24}>{L("24 ساعة", "24 hours")}</option><option value={48}>{L("48 ساعة", "48 hours")}</option><option value={168}>{L("7 أيام", "7 days")}</option><option value={720}>{L("30 يوماً", "30 days")}</option></select>
          <Btn variant="outline" onClick={() => run(() => admin("/analytics/flush", { body: {} })).then(reload)}><RefreshCw className="h-4 w-4" />{L("تحديث", "Refresh")}</Btn></>} />
      <ErrorNote error={error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={L("إجمالي عمليات البحث", "Total searches")} value={total.toLocaleString()} />
        <Stat label={L("معدل الأخطاء", "Error rate")} value={total ? `${((errs / total) * 100).toFixed(2)}%` : "—"} tone={errs ? "warn" : "good"} />
        <Stat label={L("متوسط زمن الاستجابة", "Avg response")} value={lat?.length ? `${(lat.reduce((s, r) => s + (r.avg_latency_ms ?? 0), 0) / lat.length).toFixed(0)} ms` : "—"} />
        <Stat label={L("حصة المحتوى العراقي", "Iraqi content share")} value={data?.iraqi_share.total ? `${((data.iraqi_share.iraqi / data.iraqi_share.total) * 100).toFixed(0)}%` : "—"} />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title={L("عمليات البحث بالساعة", "Searches per hour")}><Chart data={(data?.series ?? []).map((r) => ({ ...r, x: hh(r.hour) }))} keys={[{ k: "searches", name: L("بحث", "Searches"), color: "#2447c8" }, { k: "zero_results", name: L("بلا نتائج", "Zero results"), color: "#c99a2e" }]} /></Card>
        <Card title={L("أداء خدمة البحث", "Search performance")}><Chart kind="line" data={(lat ?? []).map((r) => ({ ...r, x: hh(r.hour) }))} keys={[{ k: "avg_latency_ms", name: "ms", color: "#16a34a" }]} /></Card>
        <Card title={L("الأخطاء بالساعة", "Errors per hour")}><Chart kind="bar" data={(data?.series ?? []).map((r) => ({ ...r, x: hh(r.hour) }))} keys={[{ k: "errors", name: L("أخطاء", "Errors"), color: "#dc2626" }]} /></Card>
        <Card title={L("أداء الزاحف", "Crawler performance")}><Chart kind="bar" data={(data?.crawler ?? []).map((r) => ({ ...r, x: hh(r.hour) }))} keys={[{ k: "fetched", name: L("صفحات", "Pages"), color: "#2447c8" }, { k: "errors", name: L("أخطاء", "Errors"), color: "#dc2626" }]} /></Card>
        <Card title={L("لغات البحث", "Search languages")}><Chart kind="bar" data={dist("lang")} keys={[{ k: "n", name: L("بحث", "Searches"), color: "#2447c8" }]} /></Card>
        <Card title={L("توزيع فئات البحث", "Search category distribution")}><Chart kind="bar" data={dist("category")} keys={[{ k: "n", name: L("بحث", "Searches"), color: "#c99a2e" }]} /></Card>
        <Card title={L("تغطية الفهرس حسب التصنيف", "Index coverage by category")}><Chart kind="bar" data={cov} keys={[{ k: "n", name: L("مستندات", "Docs"), color: "#7c3aed" }]} /></Card>
        <Card title={L("تغطية الفهرس حسب اللغة", "Index coverage by language")}><Chart kind="bar" data={covLang} keys={[{ k: "n", name: L("مستندات", "Docs"), color: "#0891b2" }]} /></Card>
      </div>
    </>
  );
}
