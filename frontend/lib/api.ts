/** Fetch wrappers for every Clearance backend route.
 *  Base URL comes from NEXT_PUBLIC_API_URL (default: local backend). */

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Term { term: string; weight: number }

export interface CaseRecord {
  id: string;
  batch_id: string | null;
  filename: string;
  category: string | null;
  match_pct: number | null;
  status: "scored" | "rejected_unsafe" | "error";
  reject_reason: string | null;
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
  return ok(await fetch(`${BASE}/screen`, { method: "POST", body: form }));
}

export async function screenBatch(files: File[], jdText: string):
    Promise<BatchRecord> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("jd_text", jdText);
  return ok(await fetch(`${BASE}/batch`, { method: "POST", body: form }));
}

export const getCase = async (id: string): Promise<CaseRecord> =>
  ok(await fetch(`${BASE}/cases/${id}`));

export const listCases = async (limit = 50): Promise<CaseRecord[]> =>
  ok(await fetch(`${BASE}/cases?limit=${limit}`));

export const getBatch = async (id: string): Promise<BatchRecord> =>
  ok(await fetch(`${BASE}/batches/${id}`));

export const getBiasReport = async (): Promise<any> =>
  ok(await fetch(`${BASE}/bias-report`));

export const compareCases = async (ids: string[]):
    Promise<{ cases: CaseRecord[] }> =>
  ok(await fetch(`${BASE}/compare?case_ids=${ids.join(",")}`));
