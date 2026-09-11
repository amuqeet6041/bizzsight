"""
validation.py  —  Phase 2 Python-side validation for LLM semantic mapping responses.

Validates the LLM output against profiler data and the supported role set.
Produces a validated mapping with warnings, errors, and rejected entries.
Also bridges LLM role names to STANDARD_FIELDS names used by cleaning.py.
"""

from pipeline.prompts import VALID_ROLES
from pipeline.mapping import STANDARD_FIELDS


# ---------------------------------------------------------------------------
# Role → STANDARD_FIELDS bridge
# ---------------------------------------------------------------------------

_ROLE_TO_STANDARD: dict[str, str] = {
    "date":        "order_date",
    "revenue":     "revenue",
    "quantity":    "quantity",
    "cost":        "cost_of_goods",
    "shipping":    "shipping_cost",
    "marketing":   "marketing_spend",
    "status":      "status",
    "order_id":    "order_id",
    "customer":    "customer_id",
    "customer_id": "customer_id",
    "product":     "product_id",
    "product_id":  "product_id",
}

# LLM roles that are NOT in STANDARD_FIELDS but are valid domain roles
_DIMENSION_ONLY_ROLES = {
    "price", "discount", "tax", "profit",
    "customer", "product", "category",
    "city", "country", "region",
    "invoice_id", "transaction_id",
    "payment", "channel",
}

# Roles that represent numeric measures
_NUMERIC_MEASURE_ROLES = {
    "revenue", "quantity", "price", "cost", "shipping",
    "marketing", "discount", "tax", "profit",
}

# Roles that represent identifiers
_IDENTIFIER_ROLES = {"order_id", "customer_id", "product_id", "invoice_id", "transaction_id"}


def role_to_standard(role: str | None) -> str | None:
    """Map an LLM role name to the STANDARD_FIELDS name expected by cleaning.py.
    Returns None for dimension-only roles (valid but not consumed by cleaning)."""
    if role is None:
        return None
    return _ROLE_TO_STANDARD.get(role)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class MappingValidationError(Exception):
    """Raised when the LLM response is fundamentally broken (cannot recover)."""


def validate_and_map(
    llm_response: dict,
    profile: dict,
    *,
    is_mock: bool = False,
) -> dict:
    """
    Validate raw LLM output and produce a structured response.

    Input:
        llm_response : raw dict from LLM provider (must contain "mappings" list)
        profile      : full profiler output (for column existence checks, inferred types)

    Returns:
        {
            "mappings":       [...validated mappings...],
            "warnings":       [...],
            "errors":         [...],
            "rejected":       [...],
            "profiler_summary": {...},
            "mock":           bool,
            "model":          str,
        }

    Raises MappingValidationError if the LLM response is fundamentally broken.
    """
    if not isinstance(llm_response, dict):
        raise MappingValidationError("LLM response must be a JSON object (dict).")

    raw_mappings = llm_response.get("mappings")
    if not isinstance(raw_mappings, list):
        raise MappingValidationError(
            "LLM response must contain a 'mappings' array."
        )

    model_name = llm_response.get("model", "unknown")

    # build profiler lookup structures
    profiler_columns = {col["name"]: col for col in profile.get("columns", [])}
    all_column_names = set(profiler_columns.keys())

    warnings: list[str] = []
    errors: list[str] = []
    rejected: list[dict] = []
    validated: list[dict] = []

    seen_columns: set[str] = set()
    seen_standard_fields: set[str] = set()

    for idx, entry in enumerate(raw_mappings):
        # --- structural checks ---
        if not isinstance(entry, dict):
            errors.append(f"Entry at index {idx} is not a JSON object.")
            rejected.append({"entry": entry, "reason": "not a JSON object"})
            continue

        col = entry.get("column")
        role = entry.get("role")
        confidence = entry.get("confidence")
        reason = entry.get("reason", "")

        # --- column existence ---
        if not col or not isinstance(col, str):
            errors.append(f"Entry at index {idx}: missing or invalid 'column'.")
            rejected.append({"entry": entry, "reason": "missing or invalid column"})
            continue
        if col not in all_column_names:
            errors.append(f"Column '{col}' does not exist in the dataset.")
            rejected.append({"entry": entry, "reason": f"column '{col}' not in dataset"})
            continue
        if col in seen_columns:
            warnings.append(f"Column '{col}' appears more than once; keeping first occurrence.")
            rejected.append({"entry": entry, "reason": f"duplicate column '{col}'"})
            continue
        seen_columns.add(col)

        col_profile = profiler_columns[col]
        inferred_type = col_profile.get("inferred_type", "text")

        # --- null/unmapped column (valid) ---
        if role is None:
            validated.append({
                "column": col,
                "role": None,
                "standard_field": None,
                "confidence": 0.0,
                "reason": reason or "No confident role assigned.",
                "warnings": [],
            })
            continue

        # --- role validity ---
        if not isinstance(role, str) or role not in VALID_ROLES:
            errors.append(f"Column '{col}': unsupported role '{role}'.")
            rejected.append({"entry": entry, "reason": f"unsupported role '{role}'"})
            continue

        # --- confidence validity ---
        if not isinstance(confidence, (int, float)):
            errors.append(f"Column '{col}': confidence must be a number.")
            rejected.append({"entry": entry, "reason": "confidence not a number"})
            continue
        confidence = float(confidence)
        if confidence < 0.0 or confidence > 1.0:
            errors.append(f"Column '{col}': confidence {confidence} out of range [0.0, 1.0].")
            rejected.append({"entry": entry, "reason": f"confidence {confidence} out of range"})
            continue

        col_warnings: list[str] = []

        # --- identifier ↔ measure conflict ---
        if role in _IDENTIFIER_ROLES and role not in _ROLE_TO_STANDARD:
            # identifier role that isn't in STANDARD_FIELDS — always valid if column exists
            pass
        elif role in _IDENTIFIER_ROLES and inferred_type in ("float", "datetime", "boolean"):
            col_warnings.append(
                f"Column '{col}' (inferred_type={inferred_type}) is mapped as identifier "
                f"'{role}'; this may be incorrect."
            )

        if role in _NUMERIC_MEASURE_ROLES and inferred_type in ("datetime", "boolean"):
            col_warnings.append(
                f"Column '{col}' (inferred_type={inferred_type}) is mapped as numeric "
                f"measure '{role}'; this may be incorrect."
            )

        if role in _NUMERIC_MEASURE_ROLES and inferred_type == "identifier":
            col_warnings.append(
                f"Column '{col}' was identified by the profiler as an identifier; "
                f"mapping it as numeric measure '{role}' is almost certainly wrong."
            )

        # --- impossible mappings ---
        if role == "date" and inferred_type in ("float", "integer") and col_profile.get("unique_count", 0) < 10:
            col_warnings.append(
                f"Column '{col}' is mapped as 'date' but has inferred_type '{inferred_type}' "
                f"with only {col_profile.get('unique_count', 0)} unique values."
            )

        # --- STANDARD_FIELDS collision ---
        std_field = role_to_standard(role)
        if std_field and std_field in seen_standard_fields:
            col_warnings.append(
                f"Standard field '{std_field}' (role '{role}') already assigned to another column; "
                f"keeping first assignment."
            )
            rejected.append({"entry": entry, "reason": f"duplicate standard field '{std_field}'"})
            warnings.extend(col_warnings)
            continue

        if std_field:
            seen_standard_fields.add(std_field)

        validated.append({
            "column": col,
            "role": role,
            "standard_field": std_field,
            "confidence": confidence,
            "reason": reason,
            "warnings": col_warnings,
        })
        warnings.extend(col_warnings)

    # --- profiler summary ---
    profiler_summary = {
        "row_count": profile.get("dataset", {}).get("row_count", 0),
        "column_count": profile.get("dataset", {}).get("column_count", 0),
        "detected_roles": list(profile.get("detected_fields", {}).keys()),
        "missing_common_fields": profile.get("missing_common_fields", []),
    }

    if is_mock:
        warnings.append(
            "This response was generated by the mock provider (profiler-based, not LLM). "
            "Configure a real LLM provider to get true semantic mapping."
        )

    return {
        "mappings": validated,
        "warnings": warnings,
        "errors": errors,
        "rejected": rejected,
        "profiler_summary": profiler_summary,
        "mock": is_mock,
        "model": model_name,
    }
