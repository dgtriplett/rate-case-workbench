"""Pydantic request/response schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Users / Roles -----------------------------------------------------------


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool


class UserMeOut(UserOut):
    roles: list[str]
    case_roles: dict[str, list[str]]  # case_id (str) -> [role_keys]


# --- Cases / Phases ---------------------------------------------------------


class CaseCreate(BaseModel):
    name: str
    docket_number: str
    jurisdiction: str
    commission: str
    utility_name: str
    case_type: str = "general_rate_case"
    description: Optional[str] = None
    filed_date: Optional[date] = None
    target_decision_date: Optional[date] = None


class CaseOut(ORMModel):
    id: uuid.UUID
    name: str
    docket_number: str
    jurisdiction: str
    commission: str
    utility_name: str
    case_type: str
    description: Optional[str]
    filed_date: Optional[date]
    target_decision_date: Optional[date]
    status: str
    primary_case_manager_id: Optional[uuid.UUID]
    created_at: datetime


class PhaseOut(ORMModel):
    id: uuid.UUID
    case_id: uuid.UUID
    phase_type: str
    sequence: int
    status: str
    start_date: Optional[date]
    end_date: Optional[date]
    deadline_date: Optional[date]


class PhaseUpdate(BaseModel):
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    deadline_date: Optional[date] = None
    notes: Optional[str] = None


# --- Witnesses --------------------------------------------------------------


class WitnessCreate(BaseModel):
    name: str
    title: Optional[str] = None
    expertise_areas: list[str] = Field(default_factory=list)
    is_external: bool = False
    user_id: Optional[uuid.UUID] = None


class WitnessOut(ORMModel):
    id: uuid.UUID
    name: str
    title: Optional[str]
    expertise_areas: list[str]
    is_external: bool


# --- Data Requests ----------------------------------------------------------


class DataRequestCreate(BaseModel):
    case_id: uuid.UUID
    phase_id: Optional[uuid.UUID] = None
    dr_number: str
    requester: str
    requester_kind: Optional[str] = None
    issued_date: date
    due_date: date
    subject: str
    body: str
    priority: str = "normal"
    topic_tags: list[str] = Field(default_factory=list)


class DataRequestAssign(BaseModel):
    assigned_witness_id: Optional[uuid.UUID] = None
    assigned_reviewer_id: Optional[uuid.UUID] = None


class DataRequestOut(ORMModel):
    id: uuid.UUID
    case_id: uuid.UUID
    phase_id: Optional[uuid.UUID]
    dr_number: str
    requester: str
    requester_kind: Optional[str]
    issued_date: date
    due_date: date
    subject: str
    body: str
    status: str
    priority: str
    topic_tags: list[str]
    assigned_witness_id: Optional[uuid.UUID]
    assigned_reviewer_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


# --- Responses --------------------------------------------------------------


class ResponseDraftIn(BaseModel):
    draft_text: str
    agent_trace_id: Optional[str] = None
    agent_reasoning: Optional[dict[str, Any]] = None
    model_version: Optional[str] = None
    citations: list["CitationIn"] = Field(default_factory=list)
    privilege_flags: list[str] = Field(default_factory=list)


class CitationIn(BaseModel):
    source_type: str
    source_id: str
    label: Optional[str] = None
    snippet: Optional[str] = None
    page: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None


class CitationOut(ORMModel):
    id: uuid.UUID
    source_type: str
    source_id: str
    label: Optional[str]
    snippet: Optional[str]
    page: Optional[int]


class ResponseOut(ORMModel):
    id: uuid.UUID
    data_request_id: uuid.UUID
    version: int
    is_current: bool
    draft_text: Optional[str]
    final_text: Optional[str]
    agent_trace_id: Optional[str]
    model_version: Optional[str]
    privilege_flags: list[str]
    status: str
    approved_by: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    filed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    citations: list[CitationOut] = Field(default_factory=list)


class ApproveIn(BaseModel):
    comment: Optional[str] = None


# --- Testimony --------------------------------------------------------------


class TestimonyCreate(BaseModel):
    case_id: uuid.UUID
    phase_id: Optional[uuid.UUID] = None
    witness_id: Optional[uuid.UUID] = None
    kind: str
    title: str
    draft_text: Optional[str] = None


class TestimonyOut(ORMModel):
    id: uuid.UUID
    case_id: uuid.UUID
    phase_id: Optional[uuid.UUID]
    witness_id: Optional[uuid.UUID]
    kind: str
    title: str
    draft_text: Optional[str]
    final_text: Optional[str]
    status: str
    filed_at: Optional[datetime]
    created_at: datetime


# --- Documents / Knowledge --------------------------------------------------


class DocumentOut(ORMModel):
    id: uuid.UUID
    case_id: Optional[uuid.UUID]
    title: str
    kind: str
    uri: str
    classification: str
    page_count: Optional[int]
    summary: Optional[str]
    topic_tags: list[str]
    ingested_at: Optional[datetime]
    indexed_at: Optional[datetime]
    created_at: datetime


class UploadResult(BaseModel):
    document_id: uuid.UUID
    title: str
    uri: str
    page_count: Optional[int]
    ingest_job_run_id: Optional[str] = None


class KnowledgeSearchQuery(BaseModel):
    query: str
    case_id: Optional[uuid.UUID] = None
    scope: str = "case"  # case|jurisdiction|both
    top_k: int = 8


class SearchHit(BaseModel):
    document_id: uuid.UUID
    document_title: str
    chunk_text: str
    score: float
    page: Optional[int] = None


# --- Agent memory -----------------------------------------------------------


class MemoryOut(ORMModel):
    id: uuid.UUID
    case_id: Optional[uuid.UUID]
    jurisdiction: Optional[str]
    topic_key: str
    fact_text: str
    rationale: Optional[str]
    source_response_id: Optional[uuid.UUID]
    confidence: float
    is_active: bool
    created_at: datetime


# --- Agent drafting ---------------------------------------------------------


class DraftRequest(BaseModel):
    data_request_id: uuid.UUID
    user_instruction: Optional[str] = None
    extra_context: Optional[str] = None


class DraftStep(BaseModel):
    kind: str  # plan|retrieval|genie|memory|tool|llm|final
    label: str
    detail: Optional[str] = None


class DraftResult(BaseModel):
    draft_text: str
    citations: list[CitationIn]
    steps: list[DraftStep]
    agent_trace_id: Optional[str] = None
    model_version: Optional[str] = None
    position_warnings: list[str] = Field(default_factory=list)


class PositionCheckRequest(BaseModel):
    case_id: uuid.UUID
    text: str


class PositionWarning(BaseModel):
    topic_key: str
    fact_text: str
    severity: str  # info|warning|conflict
    source_label: str


class PositionCheckResult(BaseModel):
    warnings: list[PositionWarning]


# --- Admin ------------------------------------------------------------------


class ModelConfigIn(BaseModel):
    name: str
    endpoint: str
    params: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ModelConfigOut(ORMModel):
    id: uuid.UUID
    name: str
    endpoint: str
    params: dict[str, Any]
    is_default: bool
    scope: str


class FeatureFlagOut(ORMModel):
    id: uuid.UUID
    key: str
    enabled: bool
    scope: str
    description: Optional[str]


class FeatureFlagUpdate(BaseModel):
    enabled: bool


class GenieRoomIn(BaseModel):
    room_id: str
    label: str
    description: Optional[str] = None
    case_id: Optional[uuid.UUID] = None
    allowed_roles: list[str] = Field(default_factory=list)


class GenieRoomOut(ORMModel):
    id: uuid.UUID
    case_id: Optional[uuid.UUID]
    room_id: str
    label: str
    description: Optional[str]
    allowed_roles: list[str]


class EventOut(ORMModel):
    id: uuid.UUID
    actor_email: Optional[str]
    verb: str
    target_kind: str
    target_id: Optional[uuid.UUID]
    case_id: Optional[uuid.UUID]
    payload: dict[str, Any]
    created_at: datetime
