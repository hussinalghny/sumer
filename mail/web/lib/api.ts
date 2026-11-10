export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method, credentials: "same-origin", cache: "no-store",
    headers: { ...(body !== undefined ? { "content-type": "application/json" } : {}), ...(method !== "GET" ? { "x-sumer-mail": "1" } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let code = String(r.status), message = "صار خطأ، حاول مرة ثانية.";
    try {
      const j = await r.json();
      const d = j.detail;
      if (typeof d === "object" && d) { code = d.code ?? code; message = d.message ?? message; }
      else if (typeof d === "string") { code = d; if (r.status === 429) message = d; }
    } catch { /* */ }
    if (r.status === 401) message = "انتهت الجلسة. أضف حسابك مرة ثانية.";
    throw new ApiError(r.status, code, message);
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => req<T>("GET", p),
  post: <T>(p: string, b?: unknown) => req<T>("POST", p, b ?? {}),
  del: <T>(p: string) => req<T>("DELETE", p),
};

export type Provider = { id: string; name: string; app_password: boolean; oauth_only: boolean; help_ar: string; help_url: string; imap_host: string; smtp_host: string; smtp_port: number };
export type Account = { id: string; email: string; display_name: string; provider: string; provider_name: string; label: string; sovereign: boolean; imap_host: string; smtp_host: string };
export type Stats = Partial<Record<"scanned" | "phishing" | "suspicious" | "trackers" | "reported", number>>;
export type SessionInfo = { active: boolean; accounts: Account[]; stats: Stats; expires_in?: number };
export type Reason = { code: string; title: string; detail: string; severity: "high" | "medium" | "low" };
export type Level = "safe" | "caution" | "danger";
export type Folder = "inbox" | "sent" | "trash" | "junk";
export type Summary = {
  account_id: string; folder: Folder; uid: string; subject: string; from: { name: string; email: string }; to: { name: string; email: string }[];
  date: string | null; seen: boolean; flagged: boolean; size: number; snippet: string; has_attachments: boolean;
  analysis: { level: Level; score: number; top: Reason[]; trackers: number } | null;
};
export type Attachment = { index: number; filename: string; size: number; content_type: string; risk?: "safe" | "caution" | "danger" };
export type Message = Omit<Summary, "analysis"> & {
  html: string; text: string; attachments: Attachment[]; cc: { name: string; email: string }[]; reply_to: string[];
  message_id: string; references: string;
  analysis: { level: Level; score: number; reasons: Reason[]; trackers: number; auth: Record<string, string> };
  links: { href: string; text: string; host: string; flags: string[] }[]; remote_images: number; images_shown: boolean;
};
