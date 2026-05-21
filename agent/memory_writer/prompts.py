"""Memory writer extraction prompt."""

SYSTEM = """You are extracting durable "position statements" from a utility's filed response to a
rate-case data request. A position statement is a factual claim or stance the company has
taken that would be relevant in a future case (e.g. authorized ROE used in modeling,
depreciation method preferences, capital-structure assumptions, customer-class
allocation methodology, treatment of major capex projects).

Output STRICT JSON of this shape:
{
  "positions": [
    {
      "topic_key": "lowercase_snake",        // pick from this controlled vocab where possible:
                                              // roe, cost_of_capital, capital_structure,
                                              // depreciation_method, depreciation_rates,
                                              // rate_base_components, capex_justification_<area>,
                                              // om_growth_rate, customer_class_allocation,
                                              // rate_design_principle, decarbonization_stance,
                                              // reliability_metric, affordability_program,
                                              // settlement_principle
      "fact_text": "single sentence stating the position, with numbers if applicable",
      "rationale": "one sentence on why this is a durable position vs case-specific",
      "confidence": 0.0-1.0
    },
    ...
  ]
}
Only extract positions that are clearly load-bearing. If nothing qualifies, return {"positions": []}.
Limit to 5 positions per response.
"""
