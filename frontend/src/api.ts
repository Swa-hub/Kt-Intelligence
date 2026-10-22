const base = "/api";

export function getApiToken(): string {
  try { return localStorage.getItem("kt_api_token") || ""; } catch { return ""; }
}
export function setApiToken(v: string) {
  try {
    if (v) localStorage.setItem("kt_api_token", v);
    else localStorage.removeItem("kt_api_token");
  } catch {}
}

function authHeaders(): Record<string, string> {
  const t = getApiToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(base + path, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.error || body.detail || detail;
    } catch {}
    if (r.status === 401) detail = "Unauthorized. Set your API token in Settings.";
    throw new Error(detail);
  }
  return r.json();
}

export const api = {
  health: () => request<{ status: string; llm_configured: boolean; base_url: string; model: string; embed_model: string | null }>("/health"),

  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: number) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (name: string, description?: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  deleteProject: (id: number) => request<{ deleted: number }>(`/projects/${id}`, { method: "DELETE" }),

  upload: async (projectId: number, file: File, kind?: string): Promise<UploadResult> => {
    const form = new FormData();
    form.append("file", file);
    if (kind) form.append("kind", kind);
    const r = await fetch(`${base}/projects/${projectId}/upload`, {
      method: "POST",
      body: form,
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error || r.statusText);
    return r.json();
  },

  analyze: (projectId: number) => request<{ findings_created?: number; claims_examined: number; note?: string }>(
    `/projects/${projectId}/analyze`,
    { method: "POST" }
  ),
  findings: (projectId: number, params: { status?: string; severity?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.append("status", params.status);
    if (params.severity) qs.append("severity", params.severity);
    const q = qs.toString();
    return request<Finding[]>(`/projects/${projectId}/findings${q ? "?" + q : ""}`);
  },
  updateFinding: (id: number, status: string) =>
    request<Finding>(`/findings/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),

  chat: (projectId: number, question: string, level: string) =>
    request<ChatAnswer>(`/projects/${projectId}/chat`, { method: "POST", body: JSON.stringify({ question, level }) }),
  chatHistory: (projectId: number) => request<ChatMessage[]>(`/projects/${projectId}/chat`),
  learning: (projectId: number) => request<LearningProgress>(`/projects/${projectId}/learning`),
  overview: (projectId: number) => request<ProjectOverview>(`/projects/${projectId}/overview`, { method: "POST" }),
  quiz: (projectId: number, topic: string, n = 3) =>
    request<QuizResponse>(`/projects/${projectId}/quiz`, { method: "POST", body: JSON.stringify({ topic, n }) }),
  importGithub: (projectId: number, url: string) =>
    request<GitHubImportResult>(`/projects/${projectId}/import-github`, { method: "POST", body: JSON.stringify({ url }) }),
  getChunk: (chunkId: number) =>
    request<ChunkDetail>(`/chunks/${chunkId}`),
  exportUrl: (projectId: number) => `/api/projects/${projectId}/export`,
  attention: (projectId: number) => request<AttentionFeed>(`/projects/${projectId}/attention`),
  memoryEvents: (recordId: number) => request<MemoryEvent[]>(`/memory/${recordId}/events`),
  prCommentPreview: (projectId: number, changed_files: string[]) =>
    request<{ markdown: string }>(`/projects/${projectId}/pr-comment`, { method: "POST", body: JSON.stringify({ changed_files }) }),
  benchmark: () => request<BenchmarkResult>("/benchmark"),
  assignFinding: (id: number, owner: string | null) =>
    request<Finding>(`/findings/${id}/assign`, { method: "PATCH", body: JSON.stringify({ owner }) }),
  snoozeFinding: (id: number, until: string | null) =>
    request<Finding>(`/findings/${id}/snooze`, { method: "PATCH", body: JSON.stringify({ until }) }),
  recordQuizAttempt: (projectId: number, topic: string, question: string, correct: boolean) =>
    request<{ ok: true }>(`/projects/${projectId}/quiz/attempt`, {
      method: "POST",
      body: JSON.stringify({ topic, question, correct }),
    }),

  listMemory: (projectId: number, q?: string, status?: string) => {
    const qs = new URLSearchParams();
    if (q) qs.append("q", q);
    if (status) qs.append("status", status);
    const query = qs.toString();
    return request<MemoryRecord[]>(`/projects/${projectId}/memory${query ? "?" + query : ""}`);
  },
  createMemory: (projectId: number, body: Partial<MemoryRecord>) =>
    request<MemoryRecord>(`/projects/${projectId}/memory`, { method: "POST", body: JSON.stringify(body) }),
  updateMemory: (id: number, verification_status: string) =>
    request<MemoryRecord>(`/memory/${id}`, { method: "PATCH", body: JSON.stringify({ verification_status }) }),
};

export interface Project {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
}
export interface Source {
  id: number;
  kind: string;
  filename: string;
  size_bytes: number;
  created_at: string;
}
export interface ProjectDetail extends Project {
  sources: Source[];
  stats: { chunks: number; open_findings: number; total_findings: number; memory_records: number };
}
export interface Finding {
  id: number;
  project_id: number;
  category: string;
  severity: "low" | "medium" | "high";
  title: string;
  explanation: string;
  kt_evidence: { filename: string; start_line: number; end_line: number; excerpt: string } | null;
  code_evidence: any[] | null;
  suggested_question: string | null;
  confidence: number | null;
  status: string;
  owner: string | null;
  snoozed_until: string | null;
  created_at: string;
}
export interface ChatAnswer {
  answer: string;
  citations: Array<{ chunk_id: number; filename: string; kind: string; text: string; start_line: number; end_line: number }>;
  level: string;
}
export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: ChatAnswer["citations"] | null;
  created_at: string;
}
export interface ProjectOverview {
  purpose?: string;
  stack?: string[];
  entry_points?: Array<{ filename: string; note: string }>;
  modules?: Array<{ name: string; purpose: string; files: string[]; notes?: string }>;
  open_questions?: string[];
  error?: string;
  raw?: string;
  parse_error?: boolean;
}
export interface QuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  evidence_refs: Array<{ filename: string; start_line: number; end_line: number }>;
}
export interface QuizResponse {
  questions: QuizQuestion[];
  note?: string;
  parse_error?: boolean;
}
export interface LearningProgress {
  questions_asked: number;
  answers_received: number;
  files_covered: Array<{ filename: string; times_cited: number }>;
  frequent_topics: string[];
  quiz_by_topic: Array<{ topic: string; attempts: number; correct: number; accuracy: number }>;
  weak_topics: string[];
}
export interface BenchmarkResult {
  mode: "live" | "demo";
  bytes_ingested: number;
  files_ingested: number;
  claims_examined: number;
  findings_created: number;
  findings_by_severity: { high: number; medium: number; low: number };
  extraction_method: string;
  hero_contradiction_detected: boolean;
  timings_sec: { ingest: number; analyze: number; total: number };
}
export interface AttentionFeed {
  open_findings: Array<{ id: number; title: string; severity: "high" | "medium" | "low"; category: string; status: string; created_at: string }>;
  memory_needs_review: Array<{ id: number; topic: string; verification_status: string; updated_at: string }>;
}
export interface MemoryEvent {
  id: number;
  record_id: number;
  from_status: string | null;
  to_status: string;
  reason: string | null;
  actor: string | null;
  created_at: string;
}
export interface UploadResult {
  source_id: number;
  filename: string;
  kind: string;
  chunks: number;
  size_bytes: number;
  unchanged?: boolean;
  replaced_source_id?: number;
  flagged_memory_ids?: number[];
  transcribed_from?: string;
}
export interface GitHubImportResult {
  repo: string;
  branch: string;
  files_ingested: number;
  files_skipped: number;
  sources: Array<{ filename: string; kind: string; chunks: number }>;
}
export interface ChunkDetail {
  id: number;
  text: string;
  filename: string;
  start_line: number;
  end_line: number;
  kind: string;
}
export interface MemoryRecord {
  id: number;
  topic: string;
  content: string;
  verification_status: string;
  sources: any[] | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}
