"""
advisor.py  —  PHASE 7: Business Advisor / AI Analysis Engine.

High-level flow for each /process call, AFTER metrics, insights and chart
specs have been computed in Python:

    1. build_advisor_fact_pack(...)      assemble a VERIFIED, sanitized,
                                         aggregated fact pack (no raw rows,
                                         no PII, no unverified numbers).
    2. build_business_advisor_context()  wrap it in the business-advisor-v1
                                         system/user prompt (prompts.py).
    3. provider.complete(...)            the LLM produces interpretation-only
                                         JSON (never calculations).
    4. validate_advisor_response()       schema / enum / length / fact-ID
                                         whitelist check.
    5. _hallucination_errors()           numeric-token check against the
                                         verified numbers already in the
                                         fact pack.

On ANY failure (LLM error, malformed JSON, schema violation, or a material
number that is not backed by a verified fact) the advisor returns:

    {"status": "UNAVAILABLE", "summary": None,
     "reason": "Business advisor is currently unavailable."}

so /process ALWAYS succeeds. Nothing sensitive ever leaks into that reason.

The canonical financial model, per Phase 4:

    Revenue - COGS = Gross Profit
    Gross Profit - Shipping - Marketing = Net Profit

Python is the only calculator in the whole system. The LLM never decides
availability, never computes a number, and never turns missing data into 0.
"""

import json
import math
import re

import pandas as pd

from pipeline.prompts import (
    BUSINESS_ADVISOR_PROMPT_VERSION,
    build_business_advisor_context,
)


# ===========================================================================
# 1. Fact IDs (stable identifiers the LLM must cite)
# ===========================================================================

FACT_REVENUE = "FACT_REVENUE"
FACT_COGS = "FACT_COGS"
FACT_SHIPPING = "FACT_SHIPPING"
FACT_MARKETING = "FACT_MARKETING"
FACT_GROSS_PROFIT = "FACT_GROSS_PROFIT"
FACT_GROSS_MARGIN = "FACT_GROSS_MARGIN"
FACT_NET_PROFIT = "FACT_NET_PROFIT"
FACT_NET_MARGIN = "FACT_NET_MARGIN"
FACT_ORDERS = "FACT_ORDERS"
FACT_AOV = "FACT_AOV"
FACT_QUANTITY = "FACT_QUANTITY"
FACT_CAC = "FACT_CAC"
FACT_REPEAT_RATE = "FACT_REPEAT_RATE"
FACT_RETURN_CANCEL_RATE = "FACT_RETURN_CANCEL_RATE"
FACT_CUSTOMER_COUNT = "FACT_CUSTOMER_COUNT"
FACT_TOP_PRODUCT = "FACT_TOP_PRODUCT"
FACT_TOP_CUSTOMER = "FACT_TOP_CUSTOMER"
FACT_TOP_CITY = "FACT_TOP_CITY"
FACT_CUSTOMER_CONCENTRATION = "FACT_CUSTOMER_CONCENTRATION"
FACT_REVENUE_GROWTH = "FACT_REVENUE_GROWTH"
FACT_ORDERS_GROWTH = "FACT_ORDERS_GROWTH"
FACT_REVENUE_TREND = "FACT_REVENUE_TREND"
FACT_ORDERS_TREND = "FACT_ORDERS_TREND"
FACT_ROW_COUNT = "FACT_ROW_COUNT"
FACT_DATE_RANGE = "FACT_DATE_RANGE"
FACT_PERIOD_COUNT = "FACT_PERIOD_COUNT"

KNOWN_FACT_IDS = frozenset({
    FACT_REVENUE, FACT_COGS, FACT_SHIPPING, FACT_MARKETING,
    FACT_GROSS_PROFIT, FACT_GROSS_MARGIN, FACT_NET_PROFIT, FACT_NET_MARGIN,
    FACT_ORDERS, FACT_AOV, FACT_QUANTITY, FACT_CAC, FACT_REPEAT_RATE,
    FACT_RETURN_CANCEL_RATE, FACT_CUSTOMER_COUNT, FACT_TOP_PRODUCT,
    FACT_TOP_CUSTOMER, FACT_TOP_CITY, FACT_CUSTOMER_CONCENTRATION,
    FACT_REVENUE_GROWTH, FACT_ORDERS_GROWTH, FACT_REVENUE_TREND,
    FACT_ORDERS_TREND, FACT_ROW_COUNT, FACT_DATE_RANGE, FACT_PERIOD_COUNT,
})

# Enums the validator enforces.
_OVERALL_CHOICES = ("positive", "mixed", "negative", "insufficient_data")
_TRI_CHOICES = ("high", "medium", "low")

# Limits shared by the validator and the mock.
_MAX_PRIORITIES = 6
_MAX_OPPORTUNITIES = 6
_MAX_RISKS = 6
_MAX_OBSERVATIONS = 10
_MAX_LIMITATIONS = 5
_MAX_STRING = 2000
_MAX_ITEM_STRING = 500
_TOP_ENTITY_LIMIT = 5
_SMALL_DATASET_ORDERS = 10

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_INT_TOKEN_RE = re.compile(r"\d+")
# Numbers inside identifiers (e.g. the "-02" in "C-02" or the "-01" in a
# "2024-01" period) are not business values and must not be scanned.
_NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])-?\d+(?:\.\d+)?")


# ===========================================================================
# 2. Entity-label sanitizer (never expose emails / phone numbers / addresses)
# ===========================================================================

def _safe_entity_label(label):
    """Redacts email/phone-looking entity labels; aggregated labels pass."""
    if not isinstance(label, str):
        return str(label)
    if _EMAIL_RE.search(label) or _PHONE_RE.search(label):
        return "[redacted identifier]"
    return label.strip()


# ===========================================================================
# 3. Verified helpers (read-only aggregation over already-verified artifacts)
# ===========================================================================

def _metric_available(metric_status, key):
    entry = (metric_status or {}).get(key, {})
    return entry.get("status") == "AVAILABLE" and entry.get("value") is not None


def _metric_value(metric_values, key):
    if not metric_values:
        return None
    return metric_values.get(key)


def _spec_by_id(chart_specs, cid):
    for spec in chart_specs or []:
        if spec.get("id") == cid:
            return spec
    return None


def _ranking_rows(chart_specs, cid, label_key, value_key, limit=None):
    """(label, value) pairs from an AVAILABLE ranking chart, top-limit applied."""
    spec = _spec_by_id(chart_specs, cid)
    if not spec:
        return []
    rows = []
    for r in spec.get("data", []):
        label = _safe_entity_label(r.get(label_key))
        value = r.get(value_key)
        if label is not None and value is not None:
            rows.append((label, value))
    if limit is not None:
        rows = rows[:limit]
    return rows


def _trend_series(chart_specs, cid, value_key):
    """Ordered list of (period, value) pairs from an AVAILABLE trend chart."""
    spec = _spec_by_id(chart_specs, cid)
    if not spec:
        return []
    out = []
    for r in spec.get("data", []):
        period = r.get("period")
        value = r.get(value_key)
        if period is not None and value is not None:
            out.append((str(period), float(value)))
    return out


def _growth(last, prev):
    if last is None or prev in (None, 0):
        return None
    return last / prev - 1.0


def _trend_direction(series, tolerance=0.02):
    """increasing / decreasing / stable / None based on first vs last value."""
    if len(series) < 2:
        return None
    first = series[0][1]
    last = series[-1][1]
    if first in (None, 0):
        return None
    ratio = last / first
    if ratio > 1.0 + tolerance:
        return "increasing"
    if ratio < 1.0 - tolerance:
        return "decreasing"
    return "stable"


# ===========================================================================
# 4. Fact pack construction
# ===========================================================================

def _build_metrics_facts(metric_values, metric_status, facts):
    """Adds the verified metrics as facts (AVAILABLE values only)."""
    def add(fid, key, label):
        if not _metric_available(metric_status, key):
            return
        value = _metric_value(metric_values, key)
        facts.append({
            "id": fid,
            "label": label,
            "category": (metric_status or {}).get(key, {}).get("category"),
            "value": value,
            "status": "AVAILABLE",
            "unit": "currency" if key in (
                "revenue", "cogs", "shipping", "marketing", "gross_profit",
                "net_profit", "average_order_value", "customer_acquisition_cost",
            ) else ("fraction" if key.endswith("_margin") or key in (
                "repeat_purchase_rate", "return_cancel_rate",
            ) else None),
        })

    add(FACT_REVENUE, "revenue", "Total Revenue (delivered orders)")
    add(FACT_COGS, "cogs", "Total COGS")
    add(FACT_SHIPPING, "shipping", "Total Shipping Expense")
    add(FACT_MARKETING, "marketing", "Total Marketing Spend")
    add(FACT_GROSS_PROFIT, "gross_profit", "Gross Profit")
    add(FACT_GROSS_MARGIN, "gross_profit_margin", "Gross Profit Margin")
    add(FACT_NET_PROFIT, "net_profit", "Net Profit")
    add(FACT_NET_MARGIN, "net_profit_margin", "Net Profit Margin")
    add(FACT_ORDERS, "orders", "Number of Delivered Orders")
    add(FACT_AOV, "average_order_value", "Average Order Value (AOV)")
    add(FACT_QUANTITY, "quantity", "Total Quantity Sold")
    add(FACT_CAC, "customer_acquisition_cost", "Customer Acquisition Cost (CAC)")
    add(FACT_REPEAT_RATE, "repeat_purchase_rate", "Repeat Purchase Rate")
    add(FACT_RETURN_CANCEL_RATE, "return_cancel_rate", "Return/Cancel Rate")


def _build_top_entity_facts(df, mapping, chart_specs, facts):
    """Top product / customer / city from the AVAILABLE ranking charts."""
    products = _ranking_rows(chart_specs, "product_revenue", "product", "revenue",
                             limit=_TOP_ENTITY_LIMIT)
    if products:
        facts.append({
            "id": FACT_TOP_PRODUCT, "label": "Top Product by Revenue",
            "value": products[0][0], "status": "AVAILABLE",
            "detail": [
                {"name": name, "revenue": value} for name, value in products
            ],
        })

    customers = _ranking_rows(chart_specs, "customer_revenue", "customer", "revenue",
                              limit=_TOP_ENTITY_LIMIT)
    if customers:
        revenue = None
        if _metric_available_from_facts(facts, FACT_REVENUE):
            revenue = _find_fact_value(facts, FACT_REVENUE)
        concentration = None
        if revenue not in (None, 0) and customers:
            concentration = round(float(customers[0][1]) / float(revenue), 4)
        facts.append({
            "id": FACT_TOP_CUSTOMER, "label": "Top Customer by Revenue",
            "value": customers[0][0], "status": "AVAILABLE",
            "detail": [
                {"name": name, "revenue": value} for name, value in customers
            ],
        })
        if concentration is not None:
            facts.append({
                "id": FACT_CUSTOMER_CONCENTRATION,
                "label": "Share of Revenue from Top Customer",
                "value": concentration, "status": "AVAILABLE",
                "unit": "fraction",
            })

    cities = _ranking_rows(chart_specs, "city_revenue", "city", "revenue",
                           limit=_TOP_ENTITY_LIMIT)
    if cities:
        facts.append({
            "id": FACT_TOP_CITY, "label": "Top City by Revenue",
            "value": cities[0][0], "status": "AVAILABLE",
            "detail": [
                {"name": name, "revenue": value} for name, value in cities
            ],
        })


def _build_trend_facts(chart_specs, facts):
    """Growth + direction facts derived from the verified trend charts."""
    revenue_series = _trend_series(chart_specs, "revenue_trend", "revenue")
    if revenue_series:
        last, prev = revenue_series[-1][1], (revenue_series[-2][1] if len(revenue_series) >= 2 else None)
        growth = _growth(last, prev)
        direction = _trend_direction(revenue_series)
        facts.append({
            "id": FACT_REVENUE_TREND, "label": "Revenue Trend Direction",
            "value": direction if direction else "insufficient", "status": "AVAILABLE",
            "detail": [{"period": p, "revenue": v} for p, v in revenue_series],
        })
        if growth is not None:
            facts.append({
                "id": FACT_REVENUE_GROWTH,
                "label": "Revenue Growth (latest vs previous period)",
                "value": round(growth, 4), "status": "AVAILABLE",
                "unit": "fraction",
            })

    orders_series = _trend_series(chart_specs, "orders_trend", "orders")
    if orders_series:
        last, prev = orders_series[-1][1], (orders_series[-2][1] if len(orders_series) >= 2 else None)
        growth = _growth(last, prev)
        direction = _trend_direction(orders_series)
        facts.append({
            "id": FACT_ORDERS_TREND, "label": "Orders Trend Direction",
            "value": direction if direction else "insufficient", "status": "AVAILABLE",
            "detail": [{"period": p, "orders": int(v)} for p, v in orders_series],
        })
        if growth is not None:
            facts.append({
                "id": FACT_ORDERS_GROWTH,
                "label": "Orders Growth (latest vs previous period)",
                "value": round(growth, 4), "status": "AVAILABLE",
                "unit": "fraction",
            })


def _metric_available_from_facts(facts, fid):
    return _find_fact_value(facts, fid) is not None


def _find_fact_value(facts, fid):
    for f in facts:
        if f.get("id") == fid:
            return f.get("value")
    return None


def _build_limitations(df, metric_status, metric_values):
    """Deterministic data-limitation list derived from availability only."""
    limitations = []
    ms = metric_status or {}

    # The small-dataset caution and missing date are foundational: surface them
    # before the per-field limitations so they survive the max-5 cap.
    orders = _metric_value(metric_values, "orders")
    if orders is not None and orders < _SMALL_DATASET_ORDERS:
        limitations.append(
            f"The dataset contains only {int(orders)} delivered orders; findings should be "
            "treated as initial signals rather than firm trends."
        )

    if df is not None and "order_date" not in df.columns:
        limitations.append("Order date data was not detected; trend analysis is unavailable.")

    def field_unusable(metric_key, text):
        entry = ms.get(metric_key) or {}
        if entry.get("status") != "AVAILABLE":
            limitations.append(text)

    field_unusable("shipping", "Shipping expense data was not detected.")
    field_unusable("marketing", "Marketing expense data was not detected.")
    field_unusable("cogs", "COGS data was not detected.")
    field_unusable("customer_acquisition_cost",
                   "Customer data was not detected; customer-level analysis is unavailable.")
    field_unusable("net_profit", "Net profit could not be assessed "
                                 "(shipping and/or marketing expense data was not detected).")

    return limitations[: _MAX_LIMITATIONS]


def build_advisor_fact_pack(
    df,
    mapping=None,
    capability_map=None,
    metric_values=None,
    metric_status=None,
    structured_insights=None,
    chart_specs=None,
    profiler=None,
):
    """
    Builds the sanitized, verified fact pack that is the ONLY thing the LLM
    sees. Never includes raw rows, PII, or unverified numbers.
    """
    facts = []
    _build_metrics_facts(metric_values, metric_status, facts)
    _build_top_entity_facts(df, mapping, chart_specs, facts)
    _build_trend_facts(chart_specs, facts)

    # ---- business summary (aggregates only) --------------------------------
    row_count = int(len(df)) if df is not None else 0
    facts.append({
        "id": FACT_ROW_COUNT, "label": "Rows in Dataset",
        "value": row_count, "status": "AVAILABLE", "unit": "count",
    })

    date_range = None
    if df is not None and "order_date" in df.columns:
        dates = pd.to_datetime(df["order_date"], errors="coerce").dropna()
        if len(dates):
            date_range = {
                "start": dates.min().strftime("%Y-%m-%d"),
                "end": dates.max().strftime("%Y-%m-%d"),
            }
            facts.append({
                "id": FACT_DATE_RANGE, "label": "Order Date Range",
                "value": f"{date_range['start']} to {date_range['end']}",
                "status": "AVAILABLE",
            })

    periods = set()
    revenue_series = _trend_series(chart_specs, "revenue_trend", "revenue")
    for period, _ in revenue_series:
        periods.add(period)
    if periods:
        facts.append({
            "id": FACT_PERIOD_COUNT, "label": "Number of Trend Periods",
            "value": len(periods), "status": "AVAILABLE", "unit": "count",
        })

    # ---- reader-friendly sections (duplicate the facts) --------------------
    metrics_section = [
        {
            "key": f["id"],
            "label": f["label"],
            "value": f["value"],
            "unit": f.get("unit"),
            "percent": round(f["value"] * 100, 2) if f.get("unit") == "fraction" else None,
        }
        for f in facts
        if f["id"] in (
            FACT_REVENUE, FACT_COGS, FACT_SHIPPING, FACT_MARKETING,
            FACT_GROSS_PROFIT, FACT_GROSS_MARGIN, FACT_NET_PROFIT,
            FACT_NET_MARGIN, FACT_ORDERS, FACT_AOV, FACT_QUANTITY,
            FACT_CAC, FACT_REPEAT_RATE, FACT_RETURN_CANCEL_RATE,
        )
    ]

    entities = {}
    for fid in (FACT_TOP_PRODUCT, FACT_TOP_CUSTOMER, FACT_TOP_CITY):
        f = next((x for x in facts if x["id"] == fid), None)
        if f:
            entities[fid] = {
                "top": f["value"],
                "detail": f.get("detail", []),
            }

    trends = {}
    for fid in (FACT_REVENUE_TREND, FACT_ORDERS_TREND):
        f = next((x for x in facts if x["id"] == fid), None)
        if f:
            trends[fid] = {"direction": f["value"], "points": f.get("detail", [])}
    for fid, key in ((FACT_REVENUE_GROWTH, "revenue_growth"),
                     (FACT_ORDERS_GROWTH, "orders_growth")):
        f = next((x for x in facts if x["id"] == fid), None)
        if f:
            trends[fid] = {"value": f["value"], "percent": round(f["value"] * 100, 2)}

    # ---- insight snapshot (templated Python insights, sanitized) -----------
    insight_snapshot = []
    for ins in (structured_insights or []):
        if not isinstance(ins, dict):
            continue
        if ins.get("type") == "missing_data":
            continue
        title = ins.get("title")
        message = ins.get("message")
        if title or message:
            insight_snapshot.append({
                "type": ins.get("type"),
                "priority": ins.get("priority"),
                "severity": ins.get("severity"),
                "title": title,
                "message": message,
            })
        if len(insight_snapshot) >= 6:
            break

    capabilities = []
    for role, profile in (capability_map or {}).items():
        if isinstance(profile, dict) and profile.get("usable", False):
            capabilities.append(role)

    limitations = _build_limitations(df, metric_status, metric_values)

    return {
        "prompt_version": BUSINESS_ADVISOR_PROMPT_VERSION,
        "business_summary": {
            "row_count": row_count,
            "date_range": date_range,
            "available_capabilities": capabilities,
        },
        "metrics": metrics_section,
        "top_entities": entities,
        "trends": trends,
        "insight_snapshot": insight_snapshot,
        "data_limitations": limitations,
        "facts": facts,
    }


# ===========================================================================
# 5. Response parsing
# ===========================================================================

def _parse_json_object(raw):
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# ===========================================================================
# 6. Validation (schema / enums / lengths / fact-ID whitelist)
# ===========================================================================

def _validate_strings(item, fields, max_len, errors, where):
    for field in fields:
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}.{field}: must be a non-empty string.")
        elif len(value) > max_len:
            errors.append(f"{where}.{field}: exceeds max length {max_len}.")


def _validate_fact_ids(item, errors, where, present_ids):
    fact_ids = item.get("fact_ids")
    if not isinstance(fact_ids, list):
        errors.append(f"{where}.fact_ids: must be a list of fact IDs.")
        return
    for fid in fact_ids:
        if not isinstance(fid, str) or not fid:
            errors.append(f"{where}.fact_ids: entries must be non-empty strings.")
        elif fid in KNOWN_FACT_IDS and fid not in present_ids:
            errors.append(f"{where}.fact_ids: '{fid}' is not present in the verified fact pack.")
        elif fid not in KNOWN_FACT_IDS:
            errors.append(f"{where}.fact_ids: '{fid}' is not a known fact ID.")


def _validate_priority_item(item, errors, where, present_ids):
    _validate_strings(item, ("title", "action", "reason"), _MAX_ITEM_STRING, errors, where)
    for field in ("priority", "impact", "effort"):
        value = item.get(field)
        if value not in _TRI_CHOICES:
            errors.append(f"{where}.{field}: must be one of {_TRI_CHOICES}.")
    _validate_fact_ids(item, errors, where, present_ids)


def _validate_list_item(item, errors, where, present_ids, extra_fields):
    _validate_strings(item, ("title",) + tuple(extra_fields), _MAX_ITEM_STRING, errors, where)
    _validate_fact_ids(item, errors, where, present_ids)


def validate_advisor_response(data, fact_pack=None):
    """
    Returns a list of human-readable validation errors ([] == valid).
    Never raises; never leaks data.
    """
    errors = []

    required = ("summary", "health", "priorities", "opportunities", "risks",
                "observations", "data_limitations")
    for key in required:
        if key not in data:
            errors.append(f"Missing required key '{key}'.")

    summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary: must be a non-empty string.")
    elif len(summary) > _MAX_STRING:
        errors.append(f"summary: exceeds max length {_MAX_STRING}.")

    health = data.get("health")
    if not isinstance(health, dict):
        errors.append("health: must be an object.")
    else:
        if health.get("overall") not in _OVERALL_CHOICES:
            errors.append(f"health.overall: must be one of {_OVERALL_CHOICES}.")
        explanation = health.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            errors.append("health.explanation: must be a non-empty string.")
        elif len(explanation) > _MAX_STRING:
            errors.append(f"health.explanation: exceeds max length {_MAX_STRING}.")

    present_ids = frozenset(
        f.get("id") for f in (fact_pack or {}).get("facts", []) if isinstance(f, dict)
    )

    priorities = data.get("priorities")
    if not isinstance(priorities, list) or not 0 <= len(priorities) <= _MAX_PRIORITIES:
        errors.append(f"priorities: must be a list of 0..{_MAX_PRIORITIES} items.")
    else:
        for i, item in enumerate(priorities):
            _validate_priority_item(item or {}, errors, f"priorities[{i}]", present_ids)

    for key, extra in (("opportunities", ("explanation", "action")),
                       ("risks", ("explanation", "action"))):
        items = data.get(key)
        if not isinstance(items, list) or not 0 <= len(items) <= (
                _MAX_OPPORTUNITIES if key == "opportunities" else _MAX_RISKS):
            errors.append(f"{key}: must be a list of up to "
                          f"{_MAX_OPPORTUNITIES if key == 'opportunities' else _MAX_RISKS} items.")
        else:
            for i, item in enumerate(items):
                _validate_list_item(item or {}, errors, f"{key}[{i}]", present_ids, extra)

    observations = data.get("observations")
    if not isinstance(observations, list) or not 0 <= len(observations) <= _MAX_OBSERVATIONS:
        errors.append(f"observations: must be a list of 0..{_MAX_OBSERVATIONS} items.")
    else:
        for i, item in enumerate(observations):
            _validate_list_item(item or {}, errors, f"observations[{i}]", present_ids,
                                ("message",))

    limitations = data.get("data_limitations")
    if not isinstance(limitations, list) or not 0 <= len(limitations) <= _MAX_LIMITATIONS:
        errors.append(f"data_limitations: must be a list of 0..{_MAX_LIMITATIONS} strings.")
    else:
        for i, text in enumerate(limitations):
            if not isinstance(text, str) or not text.strip():
                errors.append(f"data_limitations[{i}]: must be a non-empty string.")
            elif len(text) > _MAX_ITEM_STRING:
                errors.append(f"data_limitations[{i}]: exceeds max length {_MAX_ITEM_STRING}.")

    return errors


# ===========================================================================
# 7. Hallucination guard (numbers must be backed by a verified fact)
# ===========================================================================

def _collect_approved_numbers(obj):
    """Every number the advisory can legitimately cite (recursively)."""
    approved = set()

    def walk(value):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            approved.add(float(value))
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            # period / date strings such as "2024-01" or "2024-06-15"
            for token in _INT_TOKEN_RE.findall(value):
                approved.add(float(token))

    walk(obj)

    scaled = set()
    for a in approved:
        scaled.add(round(a, 2))
        if abs(a) < 1.0:
            # a fraction can legitimately be restated as a percentage (0.5 -> 50)
            scaled.add(a * 100.0)
            scaled.add(round(a * 100.0, 2))
    approved.update(scaled)
    for n in range(16):
        approved.add(float(n))
    return approved


def _number_approved(token, approved):
    x = float(token)
    if not math.isfinite(x):
        return False
    for a in approved:
        if abs(x - a) <= max(0.01, abs(a) * 0.005):
            return True
    return False


def _iter_number_tokens(text):
    for match in _NUMBER_TOKEN_RE.finditer(text.replace(",", "")):
        yield match.group(0)


def _hallucination_errors(data, fact_pack):
    """Returns a list of unsupported numbers appearing in the advice."""
    if not isinstance(data, dict):
        return ["Advice is not an object."]
    approved = _collect_approved_numbers(fact_pack)
    # Drop numbers that were themselves generated by the LLM (they must all be
    # checked against the fact pack, never autosigned). Serialize only safe
    # scalar fields of the response (strings + the JSON's own numbers).
    text_parts = []
    for key in ("summary",):
        v = data.get(key)
        if isinstance(v, str):
            text_parts.append(v)
    health = data.get("health")
    if isinstance(health, dict):
        for key in ("explanation",):
            if isinstance(health.get(key), str):
                text_parts.append(health[key])
    for key in ("priorities", "opportunities", "risks", "observations",
                "data_limitations"):
        for item in data.get(key) or []:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                for field in ("title", "action", "reason", "explanation", "message"):
                    if isinstance(item.get(field), str):
                        text_parts.append(item[field])

    text = "\n".join(text_parts)
    errors = []
    for token in _iter_number_tokens(text):
        if not _number_approved(token, approved):
            errors.append(f"Unsupported number '{token}' without a matching verified fact.")
    return errors[:8]


# ===========================================================================
# 8. Deterministic mock advisor (used by MockLLMProvider in mock mode)
# ===========================================================================

def _fact(facts, fid):
    return next((f for f in facts if f.get("id") == fid), None)


def _money(value):
    return f"{value:,.2f}"


def _pct(value):
    return f"{value * 100:.1f}%"


def mock_advisor_response(fact_pack):
    """
    Deterministic, valid advisor JSON built purely from the verified fact
    pack. Used in mock mode (LLM_MODE=mock) and by tests; no network, no
    time, no random ids.
    """
    facts = fact_pack.get("facts", [])

    def v(fid):
        f = _fact(facts, fid)
        return f.get("value") if f else None

    revenue = v(FACT_REVENUE)
    orders = v(FACT_ORDERS)
    net_profit = v(FACT_NET_PROFIT)
    gross_margin = v(FACT_GROSS_MARGIN)
    top_customer = (_fact(facts, FACT_TOP_CUSTOMER) or {}).get("value")
    concentration = v(FACT_CUSTOMER_CONCENTRATION)
    revenue_growth = v(FACT_REVENUE_GROWTH)
    revenue_trend = v(FACT_REVENUE_TREND)

    # ---- summary -----------------------------------------------------------
    if revenue is None:
        summary = "Revenue data was not available, so no financial assessment could be produced."
    else:
        bits = [f"Total revenue from delivered orders was {_money(revenue)}"]
        if orders is not None:
            bits.append(f"across {int(orders)} delivered orders")
        if gross_margin is not None:
            bits.append(f"with a gross margin of {_pct(gross_margin)}")
        summary = " ".join(bits) + "."

    # ---- health ------------------------------------------------------------
    if revenue is None:
        overall = "insufficient_data"
        explanation = "Not enough verified data was available to assess business health."
    elif net_profit is None:
        overall = "mixed"
        explanation = (
            "Revenue was verified, but net profitability could not be assessed "
            "because shipping and/or marketing expense data was not detected."
        )
    elif net_profit < 0:
        overall = "negative"
        explanation = "Net profit is negative: total costs exceeded revenue."
    elif gross_margin is not None and gross_margin > 0.5:
        overall = "positive"
        explanation = f"Healthy gross margin ({_pct(gross_margin)}) with positive net profit."
    else:
        overall = "positive" if net_profit > 0 else "mixed"
        explanation = f"Net profit was positive ({_money(net_profit)})."

    # ---- priorities --------------------------------------------------------
    priorities = []
    if revenue is not None and (revenue_trend == "decreasing" or
            (revenue_growth is not None and revenue_growth < 0)):
        decline_ids = [FACT_REVENUE, FACT_REVENUE_TREND]
        if _fact(facts, FACT_REVENUE_GROWTH):
            decline_ids.append(FACT_REVENUE_GROWTH)
        priorities.append({
            "title": "Investigate the recent revenue decline",
            "action": "Review pricing, promotions and product mix to identify the cause.",
            "reason": f"Revenue decreased and is currently {_money(revenue)}; "
                      "arresting the decline protects total revenue.",
            "priority": "high", "impact": "high", "effort": "medium",
            "fact_ids": decline_ids,
        })
    elif gross_margin is not None and gross_margin < 0.2 and revenue is not None:
        priorities.append({
            "title": "Review product profitability",
            "action": "Analyze costs and pricing per product to improve gross margin.",
            "reason": f"Gross margin is {_pct(gross_margin)}, leaving little room for overheads.",
            "priority": "high", "impact": "high", "effort": "medium",
            "fact_ids": [FACT_GROSS_MARGIN, FACT_REVENUE],
        })
    else:
        priorities.append({
            "title": "Grow order volume sustainably",
            "action": "Identify the most effective channels and increase order frequency.",
            "reason": f"The business verified {int(orders)} delivered orders; "
                      "order growth compounds revenue.",
            "priority": "medium", "impact": "medium", "effort": "medium",
            "fact_ids": [FACT_ORDERS, FACT_REVENUE],
        })

    if top_customer and concentration is not None and concentration >= 0.3:
        priorities.append({
            "title": "Diversify the customer base",
            "action": "Target new customer segments to reduce dependence on the top customer.",
            "reason": f"{_pct(concentration)} of revenue came from one customer "
                      f"({_safe_entity_label(top_customer)}); concentration is a revenue risk.",
            "priority": "high", "impact": "high", "effort": "high",
            "fact_ids": [FACT_TOP_CUSTOMER, FACT_CUSTOMER_CONCENTRATION, FACT_REVENUE],
        })

    # ---- opportunities -----------------------------------------------------
    opportunities = []
    if revenue_growth is not None and revenue_growth > 0:
        opportunities.append({
            "title": "Extend the current revenue momentum",
            "explanation": "Revenue grew in the latest period; sustaining this is a hypothesis "
                           "worth investigating.",
            "action": "Study which products or customers drove the growth.",
            "fact_ids": [FACT_REVENUE_GROWTH, FACT_REVENUE],
        })
    if gross_margin is not None and gross_margin >= 0.5:
        opportunities.append({
            "title": "Test higher volume at the current margin",
            "explanation": f"The gross margin ({_pct(gross_margin)}) supports room to invest "
                           "in acquisition while staying profitable.",
            "action": "Consider marketing investment experiments.",
            "fact_ids": [FACT_GROSS_MARGIN],
        })

    # ---- risks -------------------------------------------------------------
    risks = []
    if net_profit is not None and net_profit < 0:
        risks.append({
            "title": "Negative net profit",
            "explanation": f"Net profit was {_money(net_profit)}; costs exceeded revenue.",
            "action": "Review cost structure before scaling spend.",
            "fact_ids": [FACT_NET_PROFIT, FACT_REVENUE],
        })
    if top_customer and concentration is not None and concentration >= 0.3:
        risks.append({
            "title": "Customer concentration",
            "explanation": f"{_pct(concentration)} of revenue depends on one customer.",
            "action": "Diversify revenue sources.",
            "fact_ids": [FACT_TOP_CUSTOMER, FACT_CUSTOMER_CONCENTRATION],
        })
    return_rate = v(FACT_RETURN_CANCEL_RATE)
    if return_rate is not None and return_rate > 0.15:
        risks.append({
            "title": "Elevated return/cancel rate",
            "explanation": f"{_pct(return_rate)} of orders were cancelled or returned.",
            "action": "Investigate product quality and fulfillment issues.",
            "fact_ids": [FACT_RETURN_CANCEL_RATE],
        })

    # ---- observations ------------------------------------------------------
    observations = []
    if revenue is not None:
        observations.append({
            "title": "Revenue",
            "message": f"Verified revenue from delivered orders was {_money(revenue)}.",
            "fact_ids": [FACT_REVENUE],
        })
    if orders is not None:
        observations.append({
            "title": "Orders",
            "message": f"Verified delivered orders: {int(orders)}.",
            "fact_ids": [FACT_ORDERS],
        })
    if gross_margin is not None:
        observations.append({
            "title": "Gross margin",
            "message": f"Verified gross margin was {_pct(gross_margin)}.",
            "fact_ids": [FACT_GROSS_MARGIN],
        })
    if net_profit is not None:
        observations.append({
            "title": "Net profit",
            "message": f"Verified net profit was {_money(net_profit)}.",
            "fact_ids": [FACT_NET_PROFIT, FACT_REVENUE],
        })
    if revenue_trend:
        observations.append({
            "title": "Revenue trend",
            "message": f"Verified revenue trend direction: {revenue_trend}.",
            "fact_ids": [FACT_REVENUE_TREND],
        })

    return {
        "summary": summary,
        "health": {"overall": overall, "explanation": explanation},
        "priorities": priorities,
        "opportunities": opportunities,
        "risks": risks,
        "observations": observations,
        "data_limitations": list(fact_pack.get("data_limitations", [])),
    }


# ===========================================================================
# 9. Public entry point
# ===========================================================================

_UNAVAILABLE_REASON = "Business advisor is currently unavailable."
_UNAVAILABLE = {
    "status": "UNAVAILABLE",
    "summary": None,
    "reason": _UNAVAILABLE_REASON,
}


def _unavailable(reason=None):
    out = dict(_UNAVAILABLE)
    if reason:
        out["reason"] = reason
    return out


def generate_business_advice(
    df,
    mapping=None,
    capability_map=None,
    metric_values=None,
    metric_status=None,
    structured_insights=None,
    chart_specs=None,
    profiler=None,
    provider=None,
):
    """
    Phase 7 public entry point. Returns the advisor dict for the /process
    response. NEVER raises and NEVER breaks the rest of the API.

    On success:     {"status": "AVAILABLE", "prompt_version":
                    "business-advisor-v1", "summary", "health", "priorities",
                    "opportunities", "risks", "observations",
                    "data_limitations"}.
    On any failure: {"status": "UNAVAILABLE", "summary": None,
                    "reason": "Business advisor is currently unavailable."}.
    """
    try:
        fact_pack = build_advisor_fact_pack(
            df, mapping=mapping, capability_map=capability_map,
            metric_values=metric_values, metric_status=metric_status,
            structured_insights=structured_insights,
            chart_specs=chart_specs, profiler=profiler,
        )
    except Exception:
        return _unavailable()

    if provider is None:
        from pipeline.llm import get_llm_provider
        try:
            provider = get_llm_provider()
        except Exception:
            return _unavailable()

    context = build_business_advisor_context(fact_pack)
    try:
        raw = provider.complete(
            context["_system_prompt"], context["_user_prompt"], context=context
        )
    except Exception:
        return _unavailable()

    parsed = _parse_json_object(raw)
    if parsed is None:
        return _unavailable()

    errors = validate_advisor_response(parsed, fact_pack)
    if errors:
        return _unavailable()

    hallucination_errors = _hallucination_errors(parsed, fact_pack)
    if hallucination_errors:
        return _unavailable()

    parsed["status"] = "AVAILABLE"
    parsed["prompt_version"] = fact_pack.get("prompt_version", BUSINESS_ADVISOR_PROMPT_VERSION)
    return parsed