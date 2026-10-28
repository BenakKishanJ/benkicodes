// API projections of the local pipeline (apps/pipeline/src/pipeline/api.py).
// Importers live only under /admin/ so these names never ship (PRD 02 §8.2).

export type RunStatus =
  | 'queued' | 'working' | 'awaiting_plan' | 'awaiting_review' | 'awaiting_refs'
  | 'paused_budget' | 'published' | 'failed' | 'rejected' | 'planning_done'
  | 'planning' | 'reviewing' | 'preparing_repo';

export interface RunItem {
  id: string;
  topic: string;
  mode: string;
  status: RunStatus | string;
  error: string | null;
  budget_cap: number | null;
  created_at: string;
  updated_at: string;
}

export interface Budget { cap: number; spent: number; warn: boolean; pause_exhausted: boolean }

export interface Usage extends Record<string, unknown> {
  usd?: number;
  budget?: Budget;
}

export interface SourceView {
  id: string; kind: string; title: string; url: string | null;
  trust: string; flags: string[]; chars: number; excerpt: string;
}

export interface IssueView {
  severity: 'high' | 'medium' | 'low';
  location: string; problem: string; fix: string;
}

export interface SeoView {
  title: string; description: string; slug: string;
  tags: string[]; category: string;
}

export interface CheckView {
  scores?: Record<string, number>;
  issues?: IssueView[] | null;
  unsupported_claims?: string[] | null;
  seo?: SeoView;
}

export interface GateView { id: string; level: string; status: string; detail?: string }

export interface EventView { t: string; node: string; msg: string; level: string }

export interface RunView {
  id: string;
  topic: string;
  mode: string;
  status: RunStatus | string;
  error: string | null;
  created_at: string;
  updated_at: string;
  pending: { type: string } | null;
  events: EventView[];
  sources: SourceView[];
  plan: { angle?: string; working_title?: string; sections?: { heading: string; goal: string; key_points?: unknown[] }[] } | null;
  plan_feedback: string[];
  draft_md: string;
  draft_html: string;
  diff: string;
  check: CheckView | null;
  gates: GateView[];
  seo: SeoView | null;
  revision_count: number;
  human_rounds: number;
  review_note: string;
  published: { file?: string; commit?: string; url?: string; tag?: string } | null;
  usage: Usage;
  calls: Record<string, unknown>[];
  course?: CourseRunView | null;
}

// ---- course (roadmap) pipeline projections /apps/pipeline/api.py view() ----
export interface CourseDoc { id: string; title: string; url: string; chars: number; excerpt?: string; has_images?: boolean }

export interface CourseRef {
  id: string; title: string; url: string;
  type: string; illustrated?: boolean; level?: string; why?: string; verified?: boolean;
}

export interface CourseStep { title: string; intent?: string; files?: string[] }

export interface PlannedPart {
  n: number; slug: string; title: string;
  objectives: string[]; concepts?: string[];
  steps: CourseStep[]; doc_urls?: string[]; ref_ids?: string[];
  resource_notes?: Record<string, string>; estimatedMinutes?: number;
}

export interface CoursePlanView {
  project: { name: string; slug: string; summary: string; stack: string[];
             architecture_md?: string; final_features: string[] };
  parts: PlannedPart[];
}

export interface CourseRepoView {
  path: string; name: string; package?: string; remote_url?: string | null;
  remote_ok?: boolean; empty_ok?: boolean; tagged?: string[];
}

export interface CourseRunView {
  docs: CourseDoc[];
  refs: CourseRef[];
  inspired_by: string[];
  repo: CourseRepoView | null;
  plan: CoursePlanView | null;
  plan_feedback: string[];
  published_parts?: unknown[];
}

export interface TaskSetting { model?: string; fallbacks?: string[]; purpose?: string }

export interface SettingsView {
  tasks: Record<string, TaskSetting>;
  publish_mode: string;
  branch: string;
  checkpoint_plan: boolean;
  site_base_url: string;
  default_budget_usd: number;
  course_budget_usd: number;
  api_key_configured: boolean;
}

export interface ModelEntry {
  id: string; name: string | null; context_length: number | null;
  in_per_mtok: number; out_per_mtok: number; structured: boolean;
}

export interface LibraryItem {
  file: string; slug: string; title: string; description: string;
  draft: boolean; pubDate: string; category: string; tags: string[];
}

export type PlanDecision = { action: 'approve' | 'revise'; comments: string[]; plan?: Record<string, unknown> | null };
export type ReviewDecision = {
  action: 'approve' | 'changes' | 'reject';
  comments: string[];
  edited_md?: string | null;
  seo?: Record<string, unknown> | null;
  force?: boolean;
};

// course interrupt resume payloads (mirror RefsDecision / CoursePlanDecision)
export type RefsDecision = {
  keep: string[];
  added: { title: string; url: string; type?: string; why?: string }[];
  inspired_by: string[];
};
export type CoursePlanDecision = { action: 'approve' | 'changes'; plan?: unknown | null; comments: string[] };
