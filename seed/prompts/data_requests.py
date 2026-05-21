"""Prompts for generating intervenor data requests."""
import json

SYSTEM = """You draft data requests (a/k/a discovery requests, interrogatories) that
intervenors serve on a utility during a rate case. Each request must:

- Use the official numbering format: <REQUESTER_PREFIX>-DR-NNN (e.g., "STAFF-DR-001")
- Have a single, specific SUBJECT line (max 120 chars)
- Have a numbered, multi-part BODY (1-5 subparts is realistic)
- Reference specific schedules, workpapers, or testimony pages where appropriate
- Use the requester's characteristic voice and concerns (staff = neutral/comprehensive;
  consumer advocate = affordability, ROE skepticism, capex discipline; industrial
  intervenor = rate design, demand vs. energy allocation; environmental intervenor =
  decarbonization, beneficial electrification, gas system reductions)

Output JSON ONLY (no commentary), matching this schema:
{
  "requests": [
    {
      "dr_number": "STAFF-DR-001",
      "requester": "CPUC-X Staff",
      "requester_kind": "staff|consumer_advocate|industrial|environmental|other",
      "subject": "string",
      "body": "string (multi-paragraph, numbered subparts)",
      "topic_tags": ["roe", "depreciation", ...],
      "priority": "low|normal|high|urgent",
      "echoes_prior_case": null | "NLPG-22-005"
    },
    ...
  ]
}
"""


def batch_messages(
    facts: dict,
    docket: str,
    batch_size: int,
    start_index_by_requester: dict[str, int],
    prefer_prior_case_echoes: bool = False,
) -> list[dict]:
    user = (
        f"Generate {batch_size} data requests for docket {docket}.\n"
        f"Distribute requesters roughly: 40% staff, 25% consumer_advocate, "
        f"20% industrial, 15% environmental.\n"
        f"Numbering: continue from these counts: {json.dumps(start_index_by_requester)}.\n"
    )
    if prefer_prior_case_echoes:
        user += (
            "\nIMPORTANT: For at least HALF of these requests, the subject and body should "
            "closely echo a request that was already answered in the prior closed case "
            "NLPG-22-005 (e.g., similar phrasing about ROE proxy groups, similar capex "
            "justification asks, similar depreciation life questions). Set echoes_prior_case "
            "to 'NLPG-22-005' for those. The goal is to demonstrate that cross-case agent "
            "memory can detect re-asked questions.\n"
        )
    user += f"\nFACTS JSON:\n{json.dumps(facts, indent=2)}"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
