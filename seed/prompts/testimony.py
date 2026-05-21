"""Prompts for direct testimony of each witness."""
import json

SYSTEM = """You draft direct testimony for utility-commission rate proceedings.
Format strictly as Q&A: alternating "Q." (presiding ALJ / counsel) and "A." (witness)
lines. Open with personal background (3-5 Q&A pairs covering name, position, tenure,
qualifications, prior testimony). Then proceed through the substantive topics. Close
with "Q. Does this conclude your direct testimony? A. Yes, it does."

Use formal regulatory voice. Numbers must match the supplied facts JSON. Include
references to specific schedules ("WP-DR-3" style), and to the work of other
witnesses where supporting their analysis. Length: 1,200-2,500 words per testimony.
"""


def testimony_messages(facts: dict, witness: dict, docket: str) -> list[dict]:
    user = (
        f"Draft direct testimony for the following witness in docket {docket}:\n\n"
        f"WITNESS:\n{json.dumps(witness, indent=2)}\n\n"
        "Cover, at minimum:\n"
        "  1. Background & qualifications\n"
        "  2. Purpose of testimony\n"
        "  3. Summary of recommendations\n"
        "  4. Detailed support for each recommendation in the witness's area\n"
        "  5. Response to anticipated intervenor concerns\n"
        "  6. Conclusion\n\n"
        "Customize the substantive sections based on the witness's expertise (e.g., the CFO covers "
        "revenue requirement and cost of capital; the depreciation manager covers Iowa Curves, mortality "
        "studies, net salvage; the rate design director covers cost-of-service classifications and rate "
        "structure proposals; the external cost-of-capital expert covers DCF, CAPM, proxy groups).\n\n"
        f"FACTS JSON:\n{json.dumps(facts, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
