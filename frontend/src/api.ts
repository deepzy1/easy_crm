export type User = { id: string; name: string; email: string };
export type Workspace = {
  id: string;
  name: string;
  industry: string;
  website: string;
  description: string;
};
export type Stage = {
  id: string;
  name: string;
  position: number;
  color: string;
};
export type Lead = {
  id: string;
  name: string;
  company: string;
  email: string;
  phone: string;
  title: string;
  source: string;
  status: string;
  value: string;
  summary: string;
  stage_id: string;
  created_at: string;
  updated_at: string;
};
export type Note = {
  id: string;
  body: string;
  author_id: string;
  created_at: string;
};
export type Provider = {
  id: string;
  name: string;
  configured: boolean;
  models: string[];
};
export type Preference = { provider: string; model: string };
export type AISettings = {
  active: Preference | null;
  providers: Provider[];
  can_manage: boolean;
};
export type Generation = {
  text: string;
  provider: string;
  model: string;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number;
};
export type Overview = {
  total_leads: number;
  qualified_leads: number;
  active_leads: number;
  qualification_rate: number;
  sources: { source: string; count: number }[];
  pipeline: (Stage & { count: number; value: string })[];
  recent_leads: Lead[];
};
export const sources = [
  "manual",
  "website",
  "email",
  "referral",
  "whatsapp",
  "linkedin",
  "meta",
];
export const statuses = [
  "new",
  "qualifying",
  "qualified",
  "needs-human",
  "disqualified",
  "closed",
];
export const label = (s: string) =>
  ({
    whatsapp: "WhatsApp",
    linkedin: "LinkedIn",
    website: "Web form",
    meta: "Meta",
    "needs-human": "Needs human",
  })[s] || s.charAt(0).toUpperCase() + s.slice(1);
export const money = (value: string | number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
export const initials = (value: string) =>
  value
    .split(" ")
    .filter(Boolean)
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
export const api = async <T>(
  path: string,
  options: RequestInit = {},
): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Cannot reach EasyCRM. Check that the backend is running.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("session-expired"));
    const fields = body?.error?.details?.fields
      ?.map((f: { field: string }) => f.field.replace("body.", ""))
      .join(", ");
    throw new Error(
      (body?.error?.message || `Request failed (${response.status})`) +
        (fields ? `: ${fields}` : ""),
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
};
export async function allLeads(base: string, filter = ""): Promise<Lead[]> {
  const rows: Lead[] = [];
  let cursor: string | null = null;
  do {
    const result: { items: Lead[]; next_cursor: string | null } = await api(
      `${base}/leads?limit=200&${filter}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    rows.push(...result.items);
    cursor = result.next_cursor;
  } while (cursor);
  return rows;
}
