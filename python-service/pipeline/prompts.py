"""
prompts.py  —  Phase 2 versioned system prompt and context builder for
                LLM-assisted semantic mapping.

The context builder receives a full profiler output dict and emits a
compact, JSON-serializable context that includes only safe metadata
(name, inferred_type, sample_values, unique_count, null_percentage,
candidate_roles). No full dataset, no API keys, no secrets.
"""

SYSTEM_PROMPT_VERSION = "semantic-mapping-v1"

VALID_ROLES = [
    "date", "revenue", "quantity", "price", "cost", "shipping",
    "marketing", "discount", "tax", "profit",
    "customer", "product", "category",
    "city", "country", "region",
    "order_id", "customer_id", "product_id", "invoice_id", "transaction_id",
    "payment", "channel", "status",
]

ROLE_DESCRIPTIONS = {
    "date":          "Transaction or order date (required for time-series analysis).",
    "revenue":       "Revenue, sales amount, or invoice total.",
    "quantity":      "Number of units sold.",
    "price":         "Unit or selling price.",
    "cost":          "Cost of goods sold (COGS).",
    "shipping":      "Shipping or delivery cost.",
    "marketing":     "Marketing, ad spend, or advertising cost.",
    "discount":      "Discount or coupon amount.",
    "tax":           "Tax, GST, VAT, or similar.",
    "profit":        "Gross or net profit.",
    "customer":      "Customer name, email, phone, or ID (customer dimension).",
    "product":       "Product name, SKU, or variant (product dimension).",
    "category":      "Product category or type.",
    "city":          "City name (shipping or billing).",
    "country":       "Country name.",
    "region":        "Region, state, province, or territory.",
    "order_id":      "Unique order identifier (transaction key).",
    "customer_id":   "Unique customer identifier.",
    "product_id":    "Unique product identifier.",
    "invoice_id":    "Unique invoice identifier.",
    "transaction_id": "Unique transaction identifier.",
    "payment":       "Payment method (credit card, cash, etc.).",
    "channel":       "Sales channel or source (online, retail, etc.).",
    "status":        "Order or delivery status.",
}

SYSTEM_PROMPT = f"""You are a business-data column mapper for BizSight, a tool for SME owners.

You receive compact metadata about each column in a business dataset and must
return a JSON object mapping every column to its most likely semantic role.

VALID ROLES (return exactly one of these strings, or null for unmapped):
{chr(10).join(f"  - {r}: {ROLE_DESCRIPTIONS[r]}" for r in VALID_ROLES)}

RULES:
1. Return exactly this JSON structure:
   {{"mappings": [{{"column": "<name>", "role": "<role or null>", "confidence": <0.0-1.0>, "reason": "<short explanation>"}}]}}

2. Every column from the input must appear exactly once in the mappings array.
3. Set role to null when you are not confident (confidence < 0.5).
4. confidence must be a float between 0.0 and 1.0.
5. One primary role per column. Do NOT invent roles not listed above.
6. Never invent columns that do not exist in the input.
7. If a business field is missing from the dataset (e.g. no marketing column),
   do NOT map any column to that role — leave it null.
8. Identifiers (order_id, customer_id, product_id, invoice_id, transaction_id)
   should only be assigned to columns that are clearly unique identifiers,
   not to measure columns.
9. Numeric measures (revenue, cost, quantity, price, etc.) must not be
   assigned to identifier or categorical columns.
10. For date columns, prefer the "date" role. If a column is clearly an
    order date, "date" is correct.
11. Respond ONLY with valid JSON. No markdown, no explanation outside the JSON.
"""


def build_llm_context(profile: dict) -> dict:
    """
    Convert a full profiler output into a compact LLM context.

    The returned dict is safe to serialize to JSON and send to the LLM.
    It contains:
        - dataset: row/column count, file type, sheet name
        - columns: per-column compact metadata (name, inferred_type,
                   sample_values (max 5), null_percentage, unique_count,
                   candidate_roles from the profiler)
        - relationships: cross-sheet key hints (Excel only)

    The caller should merge _system_prompt and _user_prompt keys before
    passing to the LLM provider.
    """
    dataset_meta = profile.get("dataset", {})
    columns_in  = profile.get("columns", [])
    detected    = profile.get("detected_fields", {})
    rels        = profile.get("relationships", [])

    # invert detected_fields: column -> [{role, confidence}]
    col_candidates: dict[str, list[dict]] = {}
    for role, entries in detected.items():
        for entry in entries:
            col_candidates.setdefault(entry["column"], []).append({
                "role": role,
                "confidence": entry["confidence"],
            })

    compact_columns = []
    for col in columns_in:
        compact_columns.append({
            "name": col["name"],
            "inferred_type": col.get("inferred_type", "text"),
            "sample_values": col.get("sample_values", [])[:5],
            "null_percentage": col.get("null_percentage", 0.0),
            "unique_count": col.get("unique_count", 0),
            "candidate_roles": col_candidates.get(col["name"], []),
        })

    compact_context = {
        "dataset": {
            "row_count": dataset_meta.get("row_count", 0),
            "column_count": dataset_meta.get("column_count", 0),
            "file_type": profile.get("file_type", "unknown"),
            "primary_sheet": dataset_meta.get("primary_sheet_candidate", "unknown"),
            "has_date": profile.get("date_analysis", {}).get("has_date", False),
        },
        "columns": compact_columns,
        "identifiers": [
            {"column": e["column"], "possible_type": e.get("possible_type", "identifier"),
             "confidence": e.get("confidence", 0.0)}
            for e in profile.get("identifiers", [])
        ],
        "relationships": rels[:6] if rels else [],
    }

    user_prompt = (
        "Below is compact metadata about each column in a business dataset. "
        "Assign the most appropriate semantic role to each column.\n\n"
        f"```json\n{_json_pretty(compact_context)}\n```"
    )

    return {
        "context": compact_context,
        "_system_prompt": SYSTEM_PROMPT,
        "_user_prompt": user_prompt,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_pretty(obj) -> str:
    """Pretty-print JSON, escaping nothing extra (safe for prompts)."""
    import json as _json
    return _json.dumps(obj, indent=2, default=str)


# ===========================================================================
# Phase 7 — Business Advisor (LLM-assisted interpretation of verified facts)
# ===========================================================================

BUSINESS_ADVISOR_PROMPT_VERSION = "business-advisor-v1"

# Advisor response schema shown to the LLM. This is the contract the Python
# validator enforces (see pipeline/advisor.py).
_BUSINESS_ADVISOR_SCHEMA_EXAMPLE = {
    "summary": "Your summary (1-3 sentences).",
    "health": {
        "overall": "positive | mixed | negative | insufficient_data",
        "explanation": "Short explanation capturing the overall picture.",
    },
    "priorities": [
        {
            "title": "Short actionable title",
            "action": "Recommended action",
            "reason": "Why this matters, grounded in verified facts",
            "priority": "high | medium | low",
            "impact": "high | medium | low",
            "effort": "high | medium | low",
            "fact_ids": ["FACT_REVENUE", "FACT_GROSS_MARGIN"],
        }
    ],
    "opportunities": [
        {
            "title": "Opportunity title",
            "explanation": "Explanation (may note it is a hypothesis worth investigating)",
            "action": "Suggested action",
            "fact_ids": ["FACT_TOP_PRODUCT"],
        }
    ],
    "risks": [
        {
            "title": "Risk title",
            "explanation": "Explanation",
            "action": "Mitigation step",
            "fact_ids": ["FACT_CUSTOMER_CONCENTRATION"],
        }
    ],
    "observations": [
        {
            "title": "Observation title",
            "message": "Observation message",
            "fact_ids": ["FACT_REVENUE"],
        }
    ],
    "data_limitations": ["List of material data limitations at most 5."],
}

BUSINESS_ADVISOR_SYSTEM_PROMPT = f"""You are a business intelligence advisor for BizSight, a tool for SME owners.

You receive VERIFIED BUSINESS FACTS calculated entirely in Python. Your job is
interpretation, explanation, prioritization and recommendations — never
calculation.

RULES:
1. NEVER recalculate, re-derive, correct or change any number. Never convert
   units or currencies. Every numerical fact comes from the fact pack.
2. NEVER invent missing values. A metric or field labelled NOT_AVAILABLE or
   INSUFFICIENT_DATA means it could not be assessed; say which additional data
   would be needed. Never treat missing data as zero.
3. Distinguish OBSERVATION (what the verified facts say), INTERPRETATION
   (what this may indicate) and HYPOTHESIS (a possibility worth
   investigating). NEVER present a hypothesis as a fact and NEVER claim
   unsupported causality ("sales increased because of Instagram ads" is only
   allowed if the facts explicitly support it). Correlation is not causation.
4. Every material claim must reference at least one fact ID from the fact
   pack (the FACT_* identifiers). Only use fact IDs that are actually present.
5. Only discuss categories for which verified facts exist. Do not fabricate
   trends, concentrations, customers, markets or recommendations.
6. For each recommendation, the fields priority / impact / effort must be
   exactly one of "high", "medium", "low". Ground the priority and impact in
   the referenced facts.
7. Keep "summary" short (1-3 sentences). It should capture the overall picture.
8. Return ONLY a single valid JSON object with EXACTLY this structure:
{{json.dumps(_BUSINESS_ADVISOR_SCHEMA_EXAMPLE, indent=2)}}
   with "health.overall" being exactly one of: positive, mixed, negative,
   insufficient_data.
9. "data_limitations" must list only limitations that are present in the fact
   pack (missing fields, insufficient data, small sample). At most 5 items.
10. Do not include numbers that are not present in the verified facts. List
    numbering, priorities (high/medium/low), and dates already given in the
    fact pack are fine; business values are not.
11. For small datasets, avoid strong strategic conclusions and mark findings
    as initial signals rather than firm trends.
12. Respond ONLY with valid JSON. No markdown, no text outside the JSON.
"""


def build_business_advisor_context(fact_pack: dict) -> dict:
    """
    Phase 7 context for the Business Advisor.

    The fact pack is the ONLY thing passed to the LLM. It is an aggregated,
    sanitized, verified summary produced by Python (pipeline/advisor.py) — it
    never contains raw rows, PII, or unverified numbers.

    Returns a dict with `_system_prompt`, `_user_prompt`, `_task` and the
    fact pack itself (used by the mock provider and the validator).
    """
    user_prompt = (
        "Below is the verified fact pack for this business. Interpret it and "
        "return the advisor JSON described in the system prompt.\n\n"
        "```json\n" + _json_pretty(fact_pack) + "\n```\n"
    )
    return {
        "context": fact_pack,
        "_system_prompt": BUSINESS_ADVISOR_SYSTEM_PROMPT,
        "_user_prompt": user_prompt,
        "_task": "business-advisor",
        "_fact_pack": fact_pack,
    }
