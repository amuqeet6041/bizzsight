"""
insights.py  —  PHASE 5: Dynamic Business Insight Engine.

Refactors the flat, hand-written insight strings from Phase 4 into a
structured, rule-based engine. The engine decides which insights are allowed by
following the same chain as the Capability Engine and the metric engine:

    DATA AVAILABLE
        -> CAPABILITY AVAILABLE
        -> METRIC AVAILABLE
        -> INSIGHT ALLOWED

If a required capability or metric is unavailable, the corresponding insight
is NOT generated. The engine NEVER invents values for missing data, never says
"Net Profit = Gross Profit", and never treats one absent column as zero.

Insight objects are dictionaries:

    {
      "type": "financial" | "customer" | "product" | "geography" |
              "operations" | "time" | "data_quality",
      "priority": "high" | "medium" | "low",
      "title": "Gross Profit Margin is 42.3%",
      "message": "Within this dataset, Gross Profit Margin was 42.3% of revenue.",
      "metric": "gross_profit_margin",          # metric key, when relevant
      "value": 0.423,                            # machine-readable number
      "severity": "positive" | "negative" | "warning" | "neutral" | "informational"
    }

All numbers are calculated in Python. The LLM is never asked to compute facts
(this phase works with LLM_MODE=mock).

The engine is data-driven: it inspects the cleaned dataframe directly to
determine which dimensions (customer, product, city, country, region, payment,
channel, category, status) and measures (revenue, COGS, quantity) are present,
and uses `metric_status` (from evaluate_metrics) to know which metrics are
AVAILABLE vs NOT_AVAILABLE. Time-series insights only fire when a usable date
exists. Comparison semantics are respected by NOT inventing previous-period
comparisons the server cannot know: the client performs previous period / year
comparisons on the daily timeline it already has.

Small datasets (fewer than 10 orders) are handled conservatively: claims are
phrased as "Within this dataset, ..." instead of absolute business statements.
"""

import pandas as pd

from pipeline.metrics import _cancelled_mask, _field_usable


# ===========================================================================
# 1. Common helpers
# ===========================================================================

def _is_available(metric_status, key):
    return bool((metric_status or {}).get(key, {}).get("status") == "AVAILABLE")


def _metric_value(metric_status, key):
    entry = (metric_status or {}).get(key, {})
    if entry.get("status") == "AVAILABLE":
        return entry.get("value")
    return None


def _make(type_, priority, title, message, severity="informational",
          metric=None, value=None):
    """Build one structured insight object."""
    return {
        "type": type_,
        "priority": priority,
        "title": title,
        "message": message,
        "metric": metric,
        "value": value,
        "severity": severity,
    }


def _usable_dimension_col(df, col):
    """True when a mapped dimension column is actually usable as a grouping."""
    if col not in df.columns:
        return False
    usable, _ = _field_usable(df[col], "dimension")
    return usable


def _money(v):
    return f"${v:,.2f}"


def _plural(n, singular, plural=None):
    return singular if n == 1 else (plural or singular + "s")


def _verb(n, singular, plural=None):
    return singular if n == 1 else (plural or singular)


def _join_list(items):
    """English conjunction join: 'a', 'b and c'."""
    items = list(items)
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _pct_fraction(v):
    return f"{v * 100:.1f}%"


def _pct_share(v):
    return f"{v * 100:.0f}%"


def _clean_dimension_series(df, col):
    """Non-null, non-blank dimension values (used for ranking/grouping)."""
    if col not in df.columns:
        return df[[]].loc[[]] if len(df) else pd.DataFrame({"x": []})["x"]
    series = df[col].astype("object").where(df[col].notna(), None)
    clean = df.loc[series.notna() & (df[col].astype(str).str.strip() != "")]
    return clean


def _delivered(df):
    """Non-cancelled rows of the cleaned dataframe."""
    cancelled = _cancelled_mask(df)
    return df[~cancelled]


def _has_any_data(df):
    return df is not None and len(df) > 0


# ===========================================================================
# 2. Financial insights (only when the metric is AVAILABLE)
# ===========================================================================

def _financial_insights(df, metric_status, is_small):
    ins = []
    prefix = "Within this dataset, " if is_small else ""

    revenue = _metric_value(metric_status, "revenue")
    orders = _metric_value(metric_status, "orders")
    aov = _metric_value(metric_status, "average_order_value")
    gross_profit = _metric_value(metric_status, "gross_profit")
    gross_margin = _metric_value(metric_status, "gross_profit_margin")
    net_profit = _metric_value(metric_status, "net_profit")
    net_margin = _metric_value(metric_status, "net_profit_margin")
    cogs = _metric_value(metric_status, "cogs")
    shipping = _metric_value(metric_status, "shipping")
    marketing = _metric_value(metric_status, "marketing")
    cac = _metric_value(metric_status, "customer_acquisition_cost")
    return_rate = _metric_value(metric_status, "return_cancel_rate")

    # --- revenue ------------------------------------------------------------
    if revenue is not None:
        ins.append(_make(
            "financial", "high",
            f"{prefix}Revenue reached {_money(revenue)}",
            f"{prefix}Total revenue was {_money(revenue)}.",
            "neutral", "revenue", revenue,
        ))

    if orders is not None:
        ins.append(_make(
            "financial", "medium",
            f"{prefix}{orders:,} orders recorded",
            f"{prefix}{orders:,} delivered orders were recorded.",
            "neutral", "orders", orders,
        ))

    if aov is not None:
        ins.append(_make(
            "financial", "medium",
            f"{prefix}Average order value is {aov:,.2f}",
            f"{prefix}Average order value (AOV) was {_money(aov)}.",
            "neutral", "average_order_value", aov,
        ))

    # --- gross profit -------------------------------------------------------
    if gross_profit is not None and gross_margin is not None:
        severity = "positive" if gross_margin >= 0.30 else (
            "negative" if gross_margin < 0.10 else "neutral")
        ins.append(_make(
            "financial", "high",
            f"{prefix}Gross profit is nominal" if gross_margin < 0.10 else
            f"{prefix}Gross profit margin is {gross_margin * 100:.1f}%",
            f"{prefix}Gross profit was {_pct_fraction(gross_margin)} of revenue "
            f"({_money(gross_profit)}).",
            severity, "gross_profit_margin", gross_margin,
        ))
    elif gross_profit is not None:
        severity = "positive" if gross_profit > 0 else "negative"
        ins.append(_make(
            "financial", "high",
            f"{prefix}Gross profit is {gross_profit:,.2f}",
            f"{prefix}Gross profit was {_money(gross_profit)}.",
            severity, "gross_profit", gross_profit,
        ))

    # --- net profit ---------------------------------------------------------
    if net_profit is not None and net_margin is not None:
        if net_profit < 0:
            ins.append(_make(
                "financial", "high",
                f"{prefix}Net profit is negative",
                f"{prefix}Net profit is negative ({_money(net_profit)}), indicating "
                "total costs exceed revenue.",
                "negative", "net_profit", net_profit,
            ))
        else:
            severity = "positive" if net_margin >= 0.10 else "neutral"
            ins.append(_make(
                "financial", "high",
                f"{prefix}Net profit is positive" if net_margin >= 0.10 else
                f"{prefix}Net profit margin is {net_margin * 100:.1f}%",
                f"{prefix}Net profit was {_pct_fraction(net_margin)} of revenue "
                f"({_money(net_profit)}).",
                severity, "net_profit_margin", net_margin,
            ))

    # --- cost proportions (only when revenue exists) ------------------------
    if revenue is not None and revenue > 0:
        if cogs is not None:
            ratio = cogs / revenue
            severity = "positive" if ratio < 0.50 else (
                "warning" if ratio > 0.80 else "neutral")
            ins.append(_make(
                "financial", "low",
                f"{prefix}COGS is {ratio * 100:.1f}% of revenue",
                f"{prefix}Cost of goods sold accounts for {_pct_fraction(ratio)} of revenue.",
                severity, "cogs", cogs,
            ))
        if shipping is not None:
            ratio = shipping / revenue
            severity = "warning" if ratio > 0.20 else "neutral"
            ins.append(_make(
                "financial", "low",
                f"{prefix}Shipping is {ratio * 100:.1f}% of revenue",
                f"{prefix}Shipping costs represent {_pct_fraction(ratio)} of revenue.",
                severity, "shipping", shipping,
            ))
        if marketing is not None:
            ratio = marketing / revenue
            severity = "warning" if ratio > 0.20 else "neutral"
            ins.append(_make(
                "financial", "low",
                f"{prefix}Marketing is {ratio * 100:.1f}% of revenue",
                f"{prefix}Marketing spend represents {_pct_fraction(ratio)} of revenue.",
                severity, "marketing", marketing,
            ))

    # --- CAC vs AOV ---------------------------------------------------------
    if cac is not None and aov is not None and aov > 0 and cac > aov:
        ins.append(_make(
            "financial", "high",
            f"{prefix}Customer acquisition cost exceeds order value",
            f"{prefix}Customer Acquisition Cost ({_money(cac)}) is higher than "
            f"Average Order Value ({_money(aov)}), so acquiring new customers "
            f"may be unprofitable on a per-order basis.",
            "warning", "customer_acquisition_cost", cac,
        ))

    # --- return / cancel rate ------------------------------------------------
    if return_rate is not None and return_rate > 0.15:
        ins.append(_make(
            "operations", "high",
            f"{prefix}Return or cancel rate is {return_rate * 100:.1f}%",
            f"{prefix}Return/Cancel rate is {_pct_fraction(return_rate)}, which is "
            "high for eCommerce and may indicate product quality or delivery issues.",
            "negative", "return_cancel_rate", return_rate,
        ))

    return ins


# ===========================================================================
# 3. Missing-data (data quality) insights
# ===========================================================================

def _missing_data_insights(df, metric_status, is_small):
    """Explains the most important unavailable metrics. Kept to a few, not a wall."""
    ins = []
    # Net profit warning only useful when revenue exists (otherwise the metric
    # is obviously impossible and the warning adds noise).
    if (_is_available(metric_status, "revenue")
            and not _is_available(metric_status, "net_profit")):
        entry = (metric_status or {}).get("net_profit", {})
        missing = entry.get("missing_requirements") or []
        lv = {
            "shipping_cost": "shipping expense",
            "marketing_spend": "marketing expense",
            "revenue": "revenue",
            "cost_of_goods": "cost of goods sold (COGS)",
        }
        labels = _join_list(lv.get(m, m.replace("_", " ")) for m in missing)
        if labels:
            ins.append(_make(
                "data_quality", "high",
                "Net profit is unavailable",
                f"Net Profit could not be calculated because {labels} data was not "
                "detected, so it is reported as unavailable rather than estimated.",
                "warning", "net_profit", None,
            ))

    # CAC warning only useful when marketing spend exists; otherwise it repeats
    # the net-profit explanation (marketing missing).
    if (_is_available(metric_status, "marketing")
            and not _is_available(metric_status, "customer_acquisition_cost")):
        entry = (metric_status or {}).get("customer_acquisition_cost", {})
        missing = entry.get("missing_requirements") or []
        lv = {
            "marketing_spend": "marketing expense",
            "customer_id": "customer identifier",
        }
        labels = _join_list(lv.get(m, m.replace("_", " ")) for m in missing)
        if labels:
            ins.append(_make(
                "data_quality", "medium",
                "Customer Acquisition Cost is unavailable",
                f"Customer Acquisition Cost could not be calculated because {labels} "
                "data was not detected.",
                "warning", "customer_acquisition_cost", None,
            ))

    return ins


# ===========================================================================
# 4. Customer insights
# ===========================================================================

def _customer_insights(df, metric_status, is_small):
    if not _usable_dimension_col(df, "customer_id"):
        return []

    ins = []
    prefix = "Within this dataset, " if is_small else ""
    delivered = _delivered(df)
    clean = _clean_dimension_series(delivered, "customer_id")
    if len(clean) < 2:
        return []

    counts = clean["customer_id"].astype(str).str.strip().value_counts()
    total_customers = int(counts.size)
    repeat_customers = int((counts > 1).sum())

    ins.append(_make(
        "customer", "medium",
        f"{prefix}{total_customers} unique customers",
        f"{prefix}The dataset contains {total_customers} unique customers.",
        "neutral", None, total_customers,
    ))

    if "revenue" in clean.columns and _is_available(metric_status, "revenue"):
        ranked = clean.groupby(clean["customer_id"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
        if not ranked.empty:
            top_cust = ranked.index[0]
            top_rev = float(ranked.iloc[0])
            total_rev = float(ranked.sum())
            share = (top_rev / total_rev) if total_rev > 0 else 0
            ins.append(_make(
                "customer", "high",
                f"{prefix}Top customer by revenue is {top_cust}",
                f"{prefix}Customer {top_cust} generated the highest revenue "
                f"({_money(top_rev)}, {_pct_fraction(share)} of total).",
                "informational", None, top_rev,
            ))

    top_orders = counts.iloc[0]
    top_cust_orders = counts.index[0]
    if top_orders > 1:
        ins.append(_make(
            "customer", "medium",
            f"{prefix}Top customer by order count",
            f"{prefix}Customer {top_cust_orders} placed the most orders ({top_orders}).",
            "informational", None, int(top_orders),
        ))

    if _is_available(metric_status, "repeat_purchase_rate"):
        rate = _metric_value(metric_status, "repeat_purchase_rate")
        if rate is not None:
            severity = "positive" if rate >= 0.30 else "neutral"
            ins.append(_make(
                "customer", "medium",
                f"{prefix}Repeat purchase rate is {rate * 100:.1f}%",
                f"{prefix}{_pct_fraction(rate)} of customers placed more than one order.",
                severity, "repeat_purchase_rate", rate,
            ))

    return ins


# ===========================================================================
# 5. Product insights
# ===========================================================================

def _product_insights(df, metric_status, is_small):
    if not _usable_dimension_col(df, "product_id"):
        return []

    ins = []
    prefix = "Within this dataset, " if is_small else ""
    delivered = _delivered(df)
    clean = _clean_dimension_series(delivered, "product_id")
    if clean.empty:
        return []

    if "revenue" in clean.columns and _is_available(metric_status, "revenue"):
        ranked = clean.groupby(clean["product_id"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
        if not ranked.empty:
            top_prod = ranked.index[0]
            top_rev = float(ranked.iloc[0])
            total_rev = float(ranked.sum())
            share = (top_rev / total_rev) if total_rev > 0 else 0
            ins.append(_make(
                "product", "high",
                f"{prefix}Top product by revenue is {top_prod}",
                f"{prefix}Product {top_prod} generated the highest revenue "
                f"({_money(top_rev)}, {_pct_fraction(share)} of total).",
                "informational", None, top_rev,
            ))

            if share > 0.50:
                ins.append(_make(
                    "product", "medium",
                    f"{prefix}Revenue is concentrated in one product",
                    f"{prefix}Revenue is concentrated: {top_prod} alone accounts for "
                    f"{_pct_fraction(share)} of total revenue.",
                    "warning", None, share,
                ))

    if "quantity" in clean.columns and _is_available(metric_status, "quantity"):
        q_ranked = clean.groupby(clean["product_id"].astype(str).str.strip())["quantity"].sum().sort_values(ascending=False)
        if not q_ranked.empty:
            top_qty = q_ranked.index[0]
            units = float(q_ranked.iloc[0])
            ins.append(_make(
                "product", "medium",
                f"{prefix}Top product by units sold is {top_qty}",
                f"{prefix}Product {top_qty} accounted for the most units sold "
                f"({units:,.0f}).",
                "informational", "quantity", units,
            ))

    return ins


# ===========================================================================
# 6. Geography insights (city / country / region)
# ===========================================================================

def _geography_insights(df, metric_status, is_small):
    ins = []
    prefix = "Within this dataset, " if is_small else ""
    revenue_ok = _is_available(metric_status, "revenue")
    delivered = _delivered(df)

    has_city = _usable_dimension_col(df, "city")
    has_country = _usable_dimension_col(df, "country")

    if not has_city and not has_country:
        return ins

    # city totals (order count + revenue) ----------------------------------
    city_orders = None
    city_revenue = None
    if has_city:
        clean = _clean_dimension_series(delivered, "city")
        if len(clean) >= 2:
            counts = clean["city"].astype(str).str.strip().value_counts()
            city_orders = counts.iloc[0]
            top_city_orders = counts.index[0]
            if revenue_ok and "revenue" in clean.columns:
                rev_ranked = clean.groupby(clean["city"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
                if not rev_ranked.empty:
                    city_revenue = float(rev_ranked.iloc[0])
                    top_city_rev = rev_ranked.index[0]
                    total_rev = float(rev_ranked.sum())
                    share = (city_revenue / total_rev) if total_rev > 0 else 0
                    ins.append(_make(
                        "geography", "high",
                        f"{prefix}Top city by revenue is {top_city_rev}",
                        f"{prefix}{top_city_rev} generated the highest revenue "
                        f"({_money(city_revenue)}, {_pct_fraction(share)} of total).",
                        "informational", None, city_revenue,
                    ))
            else:
                ins.append(_make(
                    "geography", "medium",
                    f"{prefix}Most active city is {top_city_orders}",
                    f"{prefix}{top_city_orders} has the most records "
                    f"({int(counts.iloc[0])}).",
                    "informational", None, int(city_orders),
                ))

    # country totals ---------------------------------------------------------
    if has_country and revenue_ok and "revenue" in delivered.columns:
        clean = _clean_dimension_series(delivered, "country")
        if len(clean) >= 2:
            rev_ranked = clean.groupby(clean["country"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
            if not rev_ranked.empty:
                top_country = rev_ranked.index[0]
                country_rev = float(rev_ranked.iloc[0])
                total_rev = float(rev_ranked.sum())
                share = (country_rev / total_rev) if total_rev > 0 else 0
                ins.append(_make(
                    "geography", "high",
                    f"{prefix}Top country by revenue is {top_country}",
                    f"{prefix}{top_country} generated the highest revenue "
                    f"({_money(country_rev)}, {_pct_fraction(share)} of total).",
                    "informational", None, country_rev,
                ))

    # hierarchical: country -> city -----------------------------------------
    if has_country and has_city and revenue_ok and "revenue" in delivered.columns:
        clean = _clean_dimension_series(delivered, "country")
        if len(clean) >= 2:
            rev_ranked = clean.groupby(clean["country"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
            if not rev_ranked.empty:
                top_country = rev_ranked.index[0]
                in_country = clean[clean["country"].astype(str).str.strip() == top_country]
                if "city" in in_country.columns:
                    city_ranked = in_country.groupby(in_country["city"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
                    if not city_ranked.empty:
                        strong_city = city_ranked.index[0]
                        ins.append(_make(
                        "geography", "high",
                        f"{prefix}Strongest market is {top_country}",
                        f"{prefix}{top_country} generated the highest revenue, "
                        f"with {strong_city} being its strongest city.",
                        "informational", None, None,
                    ))

    return ins


# ===========================================================================
# 7. Operations insights (payment method / channel / status)
# ===========================================================================

def _payment_insights(df, metric_status, is_small):
    if not _usable_dimension_col(df, "payment"):
        return []
    ins = []
    prefix = "Within this dataset, " if is_small else ""
    delivered = _delivered(df)
    clean = _clean_dimension_series(delivered, "payment")
    if clean.empty:
        return []

    counts = clean["payment"].astype(str).str.strip().value_counts()
    total_orders = int(counts.sum())
    top_payment = counts.index[0]
    share = (counts.iloc[0] / total_orders) if total_orders > 0 else 0

    ins.append(_make(
        "operations", "medium",
        f"{prefix}Most-used payment method is {top_payment}",
        f"{prefix}{top_payment} accounts for {_pct_share(share)} of orders.",
        "informational", None, int(counts.iloc[0]),
    ))

    if _is_available(metric_status, "revenue") and "revenue" in delivered.columns:
        rev_ranked = delivered.groupby(delivered["payment"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
        if not rev_ranked.empty:
            top_pmt = rev_ranked.index[0]
            top_rev = float(rev_ranked.iloc[0])
            total_rev = float(rev_ranked.sum())
            pmt_share = (top_rev / total_rev) if total_rev > 0 else 0
            ins.append(_make(
                "operations", "medium",
                f"{prefix}Top payment method by revenue is {top_pmt}",
                f"{prefix}{top_pmt} generated the highest revenue "
                f"({_money(top_rev)}, {_pct_fraction(pmt_share)} of total).",
                "informational", None, top_rev,
            ))

    return ins


def _channel_insights(df, metric_status, is_small):
    if not _usable_dimension_col(df, "channel"):
        return []
    ins = []
    prefix = "Within this dataset, " if is_small else ""
    delivered = _delivered(df)
    clean = _clean_dimension_series(delivered, "channel")
    if clean.empty:
        return []

    counts = clean["channel"].astype(str).str.strip().value_counts()
    total_orders = int(counts.sum())
    top_channel = counts.index[0]
    share = (counts.iloc[0] / total_orders) if total_orders > 0 else 0

    ins.append(_make(
        "operations", "medium",
        f"{prefix}Top sales channel is {top_channel}",
        f"{prefix}{top_channel} is the most-used sales channel "
        f"({_pct_share(share)} of orders).",
        "informational", None, int(counts.iloc[0]),
    ))

    if _is_available(metric_status, "revenue") and "revenue" in delivered.columns:
        rev_ranked = delivered.groupby(delivered["channel"].astype(str).str.strip())["revenue"].sum().sort_values(ascending=False)
        if not rev_ranked.empty:
            top_ch = rev_ranked.index[0]
            top_rev = float(rev_ranked.iloc[0])
            total_rev = float(rev_ranked.sum())
            ch_share = (top_rev / total_rev) if total_rev > 0 else 0
            ins.append(_make(
                "operations", "medium",
                f"{prefix}Best-performing channel is {top_ch}",
                f"{prefix}{top_ch} generated the highest revenue among detected "
                f"sales channels ({_money(top_rev)}, {_pct_fraction(ch_share)} of total).",
                "informational", None, top_rev,
            ))

    return ins


def _status_insights(df, metric_status, is_small):
    if "status" not in df.columns or len(df) == 0:
        return []
    ins = []
    prefix = "Within this dataset, " if is_small else ""
    total = len(df)
    cancelled = _cancelled_mask(df)
    delivered_count = int((~cancelled).sum())
    cancelled_count = int(cancelled.sum())

    delivered_rate = delivered_count / total

    if cancelled_count > 0:
        ins.append(_make(
            "operations", "high" if delivered_rate < 0.80 else "medium",
            f"{prefix}Fulfillment rate is {delivered_rate * 100:.1f}%",
            f"{prefix}{delivered_count:,} of {total:,} {_plural(total, 'order')} "
            f"{_verb(delivered_count, 'was', 'were')} delivered or fulfilled "
            f"({_pct_fraction(delivered_rate)}).",
            "warning" if delivered_rate < 0.80 else "neutral",
            None, delivered_rate,
        ))

    if cancelled_count > 0 and total > 0:
        ins.append(_make(
            "operations", "medium",
            f"{prefix}{cancelled_count:,} {_plural(cancelled_count, 'order')} cancelled "
            f"or returned",
            f"{prefix}{cancelled_count:,} {_plural(cancelled_count, 'order')} "
            f"({_pct_fraction(cancelled_count / total)}) "
            f"{_verb(cancelled_count, 'was', 'were')} cancelled or returned.",
            "warning", "return_cancel_rate", cancelled_count / total,
        ))

    return ins


# ===========================================================================
# 8. Time-series insights (date + measure required)
# ===========================================================================

_MONTH_LABELS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def _month_label(month_key):
    year, month = (month_key.split("-") + ["01"])[:2]
    return f"{_MONTH_LABELS.get(month, month)} {year}"


def _time_insights(df, daily_timeline, metric_status, is_small):
    if "order_date" not in df.columns or not daily_timeline:
        return []
    if not _is_available(metric_status, "revenue"):
        return []

    ins = []
    prefix = "Within this dataset, " if is_small else ""

    monthly = {}
    for row in daily_timeline:
        revenue = row.get("revenue")
        if revenue is None or revenue == 0:
            continue
        month_key = row["date"][:7]
        monthly.setdefault(month_key, 0.0)
        monthly[month_key] += float(revenue)

    if len(monthly) < 2:
        return []

    sorted_months = sorted(monthly.keys())
    best = max(sorted_months, key=lambda m: monthly[m])
    worst = min(sorted_months, key=lambda m: monthly[m])
    if best == worst:
        return []

    ins.append(_make(
        "time", "high",
        f"{prefix}Strongest period is {_month_label(best)}",
        f"{prefix}{_month_label(best)} had the highest revenue "
        f"({_money(monthly[best])}).",
        "positive", None, monthly[best],
    ))

    ins.append(_make(
        "time", "medium",
        f"{prefix}Weakest period is {_month_label(worst)}",
        f"{prefix}{_month_label(worst)} had the lowest revenue "
        f"({_money(monthly[worst])}).",
        "neutral", None, monthly[worst],
    ))

    # overall trend direction (first half vs second half of the data)
    mid = len(sorted_months) // 2
    if mid and mid < len(sorted_months):
        first_half = sum(monthly[m] for m in sorted_months[:mid])
        second_half = sum(monthly[m] for m in sorted_months[mid:])
        if first_half > 0 and second_half > 0:
            growth = ((second_half - first_half) / first_half) * 100
            if abs(growth) >= 5:
                severity = "positive" if growth > 0 else "negative"
                direction = "increased" if growth > 0 else "decreased"
                ins.append(_make(
                    "time", "high" if abs(growth) >= 20 else "medium",
                    f"{prefix}Revenue has {direction} by {abs(growth):.1f}%",
                    f"{prefix}Revenue {direction} by {abs(growth):.1f}% from the "
                    "first half to the second half of the observed period.",
                    severity, None, growth / 100,
                ))

    return ins


# ===========================================================================
# 9. Deduplication, prioritization and top-N limiting
# ===========================================================================

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _deduplicate(insights):
    """Drop insights that restate the same observation under a different title."""
    seen = set()
    out = []
    for ins in insights:
        key = (ins["type"], ins.get("metric"), ins.get("title", "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(ins)
    return out


def _sort_and_limit(insights, limit=12):
    """Priority order (high first), then severity, then cap the count."""
    order = insights[:]
    order.sort(key=lambda i: (
        _PRIORITY_RANK.get(i.get("priority", "low"), 2),
        i.get("title", "").lower(),
    ))
    return order[:limit]


# ===========================================================================
# 10. Public API
# ===========================================================================

def generate_structured_insights(
    df,
    metric_status,
    metrics=None,
    fields_present=None,
    customer_data=None,
    product_data=None,
    daily_timeline=None,
):
    """
    Main entry point of the Dynamic Insight Engine.

    Generates a list of structured insight objects based on what the data
    actually supports. Every generator is gated so that an insight is only
    produced when its DATA -> CAPABILITY -> METRIC chain is available.

    Args:
        df:              cleaned, standardized dataframe (standard-field columns)
        metric_status:   metric -> {status, value, missing_requirements, ...}
                         (the output of evaluate_metrics())
        metrics:         legacy display-key metrics dict (optional, used for
                         small-dataset detection)
        fields_present:  dict of has_* flags (optional; the engine also inspects
                         the dataframe directly)
        daily_timeline:  list of per-day records (optional; used for time-series)
    """
    if not _has_any_data(df):
        return []

    order_total = int((metrics or {}).get("Orders") or 0)
    if order_total <= 0 and df is not None and len(df) > 0:
        order_total = len(df)
    is_small = order_total < 10

    generators = [
        _financial_insights,
        _missing_data_insights,
        _customer_insights,
        _product_insights,
        _geography_insights,
        _payment_insights,
        _channel_insights,
        _status_insights,
    ]

    collected = []
    for gen in generators:
        collected.extend(gen(df, metric_status, is_small))

    collected.extend(_time_insights(df, daily_timeline or [], metric_status, is_small))

    collected = _deduplicate(collected)
    collected = _sort_and_limit(collected)
    return collected


def insights_summary(structured):
    """Summary counts over the structured insights (matches the API contract)."""
    total = len(structured)
    return {
        "total": total,
        "high_priority": sum(
            1 for i in structured if i.get("priority") == "high"),
        "positive": sum(
            1 for i in structured if i.get("severity") == "positive"),
        "negative": sum(
            1 for i in structured if i.get("severity") == "negative"),
        "warnings": sum(
            1 for i in structured if i.get("severity") == "warning"),
    }


def insights_as_strings(structured):
    """Flat string list for the legacy `insights` field the frontend consumes."""
    return [i.get("message") or i.get("title", "") for i in structured]