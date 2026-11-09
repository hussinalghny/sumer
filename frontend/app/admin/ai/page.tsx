"use client";

import { Cpu, Download, Power } from "lucide-react";
import { useMe } from "@/components/admin/Shell";
import { Badge, Btn, Card, ErrorNote, PageHead, Stat, Table, useAction, useAdmin, useL } from "@/components/admin/ui";
import { admin } from "@/lib/api";

type Svc = { key: string; label_ar: string; label_en: string; state: string; package: string | null; package_installed: boolean; model_path: string | null; model_present: boolean; loaded: boolean; queue: number };
type AI = { services: Svc[]; resources: { process_rss_mb: number; gpu: { available: boolean; gpus?: { name: string; utilization: number; memory_used_mb: number; memory_total_mb: number }[] } }; models_dir: string };

const INSTALL: Record<string, string> = {
  speech: "pip install faster-whisper  # ثم ضع نموذج CTranslate2 في models/whisper",
  translation: "pip install ctranslate2 sentencepiece  # ثم حوّل NLLB-200 إلى models/translation",
  embeddings: "pip install sentence-transformers  # ثم ضع النموذج في models/embeddings",
  image_similarity: "pip install open_clip_torch  # ثم ضع النموذج في models/clip",
};

export default function AIPage() {
  const L = useL();
  const { can } = useMe();
  const { run, busy } = useAction();
  const { data, error, reload } = useAdmin<AI>("/ai/status", 10000);
  const gpu = data?.resources.gpu;
  return (
    <>
      <PageHead title={L("خدمات الذكاء الاصطناعي المحلية", "Local AI services")} desc={L("كل النماذج تعمل على خوادم المشغّل. لا توجد أي واجهة ذكاء اصطناعي خارجية.", "All models run on operator servers. No external AI APIs.")} />
      <ErrorNote error={error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={L("خدمات جاهزة", "Ready services")} value={data ? `${data.services.filter((s) => s.state === "ready").length} / ${data.services.length}` : "—"} />
        <Stat label={L("نماذج محمّلة", "Loaded models")} value={data?.services.filter((s) => s.loaded).length} />
        <Stat label={L("ذاكرة عملية API", "API process RAM")} value={data ? `${data.resources.process_rss_mb} MB` : "—"} />
        <Stat label="GPU" value={gpu?.available ? gpu.gpus?.map((g) => g.name).join(", ") : L("غير متوفر", "Not available")} />
      </div>
      {gpu?.available && (
        <Card title="GPU" className="mt-5">
          <Table rows={gpu.gpus as unknown as Record<string, unknown>[]} cols={[{ key: "name", label: "GPU" }, { key: "utilization", label: "%" }, { key: "memory_used_mb", label: "MB used" }, { key: "memory_total_mb", label: "MB total" }]} />
        </Card>
      )}
      <Card title={L("الخدمات", "Services")} className="mt-5">
        <Table rows={data?.services as unknown as Record<string, unknown>[] | undefined} rowKey={(r) => String(r.key)} cols={[
          { key: "label", label: L("الخدمة", "Service"), render: (r) => <div className="flex items-center gap-2"><Cpu className="h-4 w-4 text-ink-faint" />{L(String(r.label_ar), String(r.label_en))}</div> },
          { key: "state", label: L("الحالة", "State"), render: (r) => <Badge value={String(r.state)} /> },
          { key: "package_installed", label: L("المكتبة", "Package") }, { key: "model_present", label: L("النموذج", "Model") },
          { key: "loaded", label: L("محمّل", "Loaded") }, { key: "queue", label: L("بالطابور", "Queue") },
          { key: "x", label: "", render: (r) => r.state !== "ready" ? (INSTALL[String(r.key)] && <code className="ltr-text block max-w-sm whitespace-pre-wrap text-[11px] text-ink-muted">{INSTALL[String(r.key)]}</code>)
            : can("ai.manage") && ["speech", "translation"].includes(String(r.key)) && (r.loaded
              ? <Btn variant="outline" size="sm" disabled={busy} onClick={() => run(() => admin(`/ai/${r.key}/unload`, { body: {} }), { ok: L("أُلغي التحميل", "Unloaded") }).then(reload)}><Power className="h-3.5 w-3.5" />{L("إلغاء التحميل", "Unload")}</Btn>
              : <Btn size="sm" disabled={busy} onClick={() => run(() => admin(`/ai/${r.key}/load`, { body: {} }), { ok: L("حُمّل النموذج", "Model loaded") }).then(reload)}><Download className="h-3.5 w-3.5" />{L("تحميل", "Load")}</Btn>) }]} />
        <p className="mt-3 text-xs text-ink-faint">{L("مجلد النماذج", "Models directory")}: <span className="ltr-text">{data?.models_dir}</span>. {L("الخدمة غير الجاهزة تبقى معطّلة بالواجهة وترجع 503 بوضوح، ولا تُحاكى أبداً.", "Services that aren't ready stay disabled in the UI and return a clear 503; they are never simulated.")}</p>
      </Card>
    </>
  );
}
