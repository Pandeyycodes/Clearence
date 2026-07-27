/** Fetch wrappers for every Clearance backend route.
 *  Base URL comes from NEXT_PUBLIC_API_URL (default: local backend). */

// Use 127.0.0.1 (not "localhost") by default: on Windows "localhost" often
// resolves to IPv6 ::1 first, but the dev backend binds IPv4 only, which
// surfaces in the browser as "Failed to fetch". Override with NEXT_PUBLIC_API_URL.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ------------------------------------------------------------------- auth
const TOKEN_KEY = "clearance_token";

export const getToken = (): string | null =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);

export const isAuthed = (): boolean => !!getToken();

export function logout() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = "/login";
  }
}

/** Exchange email + password for a JWT (stored in localStorage). */
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Incorrect email or password.");
  const { access_token } = await res.json();
  localStorage.setItem(TOKEN_KEY, access_token);
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export interface Term { term: string; weight: number }

export interface CaseRecord {
  id: string;
  batch_id: string | null;
  filename: string;
  category: string | null;
  match_pct: number | null;
  status: "scored" | "rejected_unsafe" | "error";
  reject_reason: string | null;
  screened_by: string | null;
  created_at: string | null;
  fields_redacted: string[];
  redacted_preview: string | null;
  matched_skills: string[];
  missing_skills: string[];
  top_terms: Term[];
  match_method: string;
  unique_skills?: string[];
}

export interface BatchRecord {
  batch_id: string;
  jd_text: string;
  created_at?: string;
  cases: CaseRecord[];
}

async function ok<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    // Token missing or expired — send the user back to log in.
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export async function screen(file: File, jdText: string): Promise<CaseRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("jd_text", jdText);
  return ok(await fetch(`${BASE}/screen`,
    { method: "POST", body: form, headers: authHeaders() }));
}

export async function screenBatch(files: File[], jdText: string):
    Promise<BatchRecord> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("jd_text", jdText);
  return ok(await fetch(`${BASE}/batch`,
    { method: "POST", body: form, headers: authHeaders() }));
}

export const getCase = async (id: string): Promise<CaseRecord> =>
  ok(await fetch(`${BASE}/cases/${id}`, { headers: authHeaders() }));

export const listCases = async (limit = 50): Promise<CaseRecord[]> =>
  ok(await fetch(`${BASE}/cases?limit=${limit}`, { headers: authHeaders() }));

export const getBatch = async (id: string): Promise<BatchRecord> =>
  ok(await fetch(`${BASE}/batches/${id}`, { headers: authHeaders() }));

export const getBiasReport = async (): Promise<any> =>
  ok(await fetch(`${BASE}/bias-report`, { headers: authHeaders() }));

export const compareCases = async (ids: string[]):
    Promise<{ cases: CaseRecord[] }> =>
  ok(await fetch(`${BASE}/compare?case_ids=${ids.join(",")}`,
    { headers: authHeaders() }));
