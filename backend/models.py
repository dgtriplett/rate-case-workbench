"""SQLAlchemy ORM models — the canonical Lakebase Postgres schema for the Rate Case Workbench."""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RoleKey(str, enum.Enum):
    case_manager = "case_manager"
    witness = "witness"
    reviewer = "reviewer"
    approver = "approver"
    admin = "admin"
    viewer = "viewer"


class CaseStatus(str, enum.Enum):
    pre_filing = "pre_filing"
    active = "active"
    on_hold = "on_hold"
    closed = "closed"


class PhaseType(str, enum.Enum):
    pre_filing = "pre_filing"
    filing = "filing"
    discovery = "discovery"
    direct_testimony = "direct_testimony"
    rebuttal = "rebuttal"
    surrebuttal = "surrebuttal"
    hearing = "hearing"
    post_hearing_briefs = "post_hearing_briefs"
    order = "order"
    compliance = "compliance"


class PhaseStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    filed = "filed"
    closed = "closed"


class DRStatus(str, enum.Enum):
    new = "new"
    assigned = "assigned"
    drafting = "drafting"
    in_review = "in_review"
    approved = "approved"
    filed = "filed"
    objected = "objected"


class ResponseStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    filed = "filed"
    withdrawn = "withdrawn"


class TestimonyKind(str, enum.Enum):
    direct = "direct"
    rebuttal = "rebuttal"
    surrebuttal = "surrebuttal"
    initial_brief = "initial_brief"
    reply_brief = "reply_brief"


class DocumentKind(str, enum.Enum):
    filing = "filing"
    exhibit = "exhibit"
    order = "order"
    policy = "policy"
    upload = "upload"
    prior_case = "prior_case"
    testimony = "testimony"


class Classification(str, enum.Enum):
    public = "public"
    confidential = "confidential"
    privileged = "privileged"


# ---------------------------------------------------------------------------
# Identity & access
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    sso_subject: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[RoleKey] = mapped_column(SAEnum(RoleKey, name="role_key"), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()
    case: Mapped[Optional["Case"]] = relationship()


# ---------------------------------------------------------------------------
# Case hierarchy
# ---------------------------------------------------------------------------


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    docket_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(128), index=True)
    commission: Mapped[str] = mapped_column(String(255))
    utility_name: Mapped[str] = mapped_column(String(255))
    case_type: Mapped[str] = mapped_column(String(64), default="general_rate_case")
    description: Mapped[Optional[str]] = mapped_column(Text)
    filed_date: Mapped[Optional[date]] = mapped_column(Date)
    target_decision_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[CaseStatus] = mapped_column(SAEnum(CaseStatus, name="case_status"), default=CaseStatus.pre_filing)
    primary_case_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    phases: Mapped[list["CasePhase"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    data_requests: Mapped[list["DataRequest"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    testimony: Mapped[list["Testimony"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CasePhase(Base):
    __tablename__ = "case_phases"
    __table_args__ = (UniqueConstraint("case_id", "phase_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    phase_type: Mapped[PhaseType] = mapped_column(SAEnum(PhaseType, name="phase_type"))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[PhaseStatus] = mapped_column(SAEnum(PhaseStatus, name="phase_status"), default=PhaseStatus.not_started)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    deadline_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    case: Mapped[Case] = relationship(back_populates="phases")


# ---------------------------------------------------------------------------
# Witnesses
# ---------------------------------------------------------------------------


class Witness(Base):
    __tablename__ = "witnesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    expertise_areas: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    cv_uri: Mapped[Optional[str]] = mapped_column(Text)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Data requests + responses
# ---------------------------------------------------------------------------


class DataRequest(Base):
    __tablename__ = "data_requests"
    __table_args__ = (
        UniqueConstraint("case_id", "dr_number"),
        Index("ix_dr_status", "status"),
        Index("ix_dr_due", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    phase_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("case_phases.id"))
    dr_number: Mapped[str] = mapped_column(String(64))
    requester: Mapped[str] = mapped_column(String(255))  # e.g. "Staff", "Consumer Advocate"
    requester_kind: Mapped[Optional[str]] = mapped_column(String(64))  # staff|consumer_advocate|industrial|environmental|other
    issued_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[DRStatus] = mapped_column(SAEnum(DRStatus, name="dr_status"), default=DRStatus.new)
    priority: Mapped[str] = mapped_column(String(16), default="normal")  # low|normal|high|urgent
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    assigned_witness_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("witnesses.id"))
    assigned_reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    direction: Mapped[str] = mapped_column(String(16), default="inbound")  # inbound | outbound
    target_party_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("parties.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped[Case] = relationship(back_populates="data_requests")
    responses: Mapped[list["Response"]] = relationship(back_populates="data_request", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("data_request_id", "version"),
        Index("ix_response_current", "data_request_id", "is_current"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    data_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_requests.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    draft_text: Mapped[Optional[str]] = mapped_column(Text)
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    drafted_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    model_version: Mapped[Optional[str]] = mapped_column(String(255))
    agent_trace_id: Mapped[Optional[str]] = mapped_column(String(255))  # MLflow run id
    agent_reasoning: Mapped[Optional[dict]] = mapped_column(JSONB)  # cached agent steps
    privilege_flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[ResponseStatus] = mapped_column(
        SAEnum(ResponseStatus, name="response_status"), default=ResponseStatus.draft
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    filed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    data_request: Mapped[DataRequest] = relationship(back_populates="responses")
    citations: Mapped[list["ResponseCitation"]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )


class ResponseCitation(Base):
    __tablename__ = "response_citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    response_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(64))  # document|kb_chunk|genie_query|prior_response|prior_case
    source_id: Mapped[str] = mapped_column(String(255))
    label: Mapped[Optional[str]] = mapped_column(String(512))
    span_start: Mapped[Optional[int]] = mapped_column(Integer)
    span_end: Mapped[Optional[int]] = mapped_column(Integer)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    snippet: Mapped[Optional[str]] = mapped_column(Text)

    response: Mapped[Response] = relationship(back_populates="citations")


# ---------------------------------------------------------------------------
# Testimony
# ---------------------------------------------------------------------------


class Testimony(Base):
    __tablename__ = "testimony"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    phase_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("case_phases.id"))
    witness_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("witnesses.id"))
    kind: Mapped[TestimonyKind] = mapped_column(SAEnum(TestimonyKind, name="testimony_kind"))
    title: Mapped[str] = mapped_column(String(512))
    draft_text: Mapped[Optional[str]] = mapped_column(Text)
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    draft_uri: Mapped[Optional[str]] = mapped_column(Text)
    final_uri: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ResponseStatus] = mapped_column(
        SAEnum(ResponseStatus, name="response_status"), default=ResponseStatus.draft
    )
    # When this testimony is a rebuttal/surrebuttal of an intervenor position, link it
    rebuts_position_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped[Case] = relationship(back_populates="testimony")


# ---------------------------------------------------------------------------
# Opposing party (intervenor) positions — feed the rebuttal workbench
# ---------------------------------------------------------------------------


class IntervenorPosition(Base):
    __tablename__ = "intervenor_positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    intervenor: Mapped[str] = mapped_column(String(255))
    intervenor_kind: Mapped[Optional[str]] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(255))
    position_text: Mapped[str] = mapped_column(Text)
    source_citation: Mapped[Optional[str]] = mapped_column(Text)  # "Smith Direct, p.14"
    proposed_adjustment: Mapped[Optional[str]] = mapped_column(Text)
    impact_amount_m: Mapped[Optional[float]] = mapped_column()
    filed_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | rebutted | accepted | settled
    rebutted_by_testimony_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("testimony.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Final commission order / decision
# ---------------------------------------------------------------------------


class CommissionOrder(Base):
    __tablename__ = "commission_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), unique=True)
    order_number: Mapped[Optional[str]] = mapped_column(String(64))
    issued_date: Mapped[Optional[date]] = mapped_column(Date)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    authorized_revenue_increase_m: Mapped[Optional[float]] = mapped_column()
    authorized_roe_pct: Mapped[Optional[float]] = mapped_column()
    authorized_equity_pct: Mapped[Optional[float]] = mapped_column()
    capex_approved_m: Mapped[Optional[float]] = mapped_column()
    summary: Mapped[Optional[str]] = mapped_column(Text)
    full_text_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    compliance_filings_due: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Settlement negotiation
# ---------------------------------------------------------------------------


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    summary: Mapped[str] = mapped_column(Text)
    parties: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    proposed_revenue_increase_m: Mapped[Optional[float]] = mapped_column()
    proposed_roe_pct: Mapped[Optional[float]] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="proposed")  # proposed | accepted | rejected | filed
    proposed_date: Mapped[Optional[date]] = mapped_column(Date)
    decision_date: Mapped[Optional[date]] = mapped_column(Date)
    full_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Hearings
# ---------------------------------------------------------------------------


class Hearing(Base):
    __tablename__ = "hearings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    hearing_date: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    presiding_alj: Mapped[Optional[str]] = mapped_column(String(255))
    witness_lineup: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")  # scheduled | completed | cancelled
    kind: Mapped[str] = mapped_column(String(32), default="evidentiary")  # evidentiary | public
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Cross-examination Q&A bank
# ---------------------------------------------------------------------------


class CrossExamQA(Base):
    __tablename__ = "cross_exam_qa"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    hearing_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("hearings.id"))
    witness_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("witnesses.id"))
    topic: Mapped[str] = mapped_column(String(255))
    likely_questioner: Mapped[Optional[str]] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(Text)
    proposed_answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16), default="moderate")  # easy | moderate | hard
    source_citation: Mapped[Optional[str]] = mapped_column(Text)
    is_practiced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Compliance filings (post-order tracking)
# ---------------------------------------------------------------------------


class ComplianceFiling(Base):
    __tablename__ = "compliance_filings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("commission_orders.id"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(64))  # tariff_sheet | rate_transition | rider | accounting_order | report | other
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    filed_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="not_started")  # not_started | in_progress | filed | accepted
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Workflow automation rules (admin-configured)
# ---------------------------------------------------------------------------


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    trigger_kind: Mapped[str] = mapped_column(String(64))
    # trigger_kind in: dr_due_in_days | dr_status_change | response_filed |
    #                  position_logged_over_threshold | order_issued | testimony_submitted
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict)  # e.g. {"days": 2}
    action_kind: Mapped[str] = mapped_column(String(64))
    # action_kind in: notify | create_event | create_compliance_filing |
    #                 create_testimony_stub | post_audit
    action_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fire_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Live presence (who's looking at what right now)
# ---------------------------------------------------------------------------


class PresenceRecord(Base):
    __tablename__ = "presence_records"
    __table_args__ = (UniqueConstraint("user_id", "target_kind", "target_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_kind: Mapped[str] = mapped_column(String(64))  # testimony | response | brief
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Pre-filing: Application Workbench + supporting artifacts
# ---------------------------------------------------------------------------


class ApplicationPackage(Base):
    __tablename__ = "application_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    target_filing_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="in_prep")  # in_prep | ready | filed
    filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FinancialSchedule(Base):
    __tablename__ = "financial_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(64))  # income_statement|balance_sheet|cash_flow|rate_base|capex|om|custom
    status: Mapped[str] = mapped_column(String(32), default="not_started")  # not_started|in_progress|complete
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CostOfServiceStudy(Base):
    __tablename__ = "cost_of_service_studies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    study_type: Mapped[str] = mapped_column(String(64), default="embedded")
    source_uc_tables: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RateDesignProposal(Base):
    __tablename__ = "rate_design_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    proposed_structure: Mapped[dict] = mapped_column(JSONB, default=dict)
    bill_impact_summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Stakeholder registry — intervening parties + their counsel
# ---------------------------------------------------------------------------


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(64))  # utility|staff|consumer_advocate|industrial|environmental|individual|other
    counsel_name: Mapped[Optional[str]] = mapped_column(String(255))
    counsel_email: Mapped[Optional[str]] = mapped_column(String(255))
    counsel_firm: Mapped[Optional[str]] = mapped_column(String(255))
    intervention_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Public comments
# ---------------------------------------------------------------------------


class PublicComment(Base):
    __tablename__ = "public_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32), default="email")  # email|portal|letter|oral|social_media|other
    platform: Mapped[Optional[str]] = mapped_column(String(32))  # twitter|facebook|reddit|nextdoor|youtube
    source_handle: Mapped[Optional[str]] = mapped_column(String(128))
    commenter_name: Mapped[Optional[str]] = mapped_column(String(255))
    commenter_org: Mapped[Optional[str]] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    sentiment: Mapped[str] = mapped_column(String(16), default="neutral")  # positive|neutral|negative|mixed
    received_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# ALJ recommendation — distinct from final commission order
# ---------------------------------------------------------------------------


class ALJRecommendation(Base):
    __tablename__ = "alj_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), unique=True)
    alj_name: Mapped[Optional[str]] = mapped_column(String(255))
    issued_date: Mapped[Optional[date]] = mapped_column(Date)
    recommended_revenue_increase_m: Mapped[Optional[float]] = mapped_column()
    recommended_roe_pct: Mapped[Optional[float]] = mapped_column()
    recommended_equity_pct: Mapped[Optional[float]] = mapped_column()
    capex_recommended_m: Mapped[Optional[float]] = mapped_column()
    summary: Mapped[Optional[str]] = mapped_column(Text)
    positions_adopted: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    positions_rejected: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Intervenor testimony (full filings tracked as their own entity)
# ---------------------------------------------------------------------------


class IntervenorTestimony(Base):
    __tablename__ = "intervenor_testimony"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    party_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("parties.id"))
    witness_name: Mapped[str] = mapped_column(String(255))
    witness_title: Mapped[Optional[str]] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))  # direct | rebuttal | surrebuttal
    title: Mapped[str] = mapped_column(String(512))
    filed_date: Mapped[Optional[date]] = mapped_column(Date)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Public notices
# ---------------------------------------------------------------------------


class PublicNotice(Base):
    __tablename__ = "public_notices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)  # newspaper|web|bill_insert|email
    publication_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|approved|published
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Documents & knowledge
# ---------------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    title: Mapped[str] = mapped_column(String(512))
    kind: Mapped[DocumentKind] = mapped_column(SAEnum(DocumentKind, name="document_kind"))
    source: Mapped[Optional[str]] = mapped_column(String(128))
    uri: Mapped[str] = mapped_column(Text)
    sha256: Mapped[Optional[str]] = mapped_column(String(64))
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    classification: Mapped[Classification] = mapped_column(
        SAEnum(Classification, name="classification"), default=Classification.public
    )
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    text_preview: Mapped[str] = mapped_column(Text)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    char_start: Mapped[Optional[int]] = mapped_column(Integer)
    char_end: Mapped[Optional[int]] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Agent memory (the differentiator)
# ---------------------------------------------------------------------------


class AgentMemory(Base):
    __tablename__ = "agent_memory"
    __table_args__ = (
        Index("ix_memory_case_topic", "case_id", "topic_key"),
        Index("ix_memory_jurisdiction_topic", "jurisdiction", "topic_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(128))
    topic_key: Mapped[str] = mapped_column(String(255))
    fact_text: Mapped[str] = mapped_column(Text)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    source_response_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("responses.id"))
    source_testimony_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("testimony.id"))
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id"))
    confidence: Mapped[float] = mapped_column(default=0.8)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by_agent_run_id: Mapped[Optional[str]] = mapped_column(String(255))
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("agent_memory.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Approvals & comments
# ---------------------------------------------------------------------------


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    target_kind: Mapped[str] = mapped_column(String(64))  # response|testimony|filing
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))  # approved|rejected|needs_changes
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    target_kind: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Admin / settings
# ---------------------------------------------------------------------------


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("key", "scope", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(255))
    value_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    scope: Mapped[str] = mapped_column(String(32), default="global")  # global|case
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))  # purpose: drafter|summarizer|redactor|position_checker
    endpoint: Mapped[str] = mapped_column(String(255))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    scope: Mapped[str] = mapped_column(String(32), default="global")
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("key", "target_case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scope: Mapped[str] = mapped_column(String(32), default="global")
    target_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    description: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GenieRoom(Base):
    __tablename__ = "genie_rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    room_id: Mapped[str] = mapped_column(String(255), unique=True)
    label: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VectorIndex(Base):
    __tablename__ = "vector_indices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    index_name: Mapped[str] = mapped_column(String(512), unique=True)
    kind: Mapped[str] = mapped_column(String(64))  # case|jurisdiction|prior_responses
    endpoint_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_target", "target_kind", "target_id"),
        Index("ix_events_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    actor_email: Mapped[Optional[str]] = mapped_column(String(320))
    verb: Mapped[str] = mapped_column(String(128))
    target_kind: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("cases.id"))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
