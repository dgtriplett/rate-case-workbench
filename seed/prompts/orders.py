"""Prompts for commission final orders (closed cases)."""
import json

SYSTEM = """You draft Cascadia Public Utilities Commission FINAL ORDERS issued at the
close of a utility rate proceeding. Style:

- Begin with the docket caption, order number, and issuance date.
- Section I: Procedural History
- Section II: Issues Presented
- Section III: Discussion and Findings (subsections per issue: ROE, capital structure,
  rate base, O&M, depreciation, rate design, capex programs, policy initiatives)
- Section IV: Ordering Paragraphs (numbered, declarative)
- Signature block: signed by Commission Chair on behalf of the Commission

Use formal commission voice ("The Commission finds…", "We agree with Staff that…").
Numbers MUST match the outcomes provided in the facts JSON's prior_orders entry.
Length: 2,000-4,000 words.
"""


def order_messages(facts: dict, prior_order: dict) -> list[dict]:
    user = (
        f"Draft the full final order for docket {prior_order['docket']}, "
        f"order number {prior_order['order_no']}, issued {prior_order['issued_date']}.\n"
        f"The headline outcomes (which the order MUST resolve to) are:\n"
        f"  {json.dumps(prior_order['headline_outcomes'], indent=2)}\n\n"
        f"COMPANY FACTS JSON:\n{json.dumps(facts, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
