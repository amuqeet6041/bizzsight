"""
capabilities.py  —  PHASE 3 of the new BizSight architecture: the Capability Engine.

The Capability Engine is deterministic Python logic. It decides exactly which
analyses, metrics, dimensions and chart categories BizSight can SAFELY provide
based on:

    * the profiler output (what data actually exists and how usable it is), and
    * the validated semantic mapping (what each column means).

THE CENTRAL RULE
    NEVER CALCULATE OR DISPLAY AN ANALYSIS WHEN ITS REQUIRED DATA
    DOES NOT EXIST. NEVER treat missing values as zero.

The engine NEVER uses the LLM to decide whether a metric is valid — that is
pure Python. The LLM's job (semantics) ended upstream; here every `available`
flag is the result of explicit, data-backed requirement checking.

Main entry point:
    build_capability_map(profile, validated_mapping) -> JSON-serializable dict
"""

from dataclasses import dataclass, field


# ===========================================================================
# 1. Usability thresholds (documented, deliberate)
# ===========================================================================
#
# A mapped field is NOT automatically usable. We use the profiler's per-column
# profile plus the validated role to decide. Thresholds:
#
#   MIN_ROLE_CONFIDENCE 0.50 — a role below this confidence is treated as not
#                              present (matches the mapper's own 0.5 bar).
#   NULL_MAX_MEASURE    0.50 — a measure column that is more than 50% null is
#                              not a safe basis for financial sums.
#   NULL_MAX_DIMENSION  0.80 — a dimension with up to 80% null can still be
#                              meaningfully segmented, so it is more lenient.
#   MIN_UNIQUE_DIMENSION 2   — a constant column (1 unique value) cannot be a
#                              useful dimension.
#
# Numeric measures must have inferred_type 'integer' or 'float'. A date role is
# only usable when the profiler's date analysis recognises the column (so a
# column merely *named* 'date' that does not parse is NOT usable).

MIN_ROLE_CONFIDENCE = 0.50
NULL_MAX_MEASURE = 0.50
NULL_MAX_DIMENSION = 0.80
MIN_UNIQUE_DIMENSION = 2

NUMERIC_INFERRED_TYPES = ("integer", "float")
DIMENSION_INFERRED_TYPES = ("categorical", "text", "integer", "boolean", "identifier")
IDENTIFIER_INFERRED_TYPES = ("identifier", "integer", "text", "categorical")

# Role vocabulary used in requirement clauses (matches the LLM role contract)
MEASURE_ROLES = {
    "revenue", "quantity", "price", "cost", "shipping",
    "marketing", "discount", "tax", "profit",
}
IDENTIFIER_ROLES = {"order_id", "invoice_id", "transaction_id", "customer_id", "product_id"}
DIMENSION_ROLES = {
    "customer", "product", "category", "city", "country", "region",
    "payment", "channel", "status",
}
ORDER_IDENTIFIER_ROLES = {"order_id", "invoice_id", "transaction_id"}

# Roles that give a usable customer-level identity (name OR stable id)
CUSTOMER_ROLES = {"customer_id", "customer"}
PRODUCT_ROLES = {"product_id", "product"}

# Real role -> user-facing field name (STANDARD_FIELDS names where they exist)
_REAL_NAME = {
    "date": "order_date",
    "revenue": "revenue",
    "quantity": "quantity",
    "price": "price",
    "cost": "cost_of_goods",
    "shipping": "shipping_cost",
    "marketing": "marketing_spend",
    "discount": "discount",
    "tax": "tax",
    "profit": "profit",
    "status": "status",
    "order_id": "order_id",
    "invoice_id": "invoice_id",
    "transaction_id": "transaction_id",
    "customer_id": "customer_id",
    "product_id": "product_id",
    "customer": "customer",
    "product": "product",
    "category": "category",
    "city": "city",
    "country": "country",
    "region": "region",
    "payment": "payment",
    "channel": "channel",
}


def display_name(role: str) -> str:
    """User-facing field name for a role (standard names where they exist)."""
    return _REAL_NAME.get(role, role)


# ===========================================================================
# 2. Capability registry
# ===========================================================================

# Financial model (per the Phase 3 spec canonical model):
#   Gross Profit = Revenue - COGS
#   Net Profit   = Gross Profit - Shipping - Marketing   (= Revenue - COGS - Shipping - Marketing)
# NOTE: the current metrics.py subtracts shipping inside its own gross profit;
# Phase 4 must reconcile the metric engine with this capability-aware model.
# The engine therefore NEVER marks Net Profit available unless ALL of Revenue,
# COGS, Shipping and Marketing exist, and never substitutes missing values
# with zero.

CATEGORY_LABELS = {
    "financial": "Financial Analysis",
    "customer": "Customer Insight",
    "product": "Product Insight",
    "geography": "Geographic Insight",
    "operations": "Operational Insight",
    "time": "Time-Series Analysis",
}


@dataclass
class Capability:
    name: str
    label: str
    category: str
    description: str
    requirements: list  # list of tuples; a tuple is an OR-clause of role names
    unavailable_reason: str  # template; {missing} is replaced with the missing list
    partial_eligible: bool = False
    partial_reason_fmt: str = "Only part of the required data is present ({missing})."


def _and(*roles: str):
    """AND clause where every role is required separately."""
    return [(r,) for r in roles]


def _or(*roles: str):
    """One OR-clause (at least one of these roles required)."""
    return [roles]


CAPABILITIES: dict[str, Capability] = {}


def _register(cap: Capability):
    CAPABILITIES[cap.name] = cap
    return cap


# -------------------------------- FINANCIAL --------------------------------
_register(Capability(
    "revenue_analysis", "Revenue Analysis", "financial",
    "Total revenue from non-cancelled transactions.",
    _and("revenue"),
    "No usable revenue data was detected, so Revenue Analysis cannot be generated.",
))
_register(Capability(
    "order_analysis", "Order Analysis", "financial",
    "Order count and order-level aggregates (needs an order/invoice/transaction identifier).",
    _or("order_id", "invoice_id", "transaction_id"),
    "No order, invoice or transaction identifier was detected, so Order Analysis cannot be generated.",
))
_register(Capability(
    "quantity_analysis", "Quantity Analysis", "financial",
    "Total units sold.",
    _and("quantity"),
    "No usable quantity data was detected, so Quantity Analysis cannot be generated.",
))
_register(Capability(
    "average_order_value", "Average Order Value", "financial",
    "Revenue divided by the number of orders.",
    _and("revenue") + _or("order_id", "invoice_id", "transaction_id"),
    "Average Order Value needs both revenue and an order identifier to be calculated safely.",
))
_register(Capability(
    "gross_profit", "Gross Profit Analysis", "financial",
    "Gross Profit = Revenue - Cost of Goods Sold.",
    _and("revenue", "cost"),
    "Cost of Goods Sold data is required to calculate Gross Profit; it was not detected.",
))
_register(Capability(
    "gross_profit_margin", "Gross Profit Margin", "financial",
    "Gross Profit as a percentage of Revenue.",
    _and("revenue", "cost"),
    "Gross Profit Margin needs both Revenue and Cost of Goods Sold.",
))
_register(Capability(
    "net_profit", "Net Profit Analysis", "financial",
    "Net Profit = Gross Profit - Shipping - Marketing. Never substitutes missing costs with zero.",
    _and("revenue", "cost", "shipping", "marketing"),
    "Net Profit cannot be calculated safely because required expense data is missing: {missing}.",
))
_register(Capability(
    "net_profit_margin", "Net Profit Margin", "financial",
    "Net Profit as a percentage of Revenue.",
    _and("revenue", "cost", "shipping", "marketing"),
    "Net Profit Margin cannot be calculated safely because required expense data is missing: {missing}.",
))
_register(Capability(
    "cost_analysis", "Cost Analysis", "financial",
    "Cost of Goods Sold totals.",
    _and("cost"),
    "No usable cost data was detected, so Cost Analysis cannot be generated.",
))
_register(Capability(
    "shipping_analysis", "Shipping Analysis", "financial",
    "Shipping / delivery cost totals.",
    _and("shipping"),
    "No usable shipping data was detected, so Shipping Analysis cannot be generated.",
))
_register(Capability(
    "marketing_analysis", "Marketing Analysis", "financial",
    "Marketing / advertising spend totals.",
    _and("marketing"),
    "No usable marketing data was detected. Marketing is never assumed to be zero.",
))
_register(Capability(
    "discount_analysis", "Discount Analysis", "financial",
    "Discount / coupon amount totals.",
    _and("discount"),
    "No usable discount data was detected, so Discount Analysis cannot be generated.",
))
_register(Capability(
    "tax_analysis", "Tax Analysis", "financial",
    "Tax (GST/VAT) totals.",
    _and("tax"),
    "No usable tax data was detected, so Tax Analysis cannot be generated.",
))
_register(Capability(
    "profit_analysis", "Profit Analysis", "financial",
    "Reported profit column totals.",
    _and("profit"),
    "No usable profit column was detected, so Profit Analysis cannot be generated.",
))

# -------------------------------- CUSTOMER ---------------------------------
_register(Capability(
    "customer_analysis", "Customer Analysis", "customer",
    "Per-customer aggregates (needs a customer-level field or identifier).",
    _or("customer_id", "customer"),
    "No usable customer field or customer identifier was detected.",
))
_register(Capability(
    "top_customers", "Top Customers", "customer",
    "Customers ranked by a measure (revenue, quantity or orders).",
    _or("customer_id", "customer") + _or("revenue", "quantity", "order_id", "invoice_id", "transaction_id"),
    "Top Customers needs a customer field plus a ranking measure.",
    partial_eligible=True,
    partial_reason_fmt=(
        "A customer field exists but no ranking measure (revenue, quantity or orders) "
        "was detected, so customers can be listed but not ranked ({missing})."
    ),
))
_register(Capability(
    "customer_revenue", "Customer Revenue", "customer",
    "Revenue attributed to each customer.",
    _or("customer_id", "customer") + _and("revenue"),
    "Customer Revenue needs revenue data, which was not detected.",
))
_register(Capability(
    "customer_orders", "Customer Orders", "customer",
    "Number of orders per customer.",
    _or("customer_id", "customer") + _or("order_id", "invoice_id", "transaction_id"),
    "Customer Orders needs an order identifier, which was not detected.",
))
_register(Capability(
    "repeat_customer_analysis", "Repeat Customer Analysis", "customer",
    "Customers who purchased more than once (requires a stable customer identifier and order keys).",
    _and("customer_id") + _or("order_id", "invoice_id", "transaction_id"),
    "Repeat Customer Analysis needs a stable customer identifier and order keys. "
    "A customer name column is not treated as a stable ID.",
))
_register(Capability(
    "new_vs_returning_customers", "New vs Returning Customers", "customer",
    "First-time vs returning customers over time (requires customer identifier + transaction date).",
    _and("customer_id", "date"),
    "New vs Returning analysis needs both a customer identifier and a transaction date.",
))

# -------------------------------- PRODUCT -----------------------------------
_register(Capability(
    "product_analysis", "Product Analysis", "product",
    "Per-product aggregates (needs a product-level field or identifier).",
    _or("product_id", "product"),
    "No usable product field or product identifier was detected.",
))
_register(Capability(
    "top_products", "Top Products", "product",
    "Products ranked by a measure (revenue, quantity or orders).",
    _or("product_id", "product") + _or("revenue", "quantity", "order_id", "invoice_id", "transaction_id"),
    "Top Products needs a product field plus a ranking measure.",
    partial_eligible=True,
    partial_reason_fmt=(
        "A product field exists but no ranking measure (revenue, quantity or orders) "
        "was detected, so products can be listed but not ranked ({missing})."
    ),
))
_register(Capability(
    "product_revenue", "Product Revenue", "product",
    "Revenue per product.",
    _or("product_id", "product") + _and("revenue"),
    "Product Revenue needs revenue data, which was not detected.",
))
_register(Capability(
    "product_quantity", "Product Quantity", "product",
    "Units sold per product.",
    _or("product_id", "product") + _and("quantity"),
    "Product Quantity needs quantity data, which was not detected.",
))
_register(Capability(
    "product_orders", "Product Orders", "product",
    "Number of orders per product.",
    _or("product_id", "product") + _or("order_id", "invoice_id", "transaction_id"),
    "Product Orders needs an order identifier, which was not detected.",
))
_register(Capability(
    "category_analysis", "Category Analysis", "product",
    "Breakdown by product category.",
    _and("category"),
    "No usable product category data was detected.",
))

# -------------------------------- GEOGRAPHY ---------------------------------
_register(Capability(
    "city_analysis", "City Analysis", "geography",
    "Breakdown by city (works without country/region, e.g. Revenue by City).",
    _and("city"),
    "No usable city data was detected, so City Analysis cannot be generated.",
))
_register(Capability(
    "country_analysis", "Country Analysis", "geography",
    "Breakdown by country.",
    _and("country"),
    "No usable country data was detected, so Country Analysis cannot be generated.",
))
_register(Capability(
    "region_analysis", "Region Analysis", "geography",
    "Breakdown by region / state / province.",
    _and("region"),
    "No usable region data was detected, so Region Analysis cannot be generated.",
))
_register(Capability(
    "revenue_by_city", "Revenue by City", "geography",
    "Revenue grouped by city.",
    _and("revenue", "city"),
    "Revenue by City needs both revenue and city data.",
))
_register(Capability(
    "revenue_by_country", "Revenue by Country", "geography",
    "Revenue grouped by country.",
    _and("revenue", "country"),
    "Revenue by Country needs both revenue and country data.",
))
_register(Capability(
    "revenue_by_region", "Revenue by Region", "geography",
    "Revenue grouped by region.",
    _and("revenue", "region"),
    "Revenue by Region needs both revenue and region data.",
))

# -------------------------------- OPERATIONS --------------------------------
_register(Capability(
    "order_status_analysis", "Order Status Analysis", "operations",
    "Breakdown by order / delivery status.",
    _and("status"),
    "No usable order status data was detected.",
))
_register(Capability(
    "payment_analysis", "Payment Method Analysis", "operations",
    "Breakdown by payment method.",
    _and("payment"),
    "No usable payment-method data was detected.",
))
_register(Capability(
    "sales_channel_analysis", "Sales Channel Analysis", "operations",
    "Breakdown by sales channel / source.",
    _and("channel"),
    "No usable sales-channel data was detected.",
))
_register(Capability(
    "revenue_by_status", "Revenue by Order Status", "operations",
    "Revenue grouped by order status.",
    _and("revenue", "status"),
    "Revenue by Order Status needs both revenue and status data.",
))
_register(Capability(
    "revenue_by_payment", "Revenue by Payment Method", "operations",
    "Revenue grouped by payment method.",
    _and("revenue", "payment"),
    "Revenue by Payment Method needs both revenue and payment data.",
))
_register(Capability(
    "revenue_by_channel", "Revenue by Sales Channel", "operations",
    "Revenue grouped by sales channel.",
    _and("revenue", "channel"),
    "Revenue by Sales Channel needs both revenue and channel data.",
))

# -------------------------------- TIME --------------------------------------
_TIME_UNCHANGED = (
    "No usable date column was detected, so {label} cannot be generated."
)
_register(Capability(
    "time_series_analysis", "Time-Series Analysis", "time",
    "Any trend over time (requires a usable date column).",
    _and("date"),
    _TIME_UNCHANGED,
))
_register(Capability(
    "daily_analysis", "Daily Analysis", "time",
    "Daily trends of a measure (requires date + a measure).",
    _and("date") + _or(*sorted(MEASURE_ROLES)),
    _TIME_UNCHANGED,
))
_register(Capability(
    "weekly_analysis", "Weekly Analysis", "time",
    "Weekly trends of a measure (requires date + a measure).",
    _and("date") + _or(*sorted(MEASURE_ROLES)),
    _TIME_UNCHANGED,
))
_register(Capability(
    "monthly_analysis", "Monthly Analysis", "time",
    "Monthly trends of a measure (requires date + a measure).",
    _and("date") + _or(*sorted(MEASURE_ROLES)),
    _TIME_UNCHANGED,
))
_register(Capability(
    "quarterly_analysis", "Quarterly Analysis", "time",
    "Quarterly trends of a measure (requires date + a measure).",
    _and("date") + _or(*sorted(MEASURE_ROLES)),
    _TIME_UNCHANGED,
))
_register(Capability(
    "yearly_analysis", "Yearly Analysis", "time",
    "Yearly trends of a measure (requires date + a measure).",
    _and("date") + _or(*sorted(MEASURE_ROLES)),
    _TIME_UNCHANGED,
))
_register(Capability(
    "revenue_trend", "Revenue Trend", "time",
    "Revenue over time.",
    _and("date", "revenue"),
    "Revenue Trend needs both a usable date and revenue data.",
))
_register(Capability(
    "orders_trend", "Orders Trend", "time",
    "Order count over time.",
    _and("date") + _or("order_id", "invoice_id", "transaction_id"),
    "Orders Trend needs a usable date and an order identifier.",
))

# Composite revenue breakdowns grouped by their dimension category
_register(Capability(
    "revenue_by_product", "Revenue by Product", "product",
    "Revenue grouped by product.",
    _and("revenue") + _or("product_id", "product"),
    "Revenue by Product needs both revenue and product data.",
))
_register(Capability(
    "revenue_by_category", "Revenue by Category", "product",
    "Revenue grouped by product category.",
    _and("revenue", "category"),
    "Revenue by Category needs both revenue and category data.",
))

# What "important" means for the summary (fields that unlock the headline analyses)
IMPORTANT_FIELDS = [
    "order_date", "revenue", "cost_of_goods", "shipping_cost",
    "marketing_spend", "order_id", "customer_id", "product_id", "city", "status",
]

# ---------------------------------------------------------------------------
# Recommended-analysis ordering (display labels), used only when AVAILABLE
# ---------------------------------------------------------------------------
RECOMMENDED_LABELS = [
    ("revenue_analysis", "Revenue Analysis"),
    ("revenue_by_city", "Revenue by City"),
    ("revenue_by_product", "Revenue by Product"),
    ("top_products", "Top Products"),
    ("monthly_analysis", "Monthly Revenue Trend"),
    ("top_customers", "Top Customers"),
    ("repeat_customer_analysis", "Repeat Customer Analysis"),
    ("new_vs_returning_customers", "New vs Returning Customers"),
    ("gross_profit", "Gross Profit Analysis"),
    ("net_profit", "Net Profit Analysis"),
    ("average_order_value", "Average Order Value"),
    ("customer_analysis", "Customer Analysis"),
    ("product_analysis", "Product Analysis"),
    ("order_status_analysis", "Order Status Analysis"),
    ("sales_channel_analysis", "Sales Channel Analysis"),
]


# ===========================================================================
# 3. Role usability (data exists AND is usable)
# ===========================================================================

def _column_profile(profile, column):
    for col in profile.get("columns", []):
        if col["name"] == column:
            return col
    return {}


def _role_usable(role: str, column: str, profile: dict) -> tuple[bool, str | None]:
    """Decide whether a mapped role is backed by usable data. Returns (ok, reason)."""
    col = _column_profile(profile, column)
    inferred = col.get("inferred_type", "text")
    null_pct = col.get("null_percentage", 1.0)
    unique = col.get("unique_count", 0)

    if role == "date":
        candidates = {
            c["column"] for c in profile.get("date_analysis", {}).get("date_candidates", [])
        }
        recognised = (column in candidates) or (inferred == "datetime")
        if not recognised:
            return False, (
                f"Column '{column}' was mapped as date but no usable dates were "
                f"detected in its values."
            )
        if null_pct > NULL_MAX_MEASURE:
            return False, f"Column '{column}' is mostly empty ({null_pct*100:.0f}% null)."
        return True, None

    if role in MEASURE_ROLES:
        if inferred not in NUMERIC_INFERRED_TYPES:
            return False, (
                f"Column '{column}' has inferred type '{inferred}' and is not "
                f"usable as numeric {role} data."
            )
        if null_pct > NULL_MAX_MEASURE:
            return False, f"Column '{column}' is mostly empty ({null_pct*100:.0f}% null)."
        return True, None

    if role in IDENTIFIER_ROLES:
        if inferred not in IDENTIFIER_INFERRED_TYPES:
            return False, (
                f"Column '{column}' has inferred type '{inferred}' and was not "
                f"confirmed as an identifier."
            )
        if null_pct > NULL_MAX_DIMENSION:
            return False, f"Column '{column}' is mostly empty ({null_pct*100:.0f}% null)."
        if unique < 2:
            return False, f"Column '{column}' has fewer than 2 unique values."
        return True, None

    # dimension roles (customer, product, category, city, country, region,
    # payment, channel, status)
    if inferred not in DIMENSION_INFERRED_TYPES:
        return False, (
            f"Column '{column}' has inferred type '{inferred}' and is not usable "
            f"as a {role} dimension."
        )
    if null_pct > NULL_MAX_DIMENSION:
        return False, f"Column '{column}' is mostly empty ({null_pct*100:.0f}% null)."
    if unique < MIN_UNIQUE_DIMENSION:
        return False, f"Column '{column}' has only {unique} unique value(s); it is not a useful dimension."
    return True, None


def _mapped_roles(validated_mapping: dict, profile: dict, min_confidence: float):
    """Collect validated, role-assigned columns with their usability verdicts."""
    result = {}  # role -> dict(column, confidence, usable, reason, inferred_type, null_percentage)
    for entry in validated_mapping.get("mappings", []):
        role = entry.get("role")
        if not role or role not in _REAL_NAME:
            continue  # role None or unknown — cannot back a capability
        column = entry.get("column")
        confidence = float(entry.get("confidence", 0.0))
        usable = confidence >= min_confidence
        reason = None
        if not usable:
            reason = f"Mapping confidence ({confidence}) is below {min_confidence}."
        else:
            usable, reason = _role_usable(role, column, profile)
        col = _column_profile(profile, column)
        result[role] = {
            "column": column,
            "confidence": round(confidence, 3),
            "usable": bool(usable),
            "reason": reason,
            "inferred_type": col.get("inferred_type", "text"),
            "null_percentage": col.get("null_percentage", None),
        }
    return result


# ===========================================================================
# 4. Capability evaluation
# ===========================================================================

def _evaluate_capability(cap: Capability, mapped: dict) -> dict:
    """Evaluate one capability against the mapped (role -> usability) table."""
    supporting = []
    missing = []

    for clause in cap.requirements:
        satisfied_roles = [r for r in clause if mapped.get(r, {}).get("usable")]
        if satisfied_roles:
            supporting.extend(display_name(r) for r in satisfied_roles)
        else:
            missing.append(" / ".join(display_name(r) for r in clause))

    if not missing:
        status = "AVAILABLE"
        reason = None
    elif cap.partial_eligible and supporting:
        status = "PARTIAL"
        missing_txt = ", ".join(missing)
        reason = cap.partial_reason_fmt.format(missing=missing_txt)
    else:
        status = "NOT_AVAILABLE"
        missing_txt = ", ".join(missing)
        reason = cap.unavailable_reason.format(missing=missing_txt, label=cap.label)

    return {
        "status": status,
        "available": status == "AVAILABLE",
        "category": cap.category,
        "category_label": CATEGORY_LABELS.get(cap.category, cap.category),
        "label": cap.label,
        "description": cap.description,
        "supporting_fields": supporting,
        "missing_requirements": missing,
        "reason": reason,
    }


def _detected_dimensions(mapped: dict, profile: dict) -> dict:
    """Available dimensions plus the geography hierarchy (country->region->city)."""
    dims = []
    for role in DIMENSION_ROLES:
        info = mapped.get(role)
        if info and info["usable"]:
            dims.append({
                "role": role,
                "column": info["column"],
                "unique_count": _column_profile(profile, info["column"]).get("unique_count", 0),
            })
    geography = [r for r in ("country", "region", "city") if mapped.get(r, {}).get("usable")]
    return {
        "available": dims,
        "geography_hierarchy": geography,
        "customer_level": next(
            (r for r in ("customer_id", "customer") if mapped.get(r, {}).get("usable")), None
        ),
        "product_level": next(
            (r for r in ("product_id", "product") if mapped.get(r, {}).get("usable")), None
        ),
    }


def _missing_important_fields(mapped: dict) -> list[str]:
    important_roles = set(IMPORTANT_FIELDS)
    known_real_names = {
        display_name(r): r for r in _REAL_NAME
    }
    missing = []
    for real in IMPORTANT_FIELDS:
        role = known_real_names.get(real)
        if role is None:
            continue
        info = mapped.get(role)
        if not info or not info["usable"]:
            missing.append(real)
    return missing


def _recommended_analysis(cap_evaluated: dict, limit: int = 5) -> list[str]:
    out = []
    for cap_name, label in RECOMMENDED_LABELS:
        if cap_evaluated.get(cap_name, {}).get("available"):
            out.append(label)
        if len(out) >= limit:
            break
    return out


# ===========================================================================
# 5. Main entry point
# ===========================================================================

def build_capability_map(profile: dict, validated_mapping: dict) -> dict:
    """
    Determine exactly which analyses BizSight can safely provide.

    Args:
        profile:            full profiler output (profile_dataset result)
        validated_mapping:  validated semantic mapping (validate_and_map result)

    Returns:
        A JSON-serializable dict:
            {
                "mapped_roles": {...},
                "capabilities": {...},
                "dimensions": {...},
                "missing_important_fields": [...],
                "recommended_analysis": [...],
                "date_range": {...} | null,
                "summary": {...},
            }
    """
    mapped = _mapped_roles(validated_mapping, profile, MIN_ROLE_CONFIDENCE)

    capabilities = {
        name: _evaluate_capability(cap, mapped)
        for name, cap in CAPABILITIES.items()
    }

    statuses = {c["status"] for c in capabilities.values()}
    available_count = sum(1 for c in capabilities.values() if c["available"])
    partial_count = sum(1 for c in capabilities.values() if c["status"] == "PARTIAL")
    unavailable_count = sum(1 for c in capabilities.values() if c["status"] == "NOT_AVAILABLE")
    available_categories = sorted({
        c["category_label"] for c in capabilities.values() if c["available"]
    })

    date_analysis = profile.get("date_analysis", {})
    date_range = None
    if date_analysis.get("has_date") and date_analysis.get("earliest_date"):
        date_range = {
            "min": date_analysis["earliest_date"],
            "max": date_analysis["latest_date"],
        }

    dataset = profile.get("dataset", {})
    return {
        "profile": {
            "file_type": profile.get("file_type"),
            "primary_sheet": dataset.get("primary_sheet_candidate"),
            "row_count": dataset.get("row_count", 0),
            "column_count": dataset.get("column_count", 0),
            "date_range": date_range,
        },
        "mapped_roles": mapped,
        "capabilities": capabilities,
        "dimensions": _detected_dimensions(mapped, profile),
        "missing_important_fields": _missing_important_fields(mapped),
        "recommended_analysis": _recommended_analysis(capabilities),
        "summary": {
            "available_count": available_count,
            "unavailable_count": unavailable_count,
            "partial_count": partial_count,
            "total_capabilities": len(CAPABILITIES),
            "statuses_used": sorted(statuses),
            "available_categories": available_categories,
        },
    }