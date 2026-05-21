"""Witness expertise / coverage gap analysis.

Compares the canonical list of rate-case expertise areas against the
witnesses' declared expertise areas + the topic tags appearing on this
case's data requests and intervenor positions. Surfaces:

  - areas covered by ≥1 witness
  - areas with NO witness coverage (red flag)
  - areas with active DRs or positions but no witness assigned
  - LLM-generated suggestions for filling each gap (kind of consultant or
    in-house lookalike, sample search terms, etc.)
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import DataRequest, IntervenorPosition, Witness
from ..services.llm import chat as llm_chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/witnesses", tags=["witness-coverage"])


# Canonical set of rate-case expertise areas. Tuned for utility GRCs but
# generic enough to fit a variety of regulatory proceedings.
CANONICAL_AREAS: list[dict] = [
    {"key": "revenue_requirements", "label": "Revenue requirements & rate base", "criticality": "must"},
    {"key": "cost_of_service",      "label": "Cost-of-service / class allocation", "criticality": "must"},
    {"key": "rate_design",          "label": "Rate design & rate structure", "criticality": "must"},
    {"key": "roe_capital_structure","label": "Return on equity & capital structure", "criticality": "must"},
    {"key": "depreciation",         "label": "Depreciation / Iowa curves", "criticality": "must"},
    {"key": "capex_prudence",       "label": "Capital plan / capex prudence", "criticality": "must"},
    {"key": "om_expenses",          "label": "O&M / inflation indexing", "criticality": "should"},
    {"key": "customer_service",     "label": "Customer service & call-center metrics", "criticality": "should"},
    {"key": "low_income_programs",  "label": "Affordability / low-income programs", "criticality": "should"},
    {"key": "storm_resilience",     "label": "Storm hardening / resilience capex", "criticality": "should"},
    {"key": "decarbonization",      "label": "Decarbonization / beneficial electrification", "criticality": "should"},
    {"key": "gas_safety",           "label": "Gas distribution safety & main replacement", "criticality": "should"},
    {"key": "tax_amortization",     "label": "Tax / amortization & ADIT", "criticality": "should"},
    {"key": "regulatory_accounting","label": "Regulatory accounting & deferrals", "criticality": "should"},
    {"key": "load_forecasting",     "label": "Load forecasting & weather normalization", "criticality": "should"},
    {"key": "demand_response",      "label": "Demand response & energy efficiency", "criticality": "nice_to_have"},
    {"key": "cybersecurity",        "label": "Cybersecurity & grid resilience", "criticality": "nice_to_have"},
    {"key": "stakeholder_outreach", "label": "Stakeholder outreach & public engagement", "criticality": "nice_to_have"},
]


# Alias / keyword map — DR topic tags + intervenor topic strings get
# matched against canonical areas using these keywords (case-insensitive).
AREA_KEYWORDS: dict[str, list[str]] = {
    "revenue_requirements": ["revenue", "rate base", "working capital"],
    "cost_of_service": ["cost of service", "allocation", "class", "embedded cost"],
    "rate_design": ["rate design", "rate structure", "tier", "tariff"],
    "roe_capital_structure": ["roe", "return on equity", "capital structure", "cost of capital"],
    "depreciation": ["depreciation", "iowa curve", "service life", "net salvage"],
    "capex_prudence": ["capex", "capital plan", "imprudent", "prudent", "used and useful"],
    "om_expenses": ["o&m", "om expenses", "inflation", "wage", "operations"],
    "customer_service": ["customer service", "call center", "billing accuracy"],
    "low_income_programs": ["low income", "affordability", "lifeline", "discount"],
    "storm_resilience": ["storm", "resilience", "hardening", "ice storm"],
    "decarbonization": ["decarbonization", "beneficial electrification", "ghg", "clean energy"],
    "gas_safety": ["gas safety", "main replacement", "leak", "psma"],
    "tax_amortization": ["tax", "adit", "amortization", "deferred tax"],
    "regulatory_accounting": ["regulatory asset", "deferral", "sfas 71", "regulatory accounting"],
    "load_forecasting": ["forecast", "weather", "billing determinants", "normalization"],
    "demand_response": ["demand response", "energy efficiency", "dr program"],
    "cybersecurity": ["cyber", "security", "nerc cip"],
    "stakeholder_outreach": ["public input", "stakeholder", "community"],
}


class AreaCoverage(BaseModel):
    key: str
    label: str
    criticality: str
    witnesses: list[dict]
    open_drs: int
    positions: int
    coverage_status: str  # covered | thin | uncovered
    recommendation: Optional[str] = None


class CoverageReport(BaseModel):
    case_id: uuid.UUID
    areas: list[AreaCoverage]
    summary: dict


def _matches_area(text: str, area_key: str) -> bool:
    text_l = (text or "").lower()
    return any(kw in text_l for kw in AREA_KEYWORDS.get(area_key, []))


@router.get("/coverage", response_model=CoverageReport)
async def coverage(
    session: DBSession,
    _: CurrentUser,
    case_id: uuid.UUID = Query(...),
    with_recommendations: bool = Query(default=True),
) -> CoverageReport:
    witnesses = (await session.execute(select(Witness))).scalars().all()
    drs = (await session.execute(
        select(DataRequest).where(DataRequest.case_id == case_id)
    )).scalars().all()
    positions = (await session.execute(
        select(IntervenorPosition).where(IntervenorPosition.case_id == case_id)
    )).scalars().all()

    areas_out: list[AreaCoverage] = []
    uncovered_with_demand: list[AreaCoverage] = []

    for area in CANONICAL_AREAS:
        key = area["key"]

        # Witnesses covering this area (by declared expertise OR by name match)
        covered_by = []
        for w in witnesses:
            for e in (w.expertise_areas or []):
                if _matches_area(e, key) or e == key:
                    covered_by.append({"id": str(w.id), "name": w.name, "title": w.title})
                    break

        # DRs whose topic tags / subject mention this area
        open_drs = 0
        for d in drs:
            tag_text = " ".join(d.topic_tags or []) + " " + (d.subject or "")
            if _matches_area(tag_text, key) and d.status not in ("filed", "approved"):
                open_drs += 1

        # Intervenor positions touching this area
        pos_count = 0
        for p in positions:
            if _matches_area(p.topic + " " + (p.position_text or ""), key):
                pos_count += 1

        if covered_by:
            status = "covered" if len(covered_by) >= 2 else "thin"
        else:
            status = "uncovered"

        ac = AreaCoverage(
            key=key, label=area["label"], criticality=area["criticality"],
            witnesses=covered_by, open_drs=open_drs, positions=pos_count,
            coverage_status=status,
        )
        areas_out.append(ac)
        if status == "uncovered" and (open_drs > 0 or pos_count > 0 or area["criticality"] == "must"):
            uncovered_with_demand.append(ac)

    # LLM-generated recommendations for each truly-gappy area
    if with_recommendations and uncovered_with_demand:
        existing = ", ".join(
            f"{w.name} ({w.title or '—'}; expertise: {', '.join(w.expertise_areas or []) or 'unknown'})"
            for w in witnesses
        ) or "(no witnesses yet registered)"
        gaps_text = "\n".join(
            f"- {a.label} (criticality {a.criticality}; {a.open_drs} open DRs, "
            f"{a.positions} intervenor positions)"
            for a in uncovered_with_demand
        )
        prompt = (
            "You are advising a utility regulatory affairs team on witness "
            "lineup gaps for an active rate case. For each gap below, "
            "propose ONE specific recommendation in 1-2 sentences. Suggest "
            "either (a) a current in-house person to upskill, (b) the kind "
            "of outside consultant to retain (firm-type + role title + "
            "1-2 search keywords), or (c) merging coverage with an existing "
            "witness if appropriate. Be concrete.\n\n"
            f"EXISTING WITNESSES:\n{existing}\n\n"
            f"GAPS:\n{gaps_text}\n\n"
            "Return ONLY a JSON object: {\"recommendations\":[{\"area_key\":\"<key>\","
            "\"recommendation\":\"<text>\"}]}. No prose, no markdown fences."
        )
        try:
            raw = await llm_chat(
                [{"role": "user", "content": prompt}],
                max_tokens=1400, temperature=0.2,
            )
            import json, re
            s = raw.strip()
            if s.startswith("```"):
                s = re.sub(r"^```(?:json)?\s*", "", s)
                s = re.sub(r"\s*```\s*$", "", s)
            parsed = json.loads(s)
            recs = {r["area_key"]: r["recommendation"] for r in parsed.get("recommendations", [])}
            for a in areas_out:
                if a.key in recs:
                    a.recommendation = recs[a.key]
        except Exception:
            log.exception("coverage LLM recommendation failed")

    summary = {
        "total_areas": len(areas_out),
        "covered": sum(1 for a in areas_out if a.coverage_status == "covered"),
        "thin": sum(1 for a in areas_out if a.coverage_status == "thin"),
        "uncovered": sum(1 for a in areas_out if a.coverage_status == "uncovered"),
        "must_uncovered": sum(
            1 for a in areas_out
            if a.coverage_status == "uncovered" and a.criticality == "must"
        ),
        "open_drs_in_uncovered": sum(
            a.open_drs for a in areas_out if a.coverage_status == "uncovered"
        ),
    }
    return CoverageReport(case_id=case_id, areas=areas_out, summary=summary)
