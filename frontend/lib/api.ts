export type Seg = { t: string; h: boolean };
export type Result = {
  url: string; title: string; host: string; lang: string | null; category: string; doc_type: string;
  indexed_at: string | null; published_at: string | null; title_hl: Seg[]; snippet: Seg[]; iraqi: boolean;
  source?: "web";
  score?: number; explain?: Record<string, number>;
};
export type SearchResponse = {
  query: string; page: number; total: number; took_ms: number; results: Result[];
  corrected: string | null; did_you_mean: string | null; understood: { raw: string; label: string; kind: string }[];
  related: string[]; panel: null | { title: string; description: string | Seg[]; url: string; host: string; category: string; verified: boolean };
  lang: string | null;
  local_total?: number; web_provider?: string | null;
};
export type PublicConfig = {
  name_ar: string; name_en: string; tagline_ar: string; tagline_en: string; logo: string | null;
  default_lang: string; default_theme: string; maintenance: boolean; announcement: { enabled: boolean; ar: string; en: string } | null;
  languages: { code: string; native_name: string; direction: string }[];
  features: { images: boolean; voice: boolean; translation: boolean; reverse_image: boolean; web_fallback?: boolean }; safe_default: string;
};

export class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail); }
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* نص غير JSON */ }
    throw new ApiError(r.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json() as Promise<T>;
}

export function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
    credentials: "same-origin", cache: "no-store" }).then(handle<T>);
}

export function upload<T>(path: string, form: FormData): Promise<T> {
  return fetch(path, { method: "POST", body: form, credentials: "same-origin", cache: "no-store" }).then(handle<T>);
}

export function get<T>(path: string): Promise<T> {
  return fetch(path, { credentials: "same-origin", cache: "no-store" }).then(handle<T>);
}

// ===== لوحة التحكم: كوكي الجلسة HttpOnly + توكن CSRF في الترويسة =====
let csrf = "";
export function setCsrf(t: string) { csrf = t; }

export async function admin<T>(path: string, init: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const method = init.method ?? (init.body !== undefined || init.form ? "POST" : "GET");
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(`/api/admin${path}`, { method, headers, credentials: "same-origin", cache: "no-store",
    body: init.form ?? (init.body !== undefined ? JSON.stringify(init.body) : undefined) });
  return handle<T>(r);
}
