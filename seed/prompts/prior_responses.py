"""Prompts for prior-case responses filed by the Company (closed cases)."""
import json

SYSTEM = """You draft FILED responses to intervenor data requests. The response is from
the perspective of the utility (Northern Light Power & Gas Co.), addressing a prior
closed proceeding. Style:

- Begin with the response heading: docket, DR number, requester, date prepared.
- Open with a direct answer in 1-2 sentences.
- Provide supporting detail organized by the subparts of the request.
- Reference workpapers, schedules, and prior testimony by name.
- Use formal, professional language. Take a clear position.
- Where the question is quantitative, cite the specific number.
- End with: "Prepared by: <witness name>, <title>. Verified by: <regulatory affairs director>."

Output JSON ONLY:
{
  "responses": [
    {
      "dr_number": "STAFF-DR-001",
      "response_text": "<full response, 400-1200 words>",
      "filed_date": "YYYY-MM-DD",
      "prepared_by_witness_id": "W-002",
      "position_topic_tags": ["roe", "capital_structure", ...]
    },
    ...
  ]
}
"""


def batch_messages(facts: dict, prior_case: dict, requests: list[dict]) -> list[dict]:
    user = (
        f"Draft filed responses for the following data requests in docket {prior_case['docket']}.\n"
        f"That case was decided per {prior_case.get('order_no', 'final order')}; "
        f"headline outcomes: {prior_case.get('headline_outcomes', [])}.\n"
        f"Filed dates should fall within ~30-60 days after each request's issue date.\n\n"
        f"REQUESTS TO ANSWER:\n{json.dumps(requests, indent=2)}\n\n"
        f"COMPANY FACTS JSON:\n{json.dumps(facts, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
