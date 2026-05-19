// Central API client — all calls go through here
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface DocumentSummary {
  doc_id: string;
  source: string;
  doc_type: string;
  topic: string;
  date: string;
  tone: string;
  department: string;
  language: string;
  total_chunks: number;
}

export interface SearchResult {
  doc_id: string;
  source: string;
  score: number;
  excerpt: string;
  metadata: Record<string, string>;
}

export interface DraftRequest {
  topic: string;
  doc_type: string;
  tone: string;
  language: string;
  extra_instructions: string;
  selected_doc_ids: string[];
}

export interface Citation {
  ref_num: number;
  source: string;
  doc_id: string;
  excerpt: string;
  highlighted_text?: string;
}

export interface DraftResult {
  draft: string;
  citations: Citation[];
}

export interface RegenerateSelectionRequest {
  selected_text: string;
  instruction: string;
  full_draft: string;
  topic: string;
  doc_type: string;
  tone: string;
  language: string;
  citations?: Citation[];
}

// ── Documents ──────────────────────────────────────────────────────────────

export async function listDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>("/documents");
}

export async function deleteDocument(doc_id: string): Promise<void> {
  await request(`/documents/${doc_id}`, { method: "DELETE" });
}

export async function uploadDocument(
  file: File,
  meta: {
    doc_type: string;
    topic: string;
    date: string;
    tone: string;
    department: string;
    language: string;
  }
): Promise<{ doc_id: string; source: string; chunks: number }> {
  const form = new FormData();
  form.append("file", file);
  Object.entries(meta).forEach(([k, v]) => form.append(k, v));
  const res = await fetch(`${BASE}/documents/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

// ── Search ─────────────────────────────────────────────────────────────────

export async function searchDocuments(
  query: string,
  top_k = 8,
  filters: { doc_type?: string; language?: string; tone?: string } = {}
): Promise<SearchResult[]> {
  return request<SearchResult[]>("/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k, ...filters }),
  });
}

export async function previewDocument(doc_id: string): Promise<{ doc_id: string; text: string; metadata: Record<string, string> }> {
  return request(`/search/preview/${doc_id}`);
}

/** Returns a direct URL to stream the original PDF — open in an iframe or <a>. */
export function getPdfUrl(doc_id: string): string {
  return `${BASE}/search/pdf/${doc_id}`;
}

// ── Generation ─────────────────────────────────────────────────────────────

export async function generateDraft(req: DraftRequest): Promise<DraftResult> {
  return request<DraftResult>("/draft", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function refineDraft(current_draft: string, instruction: string, citations: Citation[] = []): Promise<string> {
  const data = await request<{ draft: string }>("/draft/refine", {
    method: "POST",
    body: JSON.stringify({ current_draft, instruction, citations }),
  });
  return data.draft;
}

export async function refineSection(section_text: string, instruction: string, context = ""): Promise<string> {
  const data = await request<{ draft: string }>("/draft/refine-section", {
    method: "POST",
    body: JSON.stringify({ section_text, instruction, context }),
  });
  return data.draft;
}

export async function regenerateSelection(req: RegenerateSelectionRequest): Promise<string> {
  const data = await request<{ draft: string }>("/draft/regenerate-selection", {
    method: "POST",
    body: JSON.stringify(req),
  });
  return data.draft;
}

// ── Export ─────────────────────────────────────────────────────────────────

export async function exportDocx(
  draft_text: string,
  filename = "draft"
): Promise<string> {
  const data = await request<{ filename: string }>("/export/docx", {
    method: "POST",
    body: JSON.stringify({ draft_text, filename, format: "docx" }),
  });
  return `${BASE}/export/download/${data.filename}`;
}
