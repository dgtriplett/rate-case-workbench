/**
 * Typed fetch wrappers for the Rate Case Workbench backend.
 *
 * The backend serves both the SPA and the API. In production the API lives at
 * `/api/v1/*` on the same origin. In development the Vite proxy forwards `/api`
 * to `http://localhost:8000`.
 */

import type {
  CaseCreate,
  CaseOut,
  DataRequestAssign,
  DataRequestCreate,
  DataRequestOut,
  DocumentOut,
  DraftRequest,
  DraftResult,
  EventOut,
  FeatureFlagOut,
  GenieRoomIn,
  GenieRoomOut,
  KnowledgeSearchQuery,
  MemoryOut,
  ModelConfigIn,
  ModelConfigOut,
  PhaseOut,
  PhaseUpdate,
  PositionCheckResult,
  ResponseDraftIn,
  ResponseOut,
  SearchHit,
  TestimonyCreate,
  TestimonyOut,
  UploadResult,
  UserMeOut,
  VectorIndexOut,
  WitnessCreate,
  WitnessOut,
} from "./types";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public payload: unknown,
  ) {
    super(`API ${status} ${statusText}`);
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const finalHeaders = new Headers(headers);
  let body = rest.body as BodyInit | null | undefined;
  if (json !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  finalHeaders.set("Accept", "application/json");

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "same-origin",
    ...rest,
    headers: finalHeaders,
    body,
  });

  if (!res.ok) {
    let payload: unknown;
    try {
      payload = await res.json();
    } catch {
      try {
        payload = await res.text();
      } catch {
        payload = null;
      }
    }
    throw new ApiError(res.status, res.statusText, payload);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function qs(params: Record<string, unknown | undefined>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

// ---- Health / Identity -----------------------------------------------------

export const api = {
  health: () => request<{ status: string }>("/health"),
  me: () => request<UserMeOut>("/users/me"),

  // ---- Cases ----
  listCases: () => request<CaseOut[]>("/cases"),
  getCase: (id: string) => request<CaseOut>(`/cases/${id}`),
  createCase: (body: CaseCreate) =>
    request<CaseOut>("/cases", { method: "POST", json: body }),
  listPhases: (caseId: string) =>
    request<PhaseOut[]>(`/cases/${caseId}/phases`),
  updatePhase: (phaseId: string, body: PhaseUpdate) =>
    request<PhaseOut>(`/phases/${phaseId}`, { method: "PATCH", json: body }),

  // ---- Witnesses ----
  listWitnesses: (caseId?: string) =>
    request<WitnessOut[]>(`/witnesses${qs({ case_id: caseId })}`),
  createWitness: (body: WitnessCreate) =>
    request<WitnessOut>("/witnesses", { method: "POST", json: body }),

  // ---- Data requests ----
  listDataRequests: (params: {
    case_id?: string;
    status?: string;
    assigned_witness_id?: string;
    direction?: string;
  }) =>
    request<DataRequestOut[]>(`/data-requests${qs(params)}`),
  getDataRequest: (id: string) =>
    request<DataRequestOut>(`/data-requests/${id}`),
  createDataRequest: (body: DataRequestCreate) =>
    request<DataRequestOut>("/data-requests", { method: "POST", json: body }),
  assignDataRequest: (id: string, body: DataRequestAssign) =>
    request<DataRequestOut>(`/data-requests/${id}/assign`, {
      method: "POST",
      json: body,
    }),

  // ---- Responses ----
  getResponse: (id: string) => request<ResponseOut>(`/responses/${id}`),
  getCurrentResponse: (drId: string) =>
    request<ResponseOut | null>(`/data-requests/${drId}/response`),
  saveDraft: (drId: string, body: ResponseDraftIn) =>
    request<ResponseOut>(`/data-requests/${drId}/responses`, {
      method: "POST",
      json: body,
    }),
  submitResponse: (id: string) =>
    request<ResponseOut>(`/responses/${id}/submit`, { method: "POST" }),
  approveResponse: (id: string, comment?: string) =>
    request<ResponseOut>(`/responses/${id}/approve`, {
      method: "POST",
      json: { comment },
    }),
  fileResponse: (id: string) =>
    request<ResponseOut>(`/responses/${id}/file`, { method: "POST" }),

  // ---- Testimony ----
  listTestimony: (caseId?: string) =>
    request<TestimonyOut[]>(`/testimony${qs({ case_id: caseId })}`),
  getTestimony: (id: string) => request<TestimonyOut>(`/testimony/${id}`),
  createTestimony: (body: TestimonyCreate & { draft_text?: string }) =>
    request<TestimonyOut>("/testimony", { method: "POST", json: body }),
  updateTestimony: (id: string, body: Partial<TestimonyCreate>) =>
    request<TestimonyOut>(`/testimony/${id}`, { method: "PATCH", json: body }),
  submitTestimony: (id: string) =>
    request<TestimonyOut>(`/testimony/${id}/submit`, { method: "POST" }),
  approveTestimony: (id: string) =>
    request<TestimonyOut>(`/testimony/${id}/approve`, { method: "POST" }),
  fileTestimony: (id: string) =>
    request<TestimonyOut>(`/testimony/${id}/file`, { method: "POST" }),

  // ---- Checklist ----
  getChecklist: (kind: "response" | "testimony") =>
    request<{ kind: string; items: { id: string; title: string; description?: string }[] }>(
      `/checklist/${kind}`,
    ),
  evaluateChecklist: (body: {
    kind: "response" | "testimony";
    target_id?: string;
    text?: string;
    case_id?: string;
  }) =>
    request<{
      kind: string;
      items: {
        id: string;
        title: string;
        verdict: string;
        rationale: string;
        suggested_edit?: string | null;
        suggested_addendum?: string | null;
      }[];
    }>(`/checklist/evaluate`, { method: "POST", json: body }),

  // ---- Document content (UC-permissioned stream) ----
  documentContentUrl: (id: string) => `${API_BASE}/documents/${id}/content`,

  // ---- Rebuttal — intervenor positions ----
  listPositions: (caseId: string) =>
    request<import("./types").IntervenorPosition[]>(
      `/intervenor-positions${qs({ case_id: caseId })}`,
    ),
  createPosition: (body: Omit<import("./types").IntervenorPosition, "id" | "status" | "rebutted_by_testimony_id">) =>
    request<import("./types").IntervenorPosition>(`/intervenor-positions`, {
      method: "POST",
      json: body,
    }),
  linkRebuttal: (positionId: string, testimonyId: string) =>
    request<import("./types").IntervenorPosition>(
      `/intervenor-positions/${positionId}/link-rebuttal`,
      { method: "POST", json: { testimony_id: testimonyId } },
    ),

  // ---- Final order ----
  getOrder: (caseId: string) =>
    request<import("./types").CommissionOrder | null>(`/orders/by-case/${caseId}`),
  upsertOrder: (body: import("./types").CommissionOrder) =>
    request<import("./types").CommissionOrder>(
      `/orders/by-case/${body.case_id}`,
      { method: "PUT", json: body },
    ),

  // ---- Settlements ----
  listSettlements: (caseId: string) =>
    request<import("./types").Settlement[]>(`/settlements${qs({ case_id: caseId })}`),
  createSettlement: (body: import("./types").Settlement) =>
    request<import("./types").Settlement>(`/settlements`, { method: "POST", json: body }),
  updateSettlement: (id: string, body: import("./types").Settlement) =>
    request<import("./types").Settlement>(`/settlements/${id}`, { method: "PATCH", json: body }),

  // ---- Drafts iteration (download / upload / AI revise / auto-fix) ----
  draftDownloadUrl: (kind: "testimony" | "response", id: string, fmt: "docx" | "md" | "txt") =>
    `${API_BASE}/drafts/${kind}/${id}/download?fmt=${fmt}`,
  draftUploadUrl: (kind: "testimony" | "response", id: string) =>
    `${API_BASE}/drafts/${kind}/${id}/upload`,
  reviseDraft: (
    kind: "testimony" | "response",
    id: string,
    body: { instruction: string; additional_context?: string },
  ) =>
    request<{ id: string; new_text: string; summary: string }>(
      `/drafts/${kind}/${id}/revise`,
      { method: "POST", json: body },
    ),
  autoFixDraft: (kind: "testimony" | "response", id: string) =>
    request<{
      id: string;
      new_text: string;
      applied_items: { id: string; title: string; verdict: string }[];
      skipped_items: { id: string; title: string; verdict: string; reason: string }[];
    }>(`/drafts/${kind}/${id}/auto-fix`, { method: "POST" }),

  // ---- Hearings ----
  // ---- Witness coverage gap analysis ----
  witnessCoverage: (caseId: string) =>
    request<{
      case_id: string;
      summary: {
        total_areas: number;
        covered: number;
        thin: number;
        uncovered: number;
        must_uncovered: number;
        open_drs_in_uncovered: number;
      };
      areas: {
        key: string;
        label: string;
        criticality: "must" | "should" | "nice_to_have";
        witnesses: { id: string; name: string; title?: string | null }[];
        open_drs: number;
        positions: number;
        coverage_status: "covered" | "thin" | "uncovered";
        recommendation?: string | null;
      }[];
    }>(`/witnesses/coverage${qs({ case_id: caseId })}`),

  listHearings: (caseId: string) =>
    request<import("./types").Hearing[]>(`/hearings${qs({ case_id: caseId })}`),
  createHearing: (body: import("./types").Hearing) =>
    request<import("./types").Hearing>(`/hearings`, { method: "POST", json: body }),
  updateHearing: (id: string, body: import("./types").Hearing) =>
    request<import("./types").Hearing>(`/hearings/${id}`, { method: "PATCH", json: body }),

  // ---- Calendar ----
  listCalendarEvents: (params?: { case_id?: string; from_date?: string; to_date?: string }) =>
    request<any[]>(`/calendar${qs(params ?? {})}`),
  calendarIcsUrl: (case_id?: string) =>
    `${API_BASE}/calendar/ics${case_id ? `?case_id=${case_id}` : ""}`,

  // ---- Positions Ledger ----
  getPositionsLedger: (case_id: string, detect_drift = true) =>
    request<any>(`/positions-ledger${qs({ case_id, detect_drift })}`),

  // ---- Cross-case insights ----
  getCrossCaseInsights: (case_id: string) =>
    request<any>(`/cross-case${qs({ case_id })}`),

  // ---- Hearing prep / cross-exam Q&A ----
  listCrossExamQA: (case_id: string, hearing_id?: string, witness_id?: string) =>
    request<any[]>(`/cross-exam${qs({ case_id, hearing_id, witness_id })}`),
  createCrossExamQA: (body: any) =>
    request<any>(`/cross-exam`, { method: "POST", json: body }),
  updateCrossExamQA: (id: string, body: any) =>
    request<any>(`/cross-exam/${id}`, { method: "PATCH", json: body }),
  markPracticed: (id: string) =>
    request<any>(`/cross-exam/${id}/practiced`, { method: "POST" }),
  generateCrossExamQA: (body: { case_id: string; hearing_id: string; witness_id: string; max_questions?: number }) =>
    request<any[]>(`/cross-exam/generate`, { method: "POST", json: body }),

  // ---- Compliance ----
  listCompliance: (case_id: string) =>
    request<any[]>(`/compliance${qs({ case_id })}`),
  createCompliance: (body: any) =>
    request<any>(`/compliance`, { method: "POST", json: body }),
  updateCompliance: (id: string, body: any) =>
    request<any>(`/compliance/${id}`, { method: "PATCH", json: body }),
  seedComplianceFromOrder: (case_id: string) =>
    request<any[]>(`/compliance/seed-from-order/${case_id}`, { method: "POST" }),

  // ---- Portfolio ----
  getPortfolio: () => request<any>("/portfolio"),

  // ---- Automation ----
  listAutomationRules: () => request<any[]>("/automation/rules"),
  createAutomationRule: (body: any) =>
    request<any>("/automation/rules", { method: "POST", json: body }),
  updateAutomationRule: (id: string, body: any) =>
    request<any>(`/automation/rules/${id}`, { method: "PATCH", json: body }),
  deleteAutomationRule: (id: string) =>
    request<any>(`/automation/rules/${id}`, { method: "DELETE" }),
  evaluateAutomation: () =>
    request<any>("/automation/evaluate", { method: "POST" }),

  // ---- Presence ----
  presenceHeartbeat: (body: { target_kind: string; target_id: string }) =>
    request<any>("/presence/heartbeat", { method: "POST", json: body }),
  presenceList: (target_kind: string, target_id: string) =>
    request<any>(`/presence${qs({ target_kind, target_id })}`),

  // ---- Application Workbench (pre-filing) ----
  getWorkbenchSnapshot: (case_id: string) =>
    request<any>(`/application-workbench/snapshot${qs({ case_id })}`),
  upsertApplicationPackage: (case_id: string, body: any) =>
    request<any>(`/application-workbench/${case_id}`, { method: "PUT", json: body }),
  fileApplication: (case_id: string) =>
    request<any>(`/application-workbench/${case_id}/file`, { method: "POST" }),
  listFinancialSchedules: (case_id: string) =>
    request<any[]>(`/application-workbench/financial-schedules${qs({ case_id })}`),
  createFinancialSchedule: (body: any) =>
    request<any>(`/application-workbench/financial-schedules`, { method: "POST", json: body }),
  updateFinancialSchedule: (id: string, body: any) =>
    request<any>(`/application-workbench/financial-schedules/${id}`, { method: "PATCH", json: body }),
  deleteFinancialSchedule: (id: string) =>
    request<any>(`/application-workbench/financial-schedules/${id}`, { method: "DELETE" }),
  listCostOfService: (case_id: string) =>
    request<any[]>(`/application-workbench/cost-of-service${qs({ case_id })}`),
  createCostOfService: (body: any) =>
    request<any>(`/application-workbench/cost-of-service`, { method: "POST", json: body }),
  updateCostOfService: (id: string, body: any) =>
    request<any>(`/application-workbench/cost-of-service/${id}`, { method: "PATCH", json: body }),
  deleteCostOfService: (id: string) =>
    request<any>(`/application-workbench/cost-of-service/${id}`, { method: "DELETE" }),
  listRateDesign: (case_id: string) =>
    request<any[]>(`/application-workbench/rate-design${qs({ case_id })}`),
  createRateDesign: (body: any) =>
    request<any>(`/application-workbench/rate-design`, { method: "POST", json: body }),
  updateRateDesign: (id: string, body: any) =>
    request<any>(`/application-workbench/rate-design/${id}`, { method: "PATCH", json: body }),
  deleteRateDesign: (id: string) =>
    request<any>(`/application-workbench/rate-design/${id}`, { method: "DELETE" }),

  // ---- Parties / stakeholder registry ----
  listParties: (case_id: string) =>
    request<any[]>(`/parties${qs({ case_id })}`),
  createParty: (body: any) =>
    request<any>(`/parties`, { method: "POST", json: body }),
  updateParty: (id: string, body: any) =>
    request<any>(`/parties/${id}`, { method: "PATCH", json: body }),
  deleteParty: (id: string) =>
    request<any>(`/parties/${id}`, { method: "DELETE" }),

  // ---- Public comments ----
  listPublicComments: (case_id: string) =>
    request<any[]>(`/public-comments${qs({ case_id })}`),
  publicCommentsSummary: (case_id: string) =>
    request<any>(`/public-comments/summary${qs({ case_id })}`),
  createPublicComment: (body: any) =>
    request<any>(`/public-comments`, { method: "POST", json: body }),
  deletePublicComment: (id: string) =>
    request<any>(`/public-comments/${id}`, { method: "DELETE" }),
  ingestSocialComments: (case_id: string, body: any = {}) =>
    request<any>(`/public-comments/ingest-social${qs({ case_id })}`, { method: "POST", json: body }),

  // ---- ALJ Recommendation ----
  getAljRecommendation: (case_id: string) =>
    request<any>(`/alj-recommendation/by-case/${case_id}`),
  upsertAljRecommendation: (case_id: string, body: any) =>
    request<any>(`/alj-recommendation/by-case/${case_id}`, { method: "PUT", json: body }),
  compareAljVsOrder: (case_id: string) =>
    request<any>(`/alj-recommendation/compare/${case_id}`),

  // ---- Intervenor testimony (full filings) ----
  listIntervenorTestimony: (case_id: string) =>
    request<any[]>(`/intervenor-testimony${qs({ case_id })}`),
  createIntervenorTestimony: (body: any) =>
    request<any>(`/intervenor-testimony`, { method: "POST", json: body }),
  updateIntervenorTestimony: (id: string, body: any) =>
    request<any>(`/intervenor-testimony/${id}`, { method: "PATCH", json: body }),
  deleteIntervenorTestimony: (id: string) =>
    request<any>(`/intervenor-testimony/${id}`, { method: "DELETE" }),

  // ---- Public notices ----
  listPublicNotices: (case_id: string) =>
    request<any[]>(`/public-notices${qs({ case_id })}`),
  createPublicNotice: (body: any) =>
    request<any>(`/public-notices`, { method: "POST", json: body }),
  updatePublicNotice: (id: string, body: any) =>
    request<any>(`/public-notices/${id}`, { method: "PATCH", json: body }),
  draftPublicNotice: (case_id: string) =>
    request<any>(`/public-notices/draft/${case_id}`, { method: "POST" }),

  // ---- Documents / Knowledge ----
  listDocuments: (caseId?: string) =>
    request<DocumentOut[]>(`/documents${qs({ case_id: caseId })}`),
  uploadDocument: async (form: FormData) => {
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      body: form,
      credentials: "same-origin",
    });
    if (!res.ok) {
      let payload: unknown;
      try {
        payload = await res.json();
      } catch {
        payload = await res.text();
      }
      throw new ApiError(res.status, res.statusText, payload);
    }
    return (await res.json()) as UploadResult;
  },
  knowledgeSearch: (body: KnowledgeSearchQuery) =>
    request<SearchHit[]>("/knowledge/search", { method: "POST", json: body }),

  // ---- Memory ----
  listMemory: (params: { case_id?: string; topic_key?: string }) =>
    request<MemoryOut[]>(`/memory${qs(params)}`),

  // ---- Agent ----
  draft: (body: DraftRequest) =>
    request<DraftResult>("/agent/draft", { method: "POST", json: body }),
  positionCheck: (caseId: string, text: string) =>
    request<PositionCheckResult>("/agent/position-check", {
      method: "POST",
      json: { case_id: caseId, text },
    }),

  // ---- Admin ----
  admin: {
    listCases: () => request<CaseOut[]>("/admin/cases"),
    archiveCase: (id: string) =>
      request<CaseOut>(`/admin/cases/${id}/archive`, { method: "POST" }),
    listUsers: () => request<unknown[]>("/admin/users"),
    inviteUser: (body: {
      email: string;
      display_name: string;
      roles: string[];
      case_id?: string;
    }) => request("/admin/users", { method: "POST", json: body }),

    listModels: () => request<ModelConfigOut[]>("/admin/models"),
    upsertModel: (body: ModelConfigIn) =>
      request<ModelConfigOut>("/admin/models", { method: "POST", json: body }),
    deleteModel: (id: string) =>
      request(`/admin/models/${id}`, { method: "DELETE" }),

    listKnowledgeSources: (caseId?: string) =>
      request<VectorIndexOut[]>(
        `/admin/knowledge-sources${qs({ case_id: caseId })}`,
      ),
    reindexKnowledgeSource: (id: string) =>
      request<VectorIndexOut>(`/admin/knowledge-sources/${id}/reindex`, {
        method: "POST",
      }),

    listGenieRooms: () => request<GenieRoomOut[]>("/admin/genie"),
    upsertGenieRoom: (body: GenieRoomIn) =>
      request<GenieRoomOut>("/admin/genie", { method: "POST", json: body }),
    deleteGenieRoom: (id: string) =>
      request(`/admin/genie/${id}`, { method: "DELETE" }),

    listFeatureFlags: () => request<FeatureFlagOut[]>("/admin/feature-flags"),
    updateFeatureFlag: (id: string, enabled: boolean) =>
      request<FeatureFlagOut>(`/admin/feature-flags/${id}`, {
        method: "PATCH",
        json: { enabled },
      }),

    listPhaseTemplates: () =>
      request<unknown[]>("/admin/phase-templates"),
    upsertPhaseTemplate: (body: unknown) =>
      request("/admin/phase-templates", { method: "POST", json: body }),

    listIntegrations: () => request<unknown[]>("/admin/integrations"),
    upsertIntegration: (body: unknown) =>
      request("/admin/integrations", { method: "POST", json: body }),

    auditEvents: (params: {
      case_id?: string;
      target_kind?: string;
      since?: string;
      limit?: number;
    }) => request<EventOut[]>(`/admin/audit/events${qs(params)}`),
  },
};
