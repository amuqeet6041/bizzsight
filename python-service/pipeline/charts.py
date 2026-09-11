"""
charts.py  â€”  PHASE 6: Dynamic Chart Engine.

BizSight no longer assumes every dataset supports the same charts. The chart
engine inspects the cleaned dataframe, the confirmed mapping, the metric
availability (evaluate_metrics) and the capability map (when available) and
returns a validated list of chart specifications that the frontend simply
renders. It never invents data.

Architecture is registry-driven: a chart is a candidate entry in CHART_REGISTRY
(with gating metadata) plus a deterministic generator function. Evaluation
follows the same chain as the rest of the pipeline:

    DATA AVAILABLE
        -> CAPABILITY / METRIC AVAILABLE
        -> CHART GENERATED

Safety rules (inherited from Phases 3-5):

* NEVER convert unavailable metrics to zero.
* NEVER invent missing fields or expenses.
* NEVER calculate net profit / margins from incomplete expense data.
* NEVER chart invalid numeric fields.
* A chart whose gating passes but whose data is degenerate (a single category,
  an empty series, a constant dimension) is INSUFFICIENT_DATA and is omitted
  from the usable list.

Status model:

    AVAILABLE            the chart was generated and is safe to render
    NOT_AVAILABLE        required fields / metrics are missing in the data
    INSUFFICIENT_DATA    gating passed but the data cannot support the chart

The engine is deterministic: no LLM, no randomness, no fabricated data. All
calculations are pure pandas on the cleaned dataframe.
"""

import pandas as pd

from pipeline.metrics import _cancelled_mask, _ensure_dates, _field_usable

# ===========================================================================
# 1. Shared helpers
# ===========================================================================

MEASURE_FIELDS = ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend", "quantity")
ORDER_IDENTIFIERS = ("order_id", "invoice_id", "transaction_id")
CUSTOMER_FIELDS = ("customer_id", "customer")
PRODUCT_FIELDS = ("product_id", "product")
DIMENSION_FIELDS = ("customer_id", "product_id", "status", "city", "country", "region", "payment", "channel", "category")

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

_PRIORITIES = ("high", "medium", "low")
_CATEGORIES = ("financial", "product", "customer", "geography", "operations")
_CHART_TYPES = ("line", "bar", "area", "pie", "donut", "composed")
_GROUPINGS = ("daily", "weekly", "monthly", "quarterly", "yearly")

# Value formats the frontend can use without business logic
_VALUE_FORMAT_CURRENCY = "currency"
_VALUE_FORMAT_COUNT = "count"
_VALUE_FORMAT_PERCENT = "percent"


def _delivered(df):
    """Non-cancelled / non-returned rows (empty-safe)."""
    if df is None or len(df) == 0:
        return df
    return df[~_cancelled_mask(df)]


def _usable(df, field, kind):
    return _field_usable(df[field] if field in df.columns else None, kind)[0]


def _date_usable(df):
    if "order_date" not in df.columns:
        return False
    return int(df["order_date"].notna().sum()) > 0


def _order_identifier(df):
    for field in ORDER_IDENTIFIERS:
        if field in df.columns and _usable(df, field, "dimension"):
            return field
    return None


def _customer_field(df):
    for field in CUSTOMER_FIELDS:
        if field in df.columns and _usable(df, field, "dimension"):
            return field
    return None


def _product_field(df):
    for field in PRODUCT_FIELDS:
        if field in df.columns and _usable(df, field, "dimension"):
            return field
    return None


def _metric_ok(metric_status, key):
    """True/False from metric_status; None when metric_status is not provided."""
    if metric_status is None:
        return None
    return (metric_status.get(key) or {}).get("status") == "AVAILABLE"


def _metric_value(metric_status, key):
    if metric_status is None:
        return None
    entry = metric_status.get(key) or {}
    return entry.get("value") if entry.get("status") == "AVAILABLE" else None


def _dim_series(df, field):
    """Clean, non-empty categorical series for a dimension field."""
    s = df[field].dropna().astype(str).str.strip()
    return s[s != ""]


def _dim_available(df, field):
    """True when the dimension column exists with at least one usable value.

    Unlike the numeric usability check this deliberately does NOT require at
    least two distinct values: a single-category dataset should surface as
    INSUFFICIENT_DATA (concept valid, data too thin) rather than NOT_AVAILABLE.
    """
    return field is not None and field in df.columns and not _dim_series(df, field).empty


def _money_v(value):
    return round(float(value), 2) if value is not None else None


def _round_by_format(value, value_format):
    if value is None:
        return None
    if value_format == _VALUE_FORMAT_CURRENCY:
        return round(float(value), 2)
    if value_format == _VALUE_FORMAT_PERCENT:
        return round(float(value), 4)
    return int(round(float(value)))


# ===========================================================================
# 2. Date grouping (reuses the application's existing modes)
# ===========================================================================

from datetime import timedelta


def _period_label(dt, grouping):
    """Deterministic period label for one timestamp."""
    if grouping == "daily":
        return dt.strftime("%Y-%m-%d")
    if grouping == "weekly":
        monday = dt - timedelta(days=dt.weekday())
        return monday.strftime("%Y-%m-%d")
    if grouping == "monthly":
        return dt.strftime("%Y-%m")
    if grouping == "quarterly":
        return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
    return str(dt.year)  # yearly


def _grouped_delivered(df, grouping):
    """Delivered rows annotated with their period label (chronological)."""
    d = _delivered(_ensure_dates(df))
    if d is None or d.empty:
        return d
    d = d.copy()
    d["order_date"] = pd.to_datetime(d["order_date"], errors="coerce")
    d = d.dropna(subset=["order_date"])
    d["_period"] = d["order_date"].map(lambda dt: _period_label(dt, grouping))
    return d.sort_values("order_date")


def _period_order(df, grouping):
    """Chronological list of periods present in the delivered data."""
    d = _grouped_delivered(df, grouping)
    if d is None or d.empty:
        return []
    return list(d["_period"].unique())


def _sum_trend(df, field, grouping):
    """Per-period sum of one field; periods with no data for the field are None (never 0)."""
    d = _grouped_delivered(df, grouping)
    if d is None or d.empty or field not in d.columns:
        return pd.Series(dtype=float)
    return d.groupby("_period", sort=False)[field].sum(min_count=1).dropna()


def _order_count_trend(df, grouping, order_field):
    """Per-period count of DISTINCT order identifiers (never double-counts line items)."""
    d = _grouped_delivered(df, grouping)
    if d is None or d.empty or order_field not in d.columns:
        return pd.Series(dtype=int)
    return d.groupby("_period", sort=False)[order_field].nunique()


def _combo_trend(df, parts, grouping, op):
    """
    Per-period result of `op(field_sums)` where `parts` is a list of field
    names. Only periods that are complete for every part are kept.
    """
    series = {field: _sum_trend(df, field, grouping) for field in parts}
    order = _period_order(df, grouping)
    out = {}
    for period in order:
        values = {field: series[field].get(period) for field in parts}
        if any(v is None or pd.isna(v) for v in values.values()):
            continue
        result = op(values)
        if result is None or pd.isna(result):
            continue
        out[period] = result
    return out


def _trend_spec_data(df, field, grouping, value_format):
    s = _sum_trend(df, field, grouping)
    return [
        {"period": period, field: _round_by_format(value, value_format)}
        for period, value in s.items()
    ]


def _dim_measure_ranking(df, dim_field, measure_field, delivered_only=True, limit=10):
    """Deterministic (value desc, label asc) ranking of a dimension by a measure."""
    base = _delivered(df) if delivered_only else df
    if base is None or base.empty:
        return []
    labels = _dim_series(base, dim_field)
    if labels.empty:
        return []
    tmp = base.loc[labels.index].copy()
    tmp["_dim"] = labels.loc[labels.index].values
    if measure_field:
        grouped = tmp.groupby("_dim")[measure_field].sum(min_count=1).dropna()
    else:
        grouped = tmp.groupby("_dim").size()
    rows = [{"label": label, "value": float(v)} for label, v in grouped.items()]
    rows.sort(key=lambda r: (-r["value"], r["label"]))
    return rows[: limit or len(rows)]


# ===========================================================================
# 3. Chart registry
# ===========================================================================

def _chart_spec(cid, ctype, category, title, description, priority,
                value_format, requires_fields, requires_metrics,
                x_key, series, data, source_fields, **extra):
    """Assemble one validated chart specification object."""
    spec = {
        "id": cid,
        "type": ctype,
        "title": title,
        "description": description,
        "category": category,
        "x_key": x_key,
        "series": series,
        "data": data,
        "priority": priority,
        "value_format": value_format,
        "unit": "%" if value_format == _VALUE_FORMAT_PERCENT else "",
        "requirements": list(requires_fields) + list(requires_metrics),
        "source_fields": list(source_fields),
    }
    spec.update(extra)
    return spec


def _none(reason):
    return ("NOT_AVAILABLE", None, reason)


def _insufficient(reason):
    return ("INSUFFICIENT_DATA", None, reason)


# ----------------------------- FINANCIAL ------------------------------------

def _g_revenue_trend(ctx):
    if not _date_usable(ctx.df) or not _usable(ctx.df, "revenue", "measure"):
        return _none("Required fields (date, revenue) are not usable.")
    data = _trend_spec_data(_delivered(ctx.df), "revenue", ctx.grouping, _VALUE_FORMAT_CURRENCY)
    if len(data) < 1:
        return _insufficient("No usable revenue periods were found.")
    return ("AVAILABLE", _chart_spec(
        "revenue_trend", "line", "financial", "Revenue Trend",
        "Revenue over time, grouped by period.",
        "high", _VALUE_FORMAT_CURRENCY, ("order_date", "revenue"), ("revenue",),
        "period", [{"key": "revenue", "label": "Revenue"}], data,
        ["order_date", "revenue"], sort="period_asc",
    ), None)


def _g_orders_trend(ctx):
    order_field = _order_identifier(ctx.df)
    if not _date_usable(ctx.df) or order_field is None:
        return _none("Required fields (date, order identifier) are not usable.")
    data = [
        {"period": period, "orders": int(count)}
        for period, count in _order_count_trend(ctx.df, ctx.grouping, order_field).items()
    ]
    if len(data) < 1:
        return _insufficient("No usable order periods were found.")
    return ("AVAILABLE", _chart_spec(
        "orders_trend", "bar", "financial", "Orders Trend",
        "Number of delivered orders over time.",
        "high", _VALUE_FORMAT_COUNT, ("order_date", order_field), ("orders",),
        "period", [{"key": "orders", "label": "Orders"}], data,
        ["order_date", order_field], sort="period_asc",
    ), None)


def _gross_ok(ctx):
    ok = _metric_ok(ctx.metric_status, "gross_profit")
    if ok is not None:
        return ok
    return _usable(ctx.df, "revenue", "measure") and _usable(ctx.df, "cost_of_goods", "measure")


def _g_gross_profit_trend(ctx):
    if not _date_usable(ctx.df) or not _gross_ok(ctx):
        return _none("Required gross profit inputs (date, revenue, COGS) are not usable.")
    data = _combo_trend(
        _delivered(ctx.df), ("revenue", "cost_of_goods"), ctx.grouping,
        lambda v: v["revenue"] - v["cost_of_goods"],
    )
    if not data:
        return _insufficient("No usable gross profit periods were found.")
    rows = [{"period": p, "gross_profit": _money_v(v)} for p, v in data.items()]
    return ("AVAILABLE", _chart_spec(
        "gross_profit_trend", "line", "financial", "Gross Profit Trend",
        "Gross profit (revenue minus COGS) over time.",
        "high", _VALUE_FORMAT_CURRENCY, ("order_date", "revenue", "cost_of_goods"), ("gross_profit",),
        "period", [{"key": "gross_profit", "label": "Gross Profit"}], rows,
        ["order_date", "revenue", "cost_of_goods"], sort="period_asc",
    ), None)


def _net_ok(ctx):
    ok = _metric_ok(ctx.metric_status, "net_profit")
    if ok is not None:
        return ok
    return all(_usable(ctx.df, f, "measure") for f in ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend"))


def _g_net_profit_trend(ctx):
    if not _date_usable(ctx.df) or not _net_ok(ctx):
        return _none("Required metric net_profit is unavailable (missing expense data is never assumed to be zero).")
    data = _combo_trend(
        _delivered(ctx.df),
        ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend"),
        ctx.grouping,
        lambda v: v["revenue"] - v["cost_of_goods"] - v["shipping_cost"] - v["marketing_spend"],
    )
    if not data:
        return _insufficient("No usable net profit periods were found.")
    rows = [{"period": p, "net_profit": _money_v(v)} for p, v in data.items()]
    return ("AVAILABLE", _chart_spec(
        "net_profit_trend", "line", "financial", "Net Profit Trend",
        "Net profit (revenue minus COGS, shipping and marketing) over time.",
        "high", _VALUE_FORMAT_CURRENCY,
        ("order_date", "revenue", "cost_of_goods", "shipping_cost", "marketing_spend"),
        ("net_profit",),
        "period", [{"key": "net_profit", "label": "Net Profit"}], rows,
        ["order_date", "revenue", "cost_of_goods", "shipping_cost", "marketing_spend"],
        sort="period_asc",
    ), None)


def _margin_trend(ctx, key, cid, title, description, priority):
    ok = _metric_ok(ctx.metric_status, key)
    if ok is not None and not ok:
        return _none(f"Required metric {key} is unavailable.")
    if not _date_usable(ctx.df):
        return _none("Required fields (date, revenue) are not usable.")
    if key == "net_profit_margin":
        if not _net_ok(ctx):
            return _none(f"Required metric {key} is unavailable (missing expense data is never assumed to be zero).")
        parts = ("revenue", "cost_of_goods", "shipping_cost", "marketing_spend")

        def numerator(v):
            return v["revenue"] - v["cost_of_goods"] - v["shipping_cost"] - v["marketing_spend"]
    else:
        if not _gross_ok(ctx):
            return _none(f"Required metric {key} is unavailable.")
        parts = ("revenue", "cost_of_goods")

        def numerator(v):
            return v["revenue"] - v["cost_of_goods"]

    data = _combo_trend(
        _delivered(ctx.df), parts, ctx.grouping,
        lambda v: (numerator(v) / v["revenue"]) if v["revenue"] not in (None, 0) else None,
    )
    if not data:
        return _insufficient("No usable margin periods were found.")
    rows = [{"period": p, str(key): round(float(v), 4)} for p, v in data.items()]
    return ("AVAILABLE", _chart_spec(
        cid, "line", "financial", title, description,
        priority, _VALUE_FORMAT_PERCENT, ("order_date",) + tuple(parts), (key,),
        "period", [{"key": key, "label": title}], rows,
        ["order_date"] + list(parts), sort="period_asc",
    ), None)


def _g_gross_margin_trend(ctx):
    return _margin_trend(ctx, "gross_profit_margin", "gross_margin_trend",
                         "Gross Profit Margin Trend",
                         "Gross profit as a percentage of revenue over time.",
                         "medium")


def _g_net_margin_trend(ctx):
    return _margin_trend(ctx, "net_profit_margin", "net_margin_trend",
                         "Net Profit Margin Trend",
                         "Net profit as a percentage of revenue over time.",
                         "medium")


def _g_cost_breakdown(ctx):
    present = []
    for field, label in (("cost_of_goods", "COGS"), ("shipping_cost", "Shipping"), ("marketing_spend", "Marketing")):
        if _usable(_delivered(ctx.df), field, "measure"):
            total = float(_delivered(ctx.df)[field].sum(min_count=1))
            if not pd.isna(total) and total > 0:
                present.append({"name": label, "value": round(total, 2), "field": field})
    if not present:
        return _none("No usable cost fields (COGS, shipping, marketing) were detected.")
    data = [{"name": r["name"], "value": r["value"]} for r in present]
    return ("AVAILABLE", _chart_spec(
        "cost_breakdown", "donut", "financial", "Cost Breakdown",
        "Total costs by category. Only cost categories that actually exist in the data are shown.",
        "high", _VALUE_FORMAT_CURRENCY, tuple(r["field"] for r in present), (),
        "name", [{"key": "value", "label": "Cost"}], data,
        [r["field"] for r in present], sort="value_desc",
    ), None)


# ------------------------------ PRODUCT -------------------------------------

def _ranking_spec(ctx, cid, title, description, category, priority, value_format,
                  dim_field, measure_field, label, kpi_label=None, count_orders=False):
    rows = _dim_measure_ranking(
        ctx.df, dim_field,
        None if count_orders else measure_field,
        delivered_only=True, limit=ctx.top_n,
    )
    if not rows:
        return _insufficient("No usable categories were found for this breakdown.")
    if len(rows) < 2:
        return _insufficient("Only a single category is present; the chart would not provide a useful comparison.")
    data = []
    for r in rows:
        row = {label: r["label"], measure_field or "value": _round_by_format(r["value"], value_format)}
        data.append(row)
    series_key = measure_field or "value"
    series_label = "Orders" if count_orders else (kpi_label or series_key)
    return ("AVAILABLE", _chart_spec(
        cid, "bar", category, title, description,
        priority, value_format, (dim_field,) + ((measure_field,) if measure_field else ()),
        () if count_orders else (),
        label, [{"key": series_key, "label": series_label}], data,
        [dim_field] + ([measure_field] if measure_field else []),
        sort="value_desc", limit=ctx.top_n,
    ), None)


def _g_product_revenue(ctx):
    product = _product_field(ctx.df)
    if product is None or not _usable(ctx.df, "revenue", "measure"):
        return _none("Product Revenue needs product and revenue data.")
    return _ranking_spec(ctx, "product_revenue", "Revenue by Product",
                         "Revenue generated by each product.",
                         "product", "high", _VALUE_FORMAT_CURRENCY,
                         product, "revenue", "product", "Revenue")


def _g_product_quantity(ctx):
    product = _product_field(ctx.df)
    if product is None or not _usable(ctx.df, "quantity", "measure"):
        return _none("Product Quantity needs product and quantity data.")
    return _ranking_spec(ctx, "product_quantity", "Quantity by Product",
                         "Units sold for each product.",
                         "product", "medium", _VALUE_FORMAT_COUNT,
                         product, "quantity", "product", "Units Sold")


def _g_category_revenue(ctx):
    if not _dim_available(ctx.df, "category") or not _usable(ctx.df, "revenue", "measure"):
        return _none("Category Revenue needs category and revenue data.")
    return _ranking_spec(ctx, "category_revenue", "Revenue by Category",
                         "Revenue generated by each product category.",
                         "product", "high", _VALUE_FORMAT_CURRENCY,
                         "category", "revenue", "category", "Revenue")


def _g_category_quantity(ctx):
    if not _dim_available(ctx.df, "category") or not _usable(ctx.df, "quantity", "measure"):
        return _none("Category Quantity needs category and quantity data.")
    return _ranking_spec(ctx, "category_quantity", "Quantity by Category",
                         "Units sold for each product category.",
                         "product", "low", _VALUE_FORMAT_COUNT,
                         "category", "quantity", "category", "Units Sold")


# ------------------------------ CUSTOMER ------------------------------------

def _g_customer_revenue(ctx):
    customer = _customer_field(ctx.df)
    if customer is None or not _usable(ctx.df, "revenue", "measure"):
        return _none("Customer Revenue needs customer and revenue data.")
    return _ranking_spec(ctx, "customer_revenue", "Revenue by Customer",
                         "Revenue attributed to each customer.",
                         "customer", "medium", _VALUE_FORMAT_CURRENCY,
                         customer, "revenue", "customer", "Revenue")


def _g_customer_orders(ctx):
    customer = _customer_field(ctx.df)
    order_field = _order_identifier(ctx.df)
    if customer is None or order_field is None:
        return _none("Customer Orders needs customer and an order identifier.")
    return _ranking_spec(ctx, "customer_orders", "Orders by Customer",
                         "Number of orders placed by each customer.",
                         "customer", "low", _VALUE_FORMAT_COUNT,
                         customer, None, "customer", "Orders", count_orders=True)


# ------------------------------ GEOGRAPHY -----------------------------------

def _g_country_revenue(ctx):
    if not _dim_available(ctx.df, "country") or not _usable(ctx.df, "revenue", "measure"):
        return _none("Revenue by Country needs country and revenue data.")
    return _ranking_spec(ctx, "country_revenue", "Revenue by Country",
                         "Revenue generated in each country.",
                         "geography", "high", _VALUE_FORMAT_CURRENCY,
                         "country", "revenue", "country", "Revenue")


def _g_region_revenue(ctx):
    if not _dim_available(ctx.df, "region") or not _usable(ctx.df, "revenue", "measure"):
        return _none("Revenue by Region needs region and revenue data.")
    return _ranking_spec(ctx, "region_revenue", "Revenue by Region",
                         "Revenue generated in each region.",
                         "geography", "medium", _VALUE_FORMAT_CURRENCY,
                         "region", "revenue", "region", "Revenue")


def _g_city_revenue(ctx):
    if not _dim_available(ctx.df, "city") or not _usable(ctx.df, "revenue", "measure"):
        return _none("Revenue by City needs city and revenue data.")
    return _ranking_spec(ctx, "city_revenue", "Revenue by City",
                         "Revenue generated in each city.",
                         "geography", "high", _VALUE_FORMAT_CURRENCY,
                         "city", "revenue", "city", "Revenue")


def _g_orders_by_city(ctx):
    order_field = _order_identifier(ctx.df)
    if not _dim_available(ctx.df, "city") or order_field is None:
        return _none("Orders by City needs city and an order identifier.")
    return _ranking_spec(ctx, "orders_by_city", "Orders by City",
                         "Number of delivered orders per city.",
                         "geography", "low", _VALUE_FORMAT_COUNT,
                         "city", None, "city", "Orders", count_orders=True)


# ------------------------------ OPERATIONS ----------------------------------

def _distribution_spec(ctx, cid, title, description, ctype, priority,
                       dim_field, measure_field, kpi_label, delivered_only=True):
    rows = _dim_measure_ranking(ctx.df, dim_field, measure_field,
                                delivered_only=delivered_only, limit=ctx.top_n)
    if not rows:
        return _insufficient("No usable categories were found for this distribution.")
    if len(rows) < 2:
        return _insufficient("Only a single category is present; the chart would not provide a useful comparison.")
    value_format = _VALUE_FORMAT_CURRENCY if measure_field else _VALUE_FORMAT_COUNT
    source = [dim_field] + ([measure_field] if measure_field else [])
    data = []
    for r in rows:
        data.append({"name": r["label"], "value": _round_by_format(r["value"], value_format)})
    return ("AVAILABLE", _chart_spec(
        cid, ctype, "operations", title, description, priority, value_format,
        (dim_field,) + ((measure_field,) if measure_field else ()), (),
        "name", [{"key": "value", "label": kpi_label}], data, source,
        sort="value_desc", limit=ctx.top_n,
    ), None)


def _g_payment_distribution(ctx):
    if not _dim_available(_delivered(ctx.df), "payment"):
        return _none("Payment distribution needs usable payment method data.")
    return _distribution_spec(ctx, "payment_distribution", "Orders by Payment Method",
                              "Share of orders by payment method.", "pie", "medium",
                              "payment", None, "Orders", delivered_only=True)


def _g_payment_revenue(ctx):
    if not _dim_available(ctx.df, "payment") or not _usable(ctx.df, "revenue", "measure"):
        return _none("Revenue by Payment Method needs payment and revenue data.")
    return _distribution_spec(ctx, "payment_revenue", "Revenue by Payment Method",
                              "Revenue attributed to each payment method.", "bar", "low",
                              "payment", "revenue", "Revenue", delivered_only=True)


def _g_channel_distribution(ctx):
    if not _dim_available(_delivered(ctx.df), "channel"):
        return _none("Channel distribution needs usable sales channel data.")
    return _distribution_spec(ctx, "channel_distribution", "Orders by Channel",
                              "Share of orders by sales channel.", "pie", "medium",
                              "channel", None, "Orders", delivered_only=True)


def _g_channel_revenue(ctx):
    if not _dim_available(ctx.df, "channel") or not _usable(ctx.df, "revenue", "measure"):
        return _none("Revenue by Channel needs channel and revenue data.")
    return _distribution_spec(ctx, "channel_revenue", "Revenue by Channel",
                              "Revenue attributed to each sales channel.", "bar", "low",
                              "channel", "revenue", "Revenue", delivered_only=True)


def _g_status_distribution(ctx):
    if not _dim_available(ctx.df, "status"):
        return _none("Order Status distribution needs usable order status data.")
    counts = ctx.df
    if counts is None or counts.empty:
        return _insufficient("No rows to distribute by status.")
    labels = _dim_series(counts, "status")
    tmp = counts.loc[labels.index].copy()
    tmp["_dim"] = labels.loc[labels.index].values
    grouped = tmp.groupby("_dim").size()
    if len(grouped) < 2:
        return _insufficient("Only a single order status is present; the chart would not provide a useful comparison.")
    rows = sorted(
        ({"name": str(k), "value": int(v)} for k, v in grouped.items()),
        key=lambda r: (-r["value"], r["name"]),
    )
    return ("AVAILABLE", _chart_spec(
        "status_distribution", "donut", "operations", "Order Status Distribution",
        "Share of all orders by status (including cancelled / returned).",
        "medium", _VALUE_FORMAT_COUNT, ("status",), (),
        "name", [{"key": "value", "label": "Orders"}], rows[: ctx.top_n],
        ["status"], sort="value_desc", limit=ctx.top_n,
    ), None)


# ===========================================================================
# 4. Registry assembly
# ===========================================================================

def _reg(cid, ctype, category, title, description, priority, value_format,
         requires_fields, requires_capabilities, requires_metrics, gen):
    return {
        "id": cid,
        "type": ctype,
        "category": category,
        "title": title,
        "description": description,
        "priority": priority,
        "value_format": value_format,
        "requires_fields": tuple(requires_fields),
        "requires_capabilities": tuple(requires_capabilities),
        "requires_metrics": tuple(requires_metrics),
        "generator": gen,
    }


CHART_REGISTRY = [
    # financial / time-series
    _reg("revenue_trend", "line", "financial", "Revenue Trend",
         "Revenue over time, grouped by period.", "high", _VALUE_FORMAT_CURRENCY,
         ("order_date", "revenue"), (), ("revenue",), _g_revenue_trend),
    _reg("orders_trend", "bar", "financial", "Orders Trend",
         "Number of delivered orders over time.", "high", _VALUE_FORMAT_COUNT,
         ("order_date",), ("order_analysis",), ("orders",), _g_orders_trend),
    _reg("gross_profit_trend", "line", "financial", "Gross Profit Trend",
         "Gross profit (revenue minus COGS) over time.", "high", _VALUE_FORMAT_CURRENCY,
         ("order_date", "revenue", "cost_of_goods"), ("gross_profit",), ("gross_profit",), _g_gross_profit_trend),
    _reg("net_profit_trend", "line", "financial", "Net Profit Trend",
         "Net profit (revenue minus COGS, shipping and marketing) over time.", "high", _VALUE_FORMAT_CURRENCY,
         ("order_date", "revenue", "cost_of_goods", "shipping_cost", "marketing_spend"),
         ("net_profit",), ("net_profit",), _g_net_profit_trend),
    _reg("gross_margin_trend", "line", "financial", "Gross Profit Margin Trend",
         "Gross profit as a percentage of revenue over time.", "medium", _VALUE_FORMAT_PERCENT,
         ("order_date", "revenue", "cost_of_goods"), ("gross_profit_margin",), ("gross_profit_margin",), _g_gross_margin_trend),
    _reg("net_margin_trend", "line", "financial", "Net Profit Margin Trend",
         "Net profit as a percentage of revenue over time.", "medium", _VALUE_FORMAT_PERCENT,
         ("order_date", "revenue", "cost_of_goods", "shipping_cost", "marketing_spend"),
         ("net_profit_margin",), ("net_profit_margin",), _g_net_margin_trend),
    _reg("cost_breakdown", "donut", "financial", "Cost Breakdown",
         "Total costs by category. Only cost categories that actually exist are shown.", "high", _VALUE_FORMAT_CURRENCY,
         (), (), (), _g_cost_breakdown),
    # product / category
    _reg("product_revenue", "bar", "product", "Revenue by Product",
         "Revenue generated by each product.", "high", _VALUE_FORMAT_CURRENCY,
         ("product_id", "revenue"), ("product_revenue",), ("revenue",), _g_product_revenue),
    _reg("product_quantity", "bar", "product", "Quantity by Product",
         "Units sold for each product.", "medium", _VALUE_FORMAT_COUNT,
         ("product_id", "quantity"), ("product_quantity",), ("quantity",), _g_product_quantity),
    _reg("category_revenue", "bar", "product", "Revenue by Category",
         "Revenue generated by each product category.", "high", _VALUE_FORMAT_CURRENCY,
         ("category", "revenue"), ("revenue_by_category",), ("revenue",), _g_category_revenue),
    _reg("category_quantity", "bar", "product", "Quantity by Category",
         "Units sold for each product category.", "low", _VALUE_FORMAT_COUNT,
         ("category", "quantity"), (), ("quantity",), _g_category_quantity),
    # customer
    _reg("customer_revenue", "bar", "customer", "Revenue by Customer",
         "Revenue attributed to each customer.", "medium", _VALUE_FORMAT_CURRENCY,
         ("customer_id", "revenue"), ("customer_revenue",), ("revenue",), _g_customer_revenue),
    _reg("customer_orders", "bar", "customer", "Orders by Customer",
         "Number of orders placed by each customer.", "low", _VALUE_FORMAT_COUNT,
         ("customer_id",), ("customer_orders",), ("orders",), _g_customer_orders),
    # geography
    _reg("country_revenue", "bar", "geography", "Revenue by Country",
         "Revenue generated in each country.", "high", _VALUE_FORMAT_CURRENCY,
         ("country", "revenue"), ("revenue_by_country",), ("revenue",), _g_country_revenue),
    _reg("region_revenue", "bar", "geography", "Revenue by Region",
         "Revenue generated in each region.", "medium", _VALUE_FORMAT_CURRENCY,
         ("region", "revenue"), ("revenue_by_region",), ("revenue",), _g_region_revenue),
    _reg("city_revenue", "bar", "geography", "Revenue by City",
         "Revenue generated in each city.", "high", _VALUE_FORMAT_CURRENCY,
         ("city", "revenue"), ("revenue_by_city",), ("revenue",), _g_city_revenue),
    _reg("orders_by_city", "bar", "geography", "Orders by City",
         "Number of delivered orders per city.", "low", _VALUE_FORMAT_COUNT,
         ("city",), (), ("orders",), _g_orders_by_city),
    # operations
    _reg("payment_distribution", "pie", "operations", "Orders by Payment Method",
         "Share of orders by payment method.", "medium", _VALUE_FORMAT_COUNT,
         ("payment",), ("payment_analysis",), (), _g_payment_distribution),
    _reg("payment_revenue", "bar", "operations", "Revenue by Payment Method",
         "Revenue attributed to each payment method.", "low", _VALUE_FORMAT_CURRENCY,
         ("payment", "revenue"), (), ("revenue",), _g_payment_revenue),
    _reg("channel_distribution", "pie", "operations", "Orders by Channel",
         "Share of orders by sales channel.", "medium", _VALUE_FORMAT_COUNT,
         ("channel",), ("sales_channel_analysis",), (), _g_channel_distribution),
    _reg("channel_revenue", "bar", "operations", "Revenue by Channel",
         "Revenue attributed to each sales channel.", "low", _VALUE_FORMAT_CURRENCY,
         ("channel", "revenue"), (), ("revenue",), _g_channel_revenue),
    _reg("status_distribution", "donut", "operations", "Order Status Distribution",
         "Share of all orders by status (including cancelled / returned).", "medium", _VALUE_FORMAT_COUNT,
         ("status",), ("order_status_analysis",), (), _g_status_distribution),
]


def _registry_by_id():
    return {entry["id"]: entry for entry in CHART_REGISTRY}


class _Context:
    """Bundle of inputs handed to every generator."""

    __slots__ = ("df", "mapping", "capability_map", "metric_values",
                 "metric_status", "profiler", "filters", "grouping", "top_n")

    def __init__(self, df, mapping, capability_map, metric_values, metric_status,
                 profiler, filters, grouping, top_n):
        self.df = df
        self.mapping = mapping
        self.capability_map = capability_map
        self.metric_values = metric_values
        self.metric_status = metric_status
        self.profiler = profiler
        self.filters = filters
        self.grouping = grouping
        self.top_n = top_n


def _normalize_grouping(grouping):
    if grouping in _GROUPINGS:
        return grouping
    return "monthly"


# ===========================================================================
# 5. Public API
# ===========================================================================

def generate_chart_specs(
    df,
    mapping=None,
    capability_map=None,
    metric_values=None,
    metric_status=None,
    profiler=None,
    filters=None,
    grouping="monthly",
    top_n=10,
):
    """
    Main entry point of the Dynamic Chart Engine.

    Returns a deterministic list of validated chart specification objects
    (AVAILABLE charts only) that the frontend renders without business logic.

    Args:
        df:                cleaned, standardized dataframe (standard-field names)
        mapping:           confirmed mapping dict {raw_col: standard_field} (optional)
        capability_map:    Phase 3 capability map (optional; the engine also
                           inspects the dataframe directly with the same thresholds)
        metric_values:     evaluate_metrics()['metric_values'] (optional)
        metric_status:     evaluate_metrics()['metric_status'] (optional)
        profiler:          Phase 1 profile output (optional)
        filters:           reserved for future filtered/grouped data passes
        grouping:          one of daily/weekly/monthly/quarterly/yearly
        top_n:             maximum categories in ranked / distribution charts
    """
    if df is None or len(df) == 0:
        return []
    ctx = _Context(df, mapping, capability_map, metric_values, metric_status,
                   profiler, filters, _normalize_grouping(grouping), top_n)
    specs = []
    for entry in CHART_REGISTRY:
        try:
            status, spec, _reason = entry["generator"](ctx)
        except Exception:
            # A chart failure must never destroy the analysis. Log-free: the
            # chart is simply omitted; generate_chart_specs stays total.
            continue
        if status == "AVAILABLE" and spec is not None:
            specs.append(spec)
    specs.sort(key=lambda s: (_PRIORITY_RANK.get(s["priority"], 2), s["id"]))
    return specs


def evaluate_chart_availability(
    df,
    mapping=None,
    capability_map=None,
    metric_values=None,
    metric_status=None,
    profiler=None,
    filters=None,
    grouping="monthly",
    top_n=10,
):
    """
    Returns the status of every registry chart: AVAILABLE, NOT_AVAILABLE or
    INSUFFICIENT_DATA, with a reason. Used by tests and diagnostics; the usable
    chart list (generate_chart_specs) only contains AVAILABLE charts.
    """
    if df is None or len(df) == 0:
        return [
            {"id": e["id"], "status": "NOT_AVAILABLE", "reason": "The dataframe is empty."}
            for e in CHART_REGISTRY
        ]
    ctx = _Context(df, mapping, capability_map, metric_values, metric_status,
                   profiler, filters, _normalize_grouping(grouping), top_n)
    out = []
    for entry in CHART_REGISTRY:
        try:
            status, _spec, reason = entry["generator"](ctx)
        except Exception as exc:  # pragmatic: never leak chart errors
            status, reason = "NOT_AVAILABLE", f"Chart generation failed: {exc.__class__.__name__}."
            reason = reason[:160]
        out.append({"id": entry["id"], "status": status, "reason": reason or None})
    return out


def summarize_chart_specs(specs):
    """Summary counts over generated chart specs (matches the API contract)."""
    categories = {}
    for spec in specs:
        categories[spec["category"]] = categories.get(spec["category"], 0) + 1
    return {
        "total": len(specs),
        "available": len(specs),
        "categories": dict(sorted(categories.items())),
    }