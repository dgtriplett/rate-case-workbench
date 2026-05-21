"""Prompts for the rate case application and major exhibits."""
import json

SYSTEM = """You are a senior regulatory affairs analyst at a US investor-owned utility,
drafting documents for filing with a state utility commission. Use formal regulatory
language. Cite schedules and witnesses by name. Numbers must be internally consistent
with the provided utility facts JSON. Where appropriate include numbered paragraphs,
section headers, and table-of-contents-style anchors. Do NOT invent facts — use only
those supplied. Length should match production rate-case documents: between 1,500
and 4,000 words for major documents, 800-1,500 for narrower exhibits.
"""


def application_messages(facts: dict, docket: str) -> list[dict]:
    user = (
        f"Draft the cover Application document for docket {docket}.\n\n"
        "Sections required (use ALL-CAPS headers):\n"
        "  I. INTRODUCTION AND SUMMARY OF REQUEST\n"
        "  II. STATEMENT OF JURISDICTION\n"
        "  III. THE COMPANY AND ITS SERVICE TERRITORY\n"
        "  IV. SUMMARY OF PROPOSED REVENUE REQUIREMENT\n"
        "  V. PROPOSED RATE OF RETURN AND CAPITAL STRUCTURE\n"
        "  VI. RATE BASE\n"
        "  VII. OPERATING EXPENSES AND O&M\n"
        "  VIII. DEPRECIATION\n"
        "  IX. RATE DESIGN AND CLASS COST ALLOCATION\n"
        "  X. CAPITAL INVESTMENT PLAN\n"
        "  XI. POLICY INITIATIVES (BENEFICIAL ELECTRIFICATION, LOW-INCOME DISCOUNT)\n"
        "  XII. SUPPORTING TESTIMONY AND EXHIBITS\n"
        "  XIII. REQUESTED RELIEF\n\n"
        "Reference the witnesses listed in the facts JSON by name where they support each section. "
        "End with a signature block from the General Counsel.\n\n"
        f"FACTS JSON:\n{json.dumps(facts, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


_EXHIBIT_TEMPLATES = {
    "rate_base_schedule": (
        "Draft Exhibit A — Rate Base Schedule narrative. Include a discussion of plant in service, "
        "accumulated depreciation, CWIP treatment, and working capital. Tie all numbers to the rate base "
        "shown in the facts JSON (current and proposed). Include a section on how plant additions during "
        "the test year are normalized. Reference workpapers WP-RB-01 through WP-RB-07."
    ),
    "cost_of_service_study": (
        "Draft Exhibit B — Cost-of-Service Study narrative (NOT the tables themselves). Explain the embedded "
        "cost methodology, classification of costs as demand/energy/customer, and the allocation factors used "
        "to assign costs to customer classes. Note where the Company's allocator selections differ from prior "
        "case (NLPG-22-005) and justify those changes. Author: Dr. Maria Calderón-Lefebvre."
    ),
    "depreciation_study": (
        "Draft Exhibit C — Depreciation Study Summary narrative. Use the Iowa Curve methodology for life and "
        "salvage estimates. Discuss key changes since the 2022 case, particularly proposed shortening of gas "
        "distribution main service lives reflecting decarbonization-driven asset retirements. Tie back to "
        "Witness Jonathan Akinwale-Petersen's testimony. Include a per-account narrative for FERC Accounts "
        "311-317 (steam production), 350-359 (transmission), 360-373 (distribution), and 376-387 (gas "
        "distribution mains and services)."
    ),
    "capital_plan": (
        "Draft Exhibit D — Five-Year Capital Investment Plan narrative covering 2026-2030. Use the annual "
        "capex numbers in the facts JSON. Provide a per-program breakdown: grid modernization (advanced "
        "metering, distribution automation, DERMS); wildfire mitigation (covered conductor, undergrounding, "
        "EFD detection); reliability (substation refurbishment, vegetation management); gas integrity "
        "(transmission integrity management, distribution main replacement); customer experience; and "
        "regulatory compliance. Cross-reference Rajesh Kothapalli-Nielsen's direct testimony."
    ),
    "roe_testimony_summary": (
        "Draft Exhibit E — ROE Recommendation Summary. Summarize Dr. Camille Bergstrom's analysis: proxy "
        "group selection criteria (10-12 publicly traded vertically integrated electric and combination "
        "utilities), DCF (constant growth and multi-stage variants), CAPM (with three risk-free-rate "
        "assumptions), and risk premium models. Present a recommended ROE range and point estimate. The "
        "Company's recommendation must equal the requested ROE in the facts JSON. Include a discussion of "
        "regulatory mechanisms (decoupling, riders, trackers) that may justify an above-median ROE."
    ),
}


def exhibit_messages(facts: dict, key: str) -> list[dict]:
    user = (
        f"{_EXHIBIT_TEMPLATES[key]}\n\n"
        f"FACTS JSON:\n{json.dumps(facts, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


EXHIBIT_KEYS = list(_EXHIBIT_TEMPLATES.keys())
