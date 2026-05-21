/**
 * TypeScript types mirroring backend Pydantic schemas in backend/schemas.py
 * and SQLAlchemy enums in backend/models.py.
 */

export type RoleKey =
  | "case_manager"
  | "witness"
  | "reviewer"
  | "approver"
  | "admin"
  | "viewer";

export type CaseStatus = "pre_filing" | "active" | "on_hold" | "closed";

export const PHASE_TYPES = [
  "pre_filing",
  "filing",
  "discovery",
  "direct_testimony",
  "rebuttal",
  "surrebuttal",
  "hearing",
  "post_hearing_briefs",
  "order",
  "compliance",
] as const;
export type PhaseType = (typeof PHASE_TYPES)[number];

export type PhaseStatus = "not_started" | "in_progress" | "filed" | "closed";

export const DR_STATUSES = [
  "new",
  "assigned",
  "drafting",
  "in_review",
  "approved",
  "filed",
  "objected",
] as const;
export type DRStatus = (typeof DR_STATUSES)[number];

export type ResponseStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "filed"
  | "withdrawn";

export type TestimonyKind =
  | "direct"
  | "rebuttal"
  | "surrebuttal"
  | "initial_brief"
  | "reply_brief";

export type IntervenorPosition = {
  id: string;
  case_id: string;
  intervenor: string;
  intervenor_kind?: string | null;
  topic: string;
  position_text: string;
  source_citation?: string | null;
  proposed_adjustment?: string | null;
  impact_amount_m?: number | null;
  filed_date?: string | null;
  status: "open" | "rebutted" | "accepted" | "settled";
  rebutted_by_testimony_id?: string | null;
};

export type CommissionOrder = {
  id?: string;
  case_id: string;
  order_number?: string | null;
  issued_date?: string | null;
  effective_date?: string | null;
  authorized_revenue_increase_m?: number | null;
  authorized_roe_pct?: number | null;
  authorized_equity_pct?: number | null;
  capex_approved_m?: number | null;
  summary?: string | null;
  full_text_document_id?: string | null;
  compliance_filings_due?: string | null;
};

export type Settlement = {
  id?: string;
  case_id: string;
  summary: string;
  parties: string[];
  proposed_revenue_increase_m?: number | null;
  proposed_roe_pct?: number | null;
  status: "proposed" | "accepted" | "rejected" | "filed";
  proposed_date?: string | null;
  decision_date?: string | null;
  full_text?: string | null;
};

export type Hearing = {
  id?: string;
  case_id: string;
  title: string;
  hearing_date?: string | null;
  location?: string | null;
  presiding_alj?: string | null;
  witness_lineup: string[];
  topics: string[];
  notes?: string | null;
  status: "scheduled" | "completed" | "cancelled";
};

export type DocumentKind =
  | "filing"
  | "exhibit"
  | "order"
  | "policy"
  | "upload"
  | "prior_case"
  | "testimony";

export type Classification = "public" | "confidential" | "privileged";

export type Priority = "low" | "normal" | "high" | "urgent";

// ---- Identity ----

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
}

export interface UserMeOut extends UserOut {
  roles: RoleKey[];
  /** case_id -> [role_keys] */
  case_roles: Record<string, RoleKey[]>;
}

// ---- Cases / Phases ----

export interface CaseOut {
  id: string;
  name: string;
  docket_number: string;
  jurisdiction: string;
  commission: string;
  utility_name: string;
  case_type: string;
  description: string | null;
  filed_date: string | null;
  target_decision_date: string | null;
  status: CaseStatus;
  primary_case_manager_id: string | null;
  created_at: string;
}

export interface CaseCreate {
  name: string;
  docket_number: string;
  jurisdiction: string;
  commission: string;
  utility_name: string;
  case_type?: string;
  description?: string;
  filed_date?: string;
  target_decision_date?: string;
}

export interface PhaseOut {
  id: string;
  case_id: string;
  phase_type: PhaseType;
  sequence: number;
  status: PhaseStatus;
  start_date: string | null;
  end_date: string | null;
  deadline_date: string | null;
}

export interface PhaseUpdate {
  status?: PhaseStatus;
  start_date?: string;
  end_date?: string;
  deadline_date?: string;
  notes?: string;
}

// ---- Witnesses ----

export interface WitnessOut {
  id: string;
  name: string;
  title: string | null;
  expertise_areas: string[];
  is_external: boolean;
}

export interface WitnessCreate {
  name: string;
  title?: string;
  expertise_areas?: string[];
  is_external?: boolean;
  user_id?: string;
}

// ---- Data requests / responses ----

export interface DataRequestOut {
  id: string;
  case_id: string;
  phase_id: string | null;
  dr_number: string;
  requester: string;
  requester_kind: string | null;
  issued_date: string;
  due_date: string;
  subject: string;
  body: string;
  status: DRStatus;
  priority: Priority;
  topic_tags: string[];
  assigned_witness_id: string | null;
  assigned_reviewer_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataRequestCreate {
  case_id: string;
  phase_id?: string;
  dr_number: string;
  requester: string;
  requester_kind?: string;
  issued_date: string;
  due_date: string;
  subject: string;
  body: string;
  priority?: Priority;
  topic_tags?: string[];
}

export interface DataRequestAssign {
  assigned_witness_id?: string | null;
  assigned_reviewer_id?: string | null;
}

export interface CitationIn {
  source_type: string;
  source_id: string;
  label?: string;
  snippet?: string;
  page?: number;
  span_start?: number;
  span_end?: number;
}

export interface CitationOut {
  id: string;
  source_type: string;
  source_id: string;
  label: string | null;
  snippet: string | null;
  page: number | null;
}

export interface ResponseOut {
  id: string;
  data_request_id: string;
  version: number;
  is_current: boolean;
  draft_text: string | null;
  final_text: string | null;
  agent_trace_id: string | null;
  model_version: string | null;
  privilege_flags: string[];
  status: ResponseStatus;
  approved_by: string | null;
  approved_at: string | null;
  filed_at: string | null;
  created_at: string;
  updated_at: string;
  citations: CitationOut[];
}

export interface ResponseDraftIn {
  draft_text: string;
  agent_trace_id?: string;
  agent_reasoning?: Record<string, unknown>;
  model_version?: string;
  citations?: CitationIn[];
  privilege_flags?: string[];
}

// ---- Testimony ----

export interface TestimonyOut {
  id: string;
  case_id: string;
  phase_id: string | null;
  witness_id: string | null;
  kind: TestimonyKind;
  title: string;
  draft_text: string | null;
  final_text: string | null;
  status: ResponseStatus;
  filed_at: string | null;
  created_at: string;
}

export interface TestimonyCreate {
  case_id: string;
  phase_id?: string;
  witness_id?: string;
  kind: TestimonyKind;
  title: string;
  draft_text?: string;
}

// ---- Documents / Knowledge ----

export interface DocumentOut {
  id: string;
  case_id: string | null;
  title: string;
  kind: DocumentKind;
  uri: string;
  classification: Classification;
  page_count: number | null;
  summary: string | null;
  topic_tags: string[];
  ingested_at: string | null;
  indexed_at: string | null;
  created_at: string;
}

export interface UploadResult {
  document_id: string;
  title: string;
  uri: string;
  page_count: number | null;
  ingest_job_run_id?: string;
}

export interface KnowledgeSearchQuery {
  query: string;
  case_id?: string;
  scope?: "case" | "jurisdiction" | "both";
  top_k?: number;
}

export interface SearchHit {
  document_id: string;
  document_title: string;
  chunk_text: string;
  score: number;
  page: number | null;
}

// ---- Agent memory & drafting ----

export interface MemoryOut {
  id: string;
  case_id: string | null;
  jurisdiction: string | null;
  topic_key: string;
  fact_text: string;
  rationale: string | null;
  source_response_id: string | null;
  confidence: number;
  is_active: boolean;
  created_at: string;
}

export interface DraftRequest {
  data_request_id: string;
  user_instruction?: string;
  extra_context?: string;
}

export type DraftStepKind =
  | "plan"
  | "retrieval"
  | "genie"
  | "memory"
  | "tool"
  | "llm"
  | "final";

export interface DraftStep {
  kind: DraftStepKind;
  label: string;
  detail?: string;
}

export interface DraftResult {
  draft_text: string;
  citations: CitationIn[];
  steps: DraftStep[];
  agent_trace_id?: string;
  model_version?: string;
  position_warnings: string[];
}

export interface PositionWarning {
  topic_key: string;
  fact_text: string;
  severity: "info" | "warning" | "conflict";
  source_label: string;
}

export interface PositionCheckResult {
  warnings: PositionWarning[];
}

// ---- Admin ----

export interface ModelConfigOut {
  id: string;
  name: string;
  endpoint: string;
  params: Record<string, unknown>;
  is_default: boolean;
  scope: string;
}

export interface ModelConfigIn {
  name: string;
  endpoint: string;
  params?: Record<string, unknown>;
  is_default?: boolean;
}

export interface FeatureFlagOut {
  id: string;
  key: string;
  enabled: boolean;
  scope: string;
  description: string | null;
}

export interface GenieRoomOut {
  id: string;
  case_id: string | null;
  room_id: string;
  label: string;
  description: string | null;
  allowed_roles: string[];
}

export interface GenieRoomIn {
  room_id: string;
  label: string;
  description?: string;
  case_id?: string;
  allowed_roles?: string[];
}

export interface EventOut {
  id: string;
  actor_email: string | null;
  verb: string;
  target_kind: string;
  target_id: string | null;
  case_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface VectorIndexOut {
  id: string;
  case_id: string | null;
  index_name: string;
  kind: string;
  endpoint_name: string;
  created_at?: string;
  chunk_count?: number;
}
