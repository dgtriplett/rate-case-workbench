"""Prompts for internal Company policy documents."""
import json

SYSTEM = """You draft INTERNAL Company policy documents used by Northern Light Power &
Gas Company's regulatory affairs team. These are NOT filed at the Commission; they
govern how the Company prepares filings. Style:

- Title page header: "INTERNAL — NOT FOR EXTERNAL DISTRIBUTION"
- Document control header: Document ID, Version, Owner, Last Reviewed, Next Review
- Section structure: Purpose, Scope, Definitions, Policy Statement, Procedures,
  Roles & Responsibilities, References, Revision History
- Voice: prescriptive ("The Company shall…", "Regulatory Affairs personnel must…")
- Length: 600-1,500 words

Output as plain text. Do NOT include privileged or attorney-client material; these
are operational policies, not legal advice.
"""

POLICY_TOPICS = [
    ("RAP-001", "Rate Case Document Production and Records Retention Policy"),
    ("RAP-002", "Cost-of-Service Study Methodology Standard"),
    ("RAP-003", "Depreciation Study Refresh Cycle and Iowa Curve Selection"),
    ("RAP-004", "Capital Project Justification and Used-and-Useful Documentation"),
    ("RAP-005", "Discovery Response Drafting and Review Standards"),
    ("RAP-006", "Witness Preparation and Testimony Filing Workflow"),
    ("RAP-007", "Affordability Program Design and Low-Income Discount Tiers"),
    ("RAP-008", "Beneficial Electrification Program Design Principles"),
]


def policy_messages(facts: dict, doc_id: str, title: str) -> list[dict]:
    user = (
        f"Draft internal policy document {doc_id}: \"{title}\".\n"
        f"Owner organization: VP Regulatory & External Affairs.\n\n"
        f"COMPANY FACTS JSON:\n{json.dumps(facts, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
