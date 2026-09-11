"""
metrics.py  —  PHASE 4: capability-aware (dynamic) metrics.

The metric engine only calculates and exposes metrics that are actually
supported by the uploaded dataset. It follows the same principle as the
Phase 3 Capability Engine:

    MISSING DATA != ZERO.

If a dataset has Revenue + COGS but no Shipping or Marketing, the engine must
NOT report:

    Net Profit = Gross Profit

Instead Net Profit is NOT_AVAILABLE (value None, explicit reason). The engine
never invents missing costs (shipping, marketing, COGS) as zero.

Canonical financial model (reconciled in Phase 4):

    Revenue
      − COGS
    = Gross Profit              (revenue − cost_of_goods)
      − Shipping
      − Marketing
    = Net Profit                (revenue − cost_of_goods − shipping − marketing)

Every metric has a registry entry in METRIC_DEFINITIONS declaring its field
requirements (STANDARD_FIELDS names), its dependency chain, its label and its
category. A metric is AVAILABLE only when every required field exists AND is
usable; otherwise it is NOT_AVAILABLE with value None (never 0) and a reason
listing the missing requirements.

Calculations are pure Python. The LLM is never asked to compute numbers.

This module operates on the cleaned, user-confirmed dataframe received by
/post/process, so it needs no profiler call and no LLM call: the confirmed
mapping already tells us which physical columns back each standard field, and
field usability is re-checked deterministically on the actual data (null
percentage, numeric dtype, uniqueness) using the same thresholds as the
Capability Engine.
"""

import pandas as pd

from pipeline.capabilities import NULL_MAX_MEASURE, NULL_MAX_DIMENSION


# ===========================================================================
# 1. Shared dataframe helpers (unchanged from earlier phases)
# ===========================================================================

def _cancelled_mask(df):
    """Returns a boolean Series marking cancelled / returned / RTO orders."""
    if "status" in df.columns:
        return df["status"].astype(str).str.lower().str.contains("cancel|return|rto", na=False)
    return pd.Series([False] * len(df), index=df.index)


def _ensure_dates(df):
    """Copies df, coerces order_date to datetime, drops unparseable dates."""
    if "order_date" not in df.columns:
        return df
    dated = df.copy()
    dated["order_date"] = pd.to_datetime(dated["order_date"], errors="coerce")
    return dated.dropna(subset=["order_date"])


# ===========================================================================
# 2. Usability thresholds (same numbers as the Capability Engine)
# ===========================================================================

# A confirmed-mapped column is still not usable on its own:
#   - numeric measures need a numeric dtype and at most 50% null,
#   - dimension fields (customer/product/status) need at most 80% null and
#     at least 2 distinct values (a constant column is not a useful dimension).


def _field_usable(series, kind):
    """
    Deterministic usability check for one standard field's data.
    kind == "measure"  -> numeric measure (revenue, costs, quantity)
    kind == "dimension"-> category-ish field (customer_id, product_id, status)
    Returns (usable: bool, reason: str | None).
    """
    if series is None:
        return False, "not present in the mapped data"
    if len(series) == 0:
        return False, "no data rows"
    null_pct = float(series.isna().mean())

    if kind == "measure":
        if not pd.api.types.is_numeric_dtype(series):
            return False, f"has non-numeric values (inferred dtype: {series.dtype})"
        if null_pct > NULL_MAX_MEASURE:
            return False, f"is mostly empty ({null_pct*100:.0f}% null)"
        return True, None

    if null_pct > NULL_MAX_DIMENSION:
        return False, f"is mostly empty ({null_pct*100:.0f}% null)"
    if series.nunique() < 2:
        return False, "has fewer than 2 unique values (constant/empty column)"
    return True, None


# ===========================================================================
# 3. Metric registry (requirements use STANDARD_FIELDS names)
# ===========================================================================

# Human-readable labels for the fields used in reasons (kept readable for both
# API consumers and non-technical users).
_FIELD_LABELS = {
    "revenue": "revenue",
    "cost_of_goods": "cost of goods sold (COGS)",
    "shipping_cost": "shipping expense",
    "marketing_spend": "marketing expense",
    "customer_id": "customer identifier",
    "product_id": "product identifier",
    "quantity": "quantity",
    "status": "order status",
}

# Metric key -> legacy display key used by the pre-Phase-4 `metrics` dict,
# so existing consumers keep working unchanged.
_LEGACY_KEYS = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "shipping": "Shipping Cost",
    "marketing": "Marketing Spend",
    "gross_profit": "Gross Profit",
    "net_profit": "Net Profit",
    "orders": "Orders",
    "average_order_value": "AOV",
    "customer_acquisition_cost": "CAC",
    "repeat_purchase_rate": "Repeat Purchase Rate",
    "return_cancel_rate": "Return/Cancel Rate",
}

# Rounding used for raw values returned from the calculation layer. Money and
# ratios remain raw numbers; formatting is a separate concern.
_ROUND = {
    "money": 2,
    "count": 4,
    "margin": 6,
}

# Reference data (informative defaults) for rounding each metric value.
_METRIC_ROUND = {
    "revenue": "money", "cogs": "money", "shipping": "money", "marketing": "money",
    "gross_profit": "money", "net_profit": "money", "average_order_value": "money",
    "customer_acquisition_cost": "money",
    "orders": "int",
    "repeat_purchase_rate": "count", "return_cancel_rate": "count",
    "gross_profit_margin": "margin", "net_profit_margin": "margin",
    "quantity": "money",
}

METRIC_DEFINITIONS: dict[str, dict] = {
    "revenue": {
        "label": "Revenue",
        "category": "financial",
        "description": "Total revenue from delivered orders.",
        "requirements": ["revenue"],
        "requires_metrics": [],
        "formula": "sum(revenue)",
    },
    "cogs": {
        "label": "COGS",
        "category": "financial",
        "description": "Total cost of goods sold.",
        "requirements": ["cost_of_goods"],
        "requires_metrics": [],
        "formula": "sum(cost_of_goods)",
    },
    "gross_profit": {
        "label": "Gross Profit",
        "category": "financial",
        "description": "Gross Profit = Revenue - COGS.",
        "requirements": ["revenue", "cost_of_goods"],
        "requires_metrics": ["revenue", "cogs"],
        "formula": "revenue - cost_of_goods",
    },
    "gross_profit_margin": {
        "label": "Gross Profit Margin",
        "category": "financial",
        "description": "Gross Profit / Revenue, as a fraction.",
        "requirements": ["revenue", "cost_of_goods"],
        "requires_metrics": ["gross_profit", "revenue"],
        "formula": "gross_profit / revenue (undefined when revenue == 0)",
    },
    "shipping": {
        "label": "Shipping Cost",
        "category": "financial",
        "description": "Total shipping / fulfillment expense.",
        "requirements": ["shipping_cost"],
        "requires_metrics": [],
        "formula": "sum(shipping_cost); missing shipping is never assumed to be zero",
    },
    "marketing": {
        "label": "Marketing Spend",
        "category": "financial",
        "description": "Total marketing / advertising spend.",
        "requirements": ["marketing_spend"],
        "requires_metrics": [],
        "formula": "sum(marketing_spend); missing marketing is never assumed to be zero",
    },
    "net_profit": {
        "label": "Net Profit",
        "category": "financial",
        "description": "Net Profit = Revenue - COGS - Shipping - Marketing.",
        "requirements": ["revenue", "cost_of_goods", "shipping_cost", "marketing_spend"],
        "requires_metrics": ["gross_profit", "shipping", "marketing"],
        "formula": "revenue - cost_of_goods - shipping_cost - marketing_spend",
    },
    "net_profit_margin": {
        "label": "Net Profit Margin",
        "category": "financial",
        "description": "Net Profit / Revenue, as a fraction.",
        "requirements": ["revenue", "cost_of_goods", "shipping_cost", "marketing_spend"],
        "requires_metrics": ["net_profit", "revenue"],
        "formula": "net_profit / revenue (undefined when revenue == 0)",
    },
    "orders": {
        "label": "Orders",
        "category": "financial",
        "description": "Number of delivered orders.",
        "requirements": [],
        "requires_metrics": [],
        "requires_rows": True,
        "formula": "count of delivered rows",
    },
    "average_order_value": {
        "label": "Average Order Value",
        "category": "financial",
        "description": "Revenue / Orders.",
        "requirements": ["revenue"],
        "requires_metrics": ["revenue", "orders"],
        "formula": "revenue / orders (undefined when orders == 0)",
    },
    "quantity": {
        "label": "Total Quantity",
        "category": "financial",
        "description": "Total units sold.",
        "requirements": ["quantity"],
        "requires_metrics": [],
        "formula": "sum(quantity)",
    },
    "customer_acquisition_cost": {
        "label": "Customer Acquisition Cost",
        "category": "customer",
        "description": "Marketing Spend / number of new customers.",
        "requirements": ["marketing_spend", "customer_id"],
        "requires_metrics": ["marketing"],
        "formula": "marketing_spend / new_customers (undefined when there are no new customers)",
    },
    "repeat_purchase_rate": {
        "label": "Repeat Purchase Rate",
        "category": "customer",
        "description": "Share of customers with more than one order.",
        "requirements": ["customer_id"],
        "requires_metrics": [],
        "formula": "repeat_customers / total_customers",
    },
    "return_cancel_rate": {
        "label": "Return/Cancel Rate",
        "category": "operations",
        "description": "Cancelled / returned orders as a share of all orders.",
        "requirements": ["status"],
        "requires_metrics": [],
        "formula": "cancelled orders / total orders",
    },
}


def _missing_fields(requirements, field_availability):
    """Raw STANDARD_FIELDS names of required fields that are not usable."""
    return [
        req for req in requirements
        if not field_availability.get(req, (False, "not present"))[0]
    ]


def _missing_labels(fields):
    """Human-readable labels for fields, used only in the reason text."""
    return [_FIELD_LABELS.get(f, f) for f in fields]


def _round_metric(key, value):
    if value is None:
        return None
    mode = _METRIC_ROUND.get(key, "money")
    if mode == "int":
        return int(round(float(value)))
    digits = _ROUND[mode]
    return round(float(value), digits)


# ===========================================================================
# 4. Capability-aware metric evaluation
# ===========================================================================

def evaluate_metrics(df):
    """
    Evaluates every registered metric against the cleaned dataframe.

    A metric is AVAILABLE when all of its required standard fields are present
    AND usable in the data, and any additional guard (e.g. revenue != 0 for
    margins) holds. Otherwise the metric is NOT_AVAILABLE with value None and
    an explicit reason.

    Returns:
        {
            "metrics":        legacy display-key dict (raw values, None where
                              unavailable) — exactly the shape pre-Phase-4
                              consumers expected,
            "metric_values":  snake_case key -> raw value (or None),
            "metric_status":  key -> {status, value, label, category,
                              description, requirements, missing_requirements,
                              requires_metrics, reason},
        }
    """
    empty = {
        "metrics": {
            "Revenue": None, "COGS": None, "Shipping Cost": None,
            "Marketing Spend": None, "Gross Profit": None, "Net Profit": None,
            "Orders": None, "AOV": None, "CAC": None,
            "Repeat Purchase Rate": None, "Return/Cancel Rate": None,
        },
        "metric_values": {},
        "metric_status": {},
    }
    if df is None or len(df) == 0:
        for key, defn in METRIC_DEFINITIONS.items():
            empty["metric_status"][key] = {
                "status": "NOT_AVAILABLE",
                "value": None,
                "label": defn["label"],
                "category": defn["category"],
                "description": defn["description"],
                "requirements": list(defn["requirements"]),
                "missing_requirements": list(defn["requirements"]),
                "requires_metrics": list(defn.get("requires_metrics", [])),
                "reason": "No data rows were available to calculate this metric.",
            }
            empty["metric_values"][key] = None
        return empty

    if "status" in df.columns:
        cancelled_mask = (
            df["status"].astype(str).str.lower().str.contains("cancel|return|rto", na=False)
        )
    else:
        cancelled_mask = pd.Series([False] * len(df), index=df.index)

    delivered = df[~cancelled_mask]
    rows_exist = len(df) > 0

    # ---- field availability (deterministic, on the delivered population) ----
    field_availability: dict[str, tuple[bool, str | None]] = {}
    for field in ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend", "quantity"):
        field_availability[field] = _field_usable(
            delivered[field] if field in delivered.columns else None, "measure"
        )
    for field in ("customer_id", "product_id"):
        field_availability[field] = _field_usable(
            delivered[field] if field in delivered.columns else None, "dimension"
        )
    # 'status' must be usable on the FULL dataframe: its whole purpose is to
    # distinguish delivered from cancelled rows, and on the delivered subset it
    # is naturally constant.
    field_availability["status"] = _field_usable(
        df["status"] if "status" in df.columns else None, "dimension"
    )

    def usable(field):
        return field_availability.get(field, (False, "not present"))[0]

    # ---- raw component values -----------------------------------------------
    def _sum(field):
        return float(delivered[field].sum()) if usable(field) else None

    revenue = _sum("revenue")
    cogs = _sum("cost_of_goods")
    shipping = _sum("shipping_cost")
    marketing = _sum("marketing_spend")
    quantity = _sum("quantity")

    gross_profit = (revenue - cogs) if (revenue is not None and cogs is not None) else None
    net_profit = (
        (revenue - cogs - shipping - marketing)
        if (revenue is not None and cogs is not None
            and shipping is not None and marketing is not None)
        else None
    )

    orders = len(delivered)
    aov = (revenue / orders) if (revenue is not None and orders > 0) else None
    gross_margin = (
        gross_profit / revenue
        if (gross_profit is not None and revenue is not None and revenue != 0)
        else None
    )
    net_margin = (
        net_profit / revenue
        if (net_profit is not None and revenue is not None and revenue != 0)
        else None
    )

    # ---- customer-derived values ---------------------------------------------
    cac = None
    repeat_rate = None
    new_customers = 0
    if usable("customer_id"):
        counts = delivered["customer_id"].value_counts()
        new_customers = int((counts == 1).sum())
        repeat_customers = int((counts > 1).sum())
        if len(counts):
            repeat_rate = repeat_customers / len(counts)
        if marketing is not None and new_customers:
            cac = marketing / new_customers

    return_rate = None
    if usable("status") and rows_exist:
        return_rate = cancelled_mask.sum() / len(df)

    # ---- metric values (snake_case) ------------------------------------------
    values = {
        "revenue": _round_metric("revenue", revenue),
        "cogs": _round_metric("cogs", cogs),
        "shipping": _round_metric("shipping", shipping),
        "marketing": _round_metric("marketing", marketing),
        "gross_profit": _round_metric("gross_profit", gross_profit),
        "net_profit": _round_metric("net_profit", net_profit),
        "gross_profit_margin": _round_metric("gross_profit_margin", gross_margin),
        "net_profit_margin": _round_metric("net_profit_margin", net_margin),
        "orders": _round_metric("orders", orders),
        "average_order_value": _round_metric("average_order_value", aov),
        "quantity": _round_metric("quantity", quantity),
        "customer_acquisition_cost": _round_metric("customer_acquisition_cost", cac),
        "repeat_purchase_rate": _round_metric("repeat_purchase_rate", repeat_rate),
        "return_cancel_rate": _round_metric("return_cancel_rate", return_rate),
    }

    # ---- guards beyond field presence (division-by-zero, empty populations) ---
    guard_reason = {}
    if revenue is not None and revenue == 0:
        guard_reason["gross_profit_margin"] = "Revenue is zero, so Gross Profit Margin is mathematically undefined."
        guard_reason["net_profit_margin"] = "Revenue is zero, so Net Profit Margin is mathematically undefined."
    if orders == 0:
        guard_reason["average_order_value"] = "No delivered orders, so Average Order Value is mathematically undefined."
    if cac is None and usable("marketing_spend") and usable("customer_id") and new_customers == 0:
        guard_reason["customer_acquisition_cost"] = "No new customers were found, so Customer Acquisition Cost is undefined."

    # ---- assemble statuses -----------------------------------------------------
    metric_status = {}
    for key, defn in METRIC_DEFINITIONS.items():
        requirements = list(defn.get("requirements", []))
        missing = _missing_fields(requirements, field_availability)
        requires_rows = defn.get("requires_rows", False)

        reason = None
        if (not requires_rows or rows_exist) and not missing and key not in guard_reason:
            status = "AVAILABLE"
            actual_value = values[key]
        else:
            status = "NOT_AVAILABLE"
            actual_value = None
            if missing:
                reason = (
                    "Required data not detected: "
                    + ", ".join(_missing_labels(missing))
                    + "."
                )
            elif guard_reason.get(key):
                reason = guard_reason[key]
            elif requires_rows and not rows_exist:
                reason = "No data rows were available to calculate this metric."
            else:
                reason = "Required data not detected."

        metric_status[key] = {
            "status": status,
            "value": actual_value,
            "label": defn["label"],
            "category": defn["category"],
            "description": defn["description"],
            "requirements": requirements,
            "missing_requirements": missing,
            "requires_metrics": list(defn.get("requires_metrics", [])),
            "reason": reason,
        }

    # ---- legacy display-key metrics dict (raw values, None where unavailable) --
    legacy_metrics = {
        display_key: (values[key] if metric_status[key]["status"] == "AVAILABLE" else None)
        for key, display_key in _LEGACY_KEYS.items()
    }

    return {
        "metrics": legacy_metrics,
        "metric_values": values,
        "metric_status": metric_status,
    }


def compute_metrics(df):
    """
    Backwards-compatible entry point: returns the legacy display-key raw
    metrics dict. Unavailable metrics are None (never 0), matching the
    pre-Phase-4 dict shape so existing consumers keep working.
    """
    return evaluate_metrics(df)["metrics"]


# ===========================================================================
# 5. Display formatting (separate from calculation, as before)
# ===========================================================================

def format_metrics_for_display(metrics):
    """
    Converts the raw metrics dict into display-friendly strings, used only for
    showing the table / KPI cards. Formatting is purely presentational; the raw
    numbers in `compute_metrics()` / `evaluate_metrics()` remain unchanged.
    """
    display = dict(metrics)

    if display.get("CAC") is None:
        display["CAC"] = "N/A"

    repeat = display.get("Repeat Purchase Rate")
    if repeat is None:
        display["Repeat Purchase Rate"] = "N/A"
    else:
        display["Repeat Purchase Rate"] = f"{repeat*100:.1f}%"

    ret = display.get("Return/Cancel Rate")
    if ret is None:
        display["Return/Cancel Rate"] = "N/A"
    else:
        display["Return/Cancel Rate"] = f"{ret*100:.1f}%"

    return display


# ===========================================================================
# 6. Insights (never generate claims from unavailable metrics)
# ===========================================================================

def _unavailable_fields_text(metric_key, metric_status):
    """Returns a comma-joined phrase describing missing required fields for a metric."""
    entry = (metric_status or {}).get(metric_key, {})
    missing = entry.get("missing_requirements") or []
    if not missing:
        return None
    return ", ".join(_FIELD_LABELS.get(m, m) for m in missing)


def generate_insights(metrics, metric_status=None):
    """
    Expects the RAW metrics dict (fractions, None for missing) plus the optional
    metric_status metadata from evaluate_metrics(). Only generates financial
    insights when the underlying metric is AVAILABLE; when a metric is
    unavailable it adds an explanatory insight instead of inventing a value.
    """
    insights = []

    net_profit = metrics.get("Net Profit")
    if net_profit is None:
        missing = _unavailable_fields_text("net_profit", metric_status)
        if missing:
            insights.append(
                f"Net Profit could not be calculated because required data was "
                f"not detected: {missing}."
            )
        else:
            insights.append(
                "Net Profit could not be calculated from the current data."
            )
    elif net_profit < 0:
        insights.append(
            "Warning: Net profit is negative — total costs currently exceed revenue."
        )

    if metric_status:
        for metric_key, noun in (
            ("gross_profit_margin", "Gross Profit Margin"),
            ("net_profit_margin", "Net Profit Margin"),
            ("customer_acquisition_cost", "Customer Acquisition Cost"),
        ):
            entry = metric_status.get(metric_key) or {}
            if entry.get("status") != "AVAILABLE":
                missing = entry.get("missing_requirements") or []
                reason = entry.get("reason")
                if reason and missing:
                    insights.append(
                        f"{noun} could not be calculated. {reason}"
                    )
                elif reason:
                    insights.append(f"{noun} could not be calculated. {reason}")

    cac = metrics.get("CAC")
    aov = metrics.get("AOV")
    if cac is not None and aov is not None and aov > 0:
        if cac > aov:
            insights.append(
                "Warning: Customer Acquisition Cost (CAC) is higher than Average "
                "Order Value (AOV) — acquiring new customers may currently be "
                "unprofitable on a per-order basis."
            )

    return_rate = metrics.get("Return/Cancel Rate")
    if return_rate is not None and return_rate > 0.15:
        insights.append(
            f"Warning: Return/Cancel rate is {return_rate*100:.1f}%, which is high "
            "for eCommerce — worth investigating product quality or delivery issues."
        )

    if not insights:
        insights.append("No major red flags detected in the current data.")

    return insights


# ===========================================================================
# 7. Chart data (MISSING != ZERO)
# ===========================================================================

def generate_chart_data(df):
    """
    Generates time-series data for frontend charts.

    Returns:
        {
            "revenue_trend": [...],
            "profit_trend": [...],
            "orders_trend": [...]
        }

    Each record contains a month and the corresponding metric. A metric that is
    NOT supported by the dataset is represented with null values (never 0), and
    its derived profit metrics are also null rather than a misleading zero. This
    keeps the response shape identical to pre-Phase-4 for compatible charts
    while making MISSING != ZERO.
    """
    empty = {
        "revenue_trend": [],
        "profit_trend": [],
        "orders_trend": [],
    }

    if "order_date" not in df.columns:
        return empty

    chart_df = df.copy()
    chart_df["order_date"] = pd.to_datetime(chart_df["order_date"], errors="coerce")
    chart_df = chart_df.dropna(subset=["order_date"])

    if chart_df.empty:
        return empty

    if "status" in chart_df.columns:
        cancelled_mask = (
            chart_df["status"]
            .astype(str)
            .str.lower()
            .str.contains("cancel|return|rto", na=False)
        )
    else:
        cancelled_mask = pd.Series([False] * len(chart_df), index=chart_df.index)

    delivered = chart_df[~cancelled_mask].copy()

    if delivered.empty:
        return empty

    delivered["month"] = delivered["order_date"].dt.to_period("M")

    # Which measure columns are genuinely usable?
    chart_available = {
        field: _field_usable(delivered[field] if field in delivered.columns else None, "measure")
        for field in ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend")
    }
    has_col = {field: ok for field, (ok, _) in chart_available.items()}

    def month_series(field):
        if not has_col[field]:
            return pd.DataFrame(columns=["month", field])
        return (
            delivered.groupby("month")[field]
            .sum()
            .reset_index()
            .rename(columns={field: field})
        )

    base = pd.DataFrame({"month": delivered["month"].unique()})
    trend = base.copy()
    empty_frames = []
    for field in ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend"):
        extra = month_series(field)
        if extra.shape[0]:
            trend = trend.merge(extra, on="month", how="left")
        else:
            empty_frames.append(field)

    # Only fill missing months with zero for fields that genuinely exist in the
    # data. Fields that do not exist stay null (MISSING != ZERO).
    for field in ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend"):
        if has_col[field] and field in trend.columns:
            trend[field] = trend[field].fillna(0)
        elif field in trend.columns:
            trend[field] = None  # explicitly null for unsupported fields

    trend["month"] = trend["month"].astype(str)
    trend = trend.sort_values("month")

    orders_dict = {
        row["month"]: int(row["orders"])
        for _, row in delivered.groupby("month").size().reset_index(name="orders").iterrows()
    }

    gross_ok = has_col["revenue"] and has_col["cost_of_goods"]
    net_ok = (
        has_col["revenue"] and has_col["cost_of_goods"]
        and has_col["shipping_cost"] and has_col["marketing_spend"]
    )

    revenue_profit_data = []
    for _, row in trend.iterrows():
        month = row["month"]
        revenue_val = float(row.get("revenue")) if has_col.get("revenue") else None
        cogs_val = float(row.get("cost_of_goods")) if has_col.get("cost_of_goods") else None
        shipping_val = float(row.get("shipping_cost")) if has_col.get("shipping_cost") else None
        marketing_val = float(row.get("marketing_spend")) if has_col.get("marketing_spend") else None

        if gross_ok:
            gross_val = revenue_val - cogs_val
        else:
            gross_val = None

        if net_ok:
            net_val = revenue_val - cogs_val - shipping_val - marketing_val
        else:
            net_val = None

        revenue_profit_data.append({
            "month": month,
            "revenue": round(revenue_val, 2) if revenue_val is not None else None,
            "cogs": round(cogs_val, 2) if cogs_val is not None else None,
            "shipping": round(shipping_val, 2) if shipping_val is not None else None,
            "marketing": round(marketing_val, 2) if marketing_val is not None else None,
            "gross_profit": round(gross_val, 2) if gross_val is not None else None,
            "net_profit": round(net_val, 2) if net_val is not None else None,
            "orders": orders_dict.get(month, 0),
        })

    return {
        "revenue_trend": revenue_profit_data,
        "profit_trend": revenue_profit_data,
        "orders_trend": [
            {"month": month, "orders": orders}
            for month, orders in orders_dict.items()
        ],
    }


# ===========================================================================
# 8. Daily timeline (MISSING != ZERO)
# ===========================================================================

def generate_daily_timeline(df):
    """
    Returns one row per calendar day of delivered/non-cancelled orders, so the
    frontend can filter/aggregate by arbitrary date ranges client-side.

    Each row: {date, revenue, cogs, shipping, marketing, gross_profit,
    net_profit, orders, cancelled}. Unsupported fields are None, never 0;
    gross_profit / net_profit are None when their prerequisite fields are not
    present in the dataset.
    """
    if "order_date" not in df.columns:
        return []

    daily = _ensure_dates(df)
    if daily.empty:
        return []

    daily = daily.sort_values("order_date")
    daily = daily.copy()
    daily["date"] = daily["order_date"].dt.strftime("%Y-%m-%d")
    daily = daily.dropna(subset=["date"])

    cancelled = _cancelled_mask(daily)
    delivered = daily[~cancelled]

    if delivered.empty:
        return []

    ordered_dates = sorted(daily["date"].unique())
    delivered_counts = delivered.groupby("date").size()
    cancelled_counts = daily[cancelled].groupby(daily.loc[cancelled, "date"]).size()

    # Which measure fields are usable in this dataset?
    avail = {}
    for field in ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend"):
        avail[field] = _field_usable(
            delivered[field] if field in delivered.columns else None, "measure"
        )[0]

    def col_sum(rows, name):
        if not avail.get(name):
            return None  # field not supported by the dataset: MISSING != ZERO
        if name not in rows.columns:
            return 0.0  # field exists; this day simply has no data for it
        return float(rows[name].sum())

    delivered_by_date = {date: rows for date, rows in delivered.groupby("date")}

    gross_ok = avail["revenue"] and avail["cost_of_goods"]
    net_ok = (
        avail["revenue"] and avail["cost_of_goods"]
        and avail["shipping_cost"] and avail["marketing_spend"]
    )

    rows = []
    for date in ordered_dates:
        day_rows = delivered_by_date.get(date, pd.DataFrame())
        revenue = col_sum(day_rows, "revenue")
        cogs = col_sum(day_rows, "cost_of_goods")
        shipping = col_sum(day_rows, "shipping_cost")
        marketing = col_sum(day_rows, "marketing_spend")

        gross_profit = (revenue - cogs) if gross_ok else None
        net_profit = (
            (revenue - cogs - shipping - marketing) if net_ok else None
        )

        rows.append({
            "date": date,
            "revenue": round(revenue, 2) if revenue is not None else None,
            "cogs": round(cogs, 2) if cogs is not None else None,
            "shipping": round(shipping, 2) if shipping is not None else None,
            "marketing": round(marketing, 2) if marketing is not None else None,
            "gross_profit": round(gross_profit, 2) if gross_profit is not None else None,
            "net_profit": round(net_profit, 2) if net_profit is not None else None,
            "orders": int(delivered_counts.get(date, 0)),
            "cancelled": int(cancelled_counts.get(date, 0)),
        })

    return rows


# ===========================================================================
# 9. Customer / product per-day aggregates (unchanged; consumed by the
#    frontend's client-side date-range analysis)
# ===========================================================================

def compute_customer_data(df):
    """
    Returns per-customer, per-day aggregates of delivered orders plus the
    all-time first-order date per customer. Enough for the frontend to
    recompute repeat rate, new vs returning customers, top customers, etc.
    for any selected date range.
    """
    empty = {
        "available": False,
        "rows": [],
        "first_orders": {},
        "total_customers": 0,
        "repeat_customers": 0,
        "repeat_rate": None,
    }

    if "customer_id" not in df.columns or "order_date" not in df.columns:
        return empty

    data = _ensure_dates(df)
    if data.empty:
        return empty

    cancelled = _cancelled_mask(data)
    delivered = data[~cancelled]
    delivered = delivered[
        delivered["customer_id"].notna()
        & (delivered["customer_id"].astype(str).str.strip() != "")
    ]
    delivered = delivered.dropna(subset=["order_date"])

    if delivered.empty:
        return empty

    delivered = delivered.copy()
    delivered["customer"] = delivered["customer_id"].astype(str).str.strip()
    delivered["date"] = delivered["order_date"].dt.strftime("%Y-%m-%d")

    revenue_col = "revenue" if "revenue" in delivered.columns else None

    rows = []
    for (customer, date), day in delivered.groupby(["customer", "date"]):
        revenue = day[revenue_col].sum() if revenue_col else 0
        rows.append({
            "date": date,
            "customer": customer,
            "revenue": round(float(revenue), 2),
            "orders": int(len(day)),
        })
    rows.sort(key=lambda row: (row["date"], row["customer"]))

    first = delivered.groupby("customer")["order_date"].min()
    first_orders = {
        customer: date.strftime("%Y-%m-%d")
        for customer, date in first.items()
    }

    counts = delivered["customer_id"].value_counts()
    total_customers = int(len(counts))
    repeat_customers = int((counts > 1).sum())

    return {
        "available": True,
        "rows": rows,
        "first_orders": first_orders,
        "total_customers": total_customers,
        "repeat_customers": repeat_customers,
        "repeat_rate": round(repeat_customers / total_customers, 4) if total_customers else 0,
    }


def compute_product_data(df):
    """
    Returns per-product, per-day aggregates of delivered orders (revenue,
    units, orders). Frontend recomputes rankings/best sellers per date range.
    """
    empty = {
        "available": False,
        "has_quantity": False,
        "rows": [],
        "total_products": 0,
    }

    if "product_id" not in df.columns or "order_date" not in df.columns:
        return empty

    data = _ensure_dates(df)
    if data.empty:
        return empty

    cancelled = _cancelled_mask(data)
    delivered = data[~cancelled]
    delivered = delivered[
        delivered["product_id"].notna()
        & (delivered["product_id"].astype(str).str.strip() != "")
    ]
    delivered = delivered.dropna(subset=["order_date"])

    has_quantity = "quantity" in df.columns

    if delivered.empty:
        return {
            "available": True,
            "has_quantity": has_quantity,
            "rows": [],
            "total_products": 0,
        }

    delivered = delivered.copy()
    delivered["product"] = delivered["product_id"].astype(str).str.strip()
    delivered["date"] = delivered["order_date"].dt.strftime("%Y-%m-%d")

    revenue_col = "revenue" if "revenue" in delivered.columns else None
    quantity_col = "quantity" if has_quantity else None

    rows = []
    for (product, date), day in delivered.groupby(["product", "date"]):
        revenue = day[revenue_col].sum() if revenue_col else 0
        units = day[quantity_col].sum() if quantity_col else 0
        rows.append({
            "date": date,
            "product": product,
            "revenue": round(float(revenue), 2),
            "units": round(float(units), 2) if quantity_col else 0,
            "orders": int(len(day)),
        })
    rows.sort(key=lambda row: (row["date"], row["product"]))

    total_products = int(delivered["product"].nunique())

    return {
        "available": True,
        "has_quantity": has_quantity,
        "rows": rows,
        "total_products": total_products,
    }