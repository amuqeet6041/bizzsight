"""
metrics.py
Computes standard SME eCommerce business metrics from the cleaned dataframe,
and generates simple rule-based plain-English insights.
"""

import pandas as pd


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


def compute_metrics(df):
    """
    Returns RAW numeric values (not display-formatted strings).
    Percentages are returned as fractions (0.222, not "22.2%") so Power BI
    can format them natively as percentages. Missing values are None.
    This dict is what gets exported to the "Metrics" sheet for Power BI.
    """
    if "status" in df.columns:
        cancelled_mask = (
            df["status"].astype(str).str.lower().str.contains("cancel|return|rto", na=False)
        )
    else:
        cancelled_mask = pd.Series([False] * len(df), index=df.index)

    delivered = df[~cancelled_mask]

    revenue = delivered["revenue"].sum() if "revenue" in delivered.columns else 0
    cogs = delivered["cost_of_goods"].sum() if "cost_of_goods" in delivered.columns else 0
    shipping = delivered["shipping_cost"].sum() if "shipping_cost" in delivered.columns else 0
    marketing = delivered["marketing_spend"].sum() if "marketing_spend" in delivered.columns else 0

    gross_profit = revenue - cogs - shipping
    net_profit = gross_profit - marketing

    num_orders = len(delivered)
    aov = revenue / num_orders if num_orders else 0

    cac = None
    repeat_rate = None
    if "customer_id" in delivered.columns:
        counts = delivered["customer_id"].value_counts()
        new_customers = int((counts == 1).sum())
        repeat_customers = int((counts > 1).sum())
        cac = marketing / new_customers if new_customers else None
        repeat_rate = repeat_customers / len(counts) if len(counts) else 0

    return_rate = cancelled_mask.sum() / len(df) if len(df) else 0

    metrics = {
        "Revenue": round(float(revenue), 2),
        "COGS": round(float(cogs), 2),
        "Shipping Cost": round(float(shipping), 2),
        "Marketing Spend": round(float(marketing), 2),
        "Gross Profit": round(float(gross_profit), 2),
        "Net Profit": round(float(net_profit), 2),
        "Orders": int(num_orders),
        "AOV": round(float(aov), 2),
        "CAC": round(float(cac), 2) if cac is not None else None,
        "Repeat Purchase Rate": round(float(repeat_rate), 4) if repeat_rate is not None else None,
        "Return/Cancel Rate": round(float(return_rate), 4),
    }
    return metrics


def format_metrics_for_display(metrics):
    """
    Converts the raw metrics dict into display-friendly strings,
    used only for showing the table inside the Streamlit app.
    """
    display = dict(metrics)
    if display["CAC"] is None:
        display["CAC"] = "N/A"
    if display["Repeat Purchase Rate"] is None:
        display["Repeat Purchase Rate"] = "N/A"
    else:
        display["Repeat Purchase Rate"] = f"{display['Repeat Purchase Rate']*100:.1f}%"
    display["Return/Cancel Rate"] = f"{display['Return/Cancel Rate']*100:.1f}%"
    return display


def generate_insights(metrics):
    """Expects the RAW metrics dict from compute_metrics (fractions, None for missing)."""
    insights = []

    if metrics["Net Profit"] < 0:
        insights.append("⚠️ Net profit is negative — total costs currently exceed revenue.")

    if metrics["CAC"] is not None and metrics["AOV"] > 0:
        if metrics["CAC"] > metrics["AOV"]:
            insights.append(
                "⚠️ Customer Acquisition Cost (CAC) is higher than Average Order Value (AOV) — "
                "acquiring new customers may currently be unprofitable on a per-order basis."
            )

    if metrics["Return/Cancel Rate"] > 0.15:
        insights.append(
            f"⚠️ Return/Cancel rate is {metrics['Return/Cancel Rate']*100:.1f}%, which is high "
            "for eCommerce — worth investigating product quality or delivery issues."
        )

    if not insights:
        insights.append("✅ No major red flags detected in the current data.")

    return insights

def generate_chart_data(df):
    """
    Generates time-series data for frontend charts.

    Returns:
        {
            "revenue_trend": [...],
            "profit_trend": [...],
            "orders_trend": [...]
        }

    Each item contains a date/month and the corresponding metric.
    """

    # If order_date doesn't exist, return empty chart data
    if "order_date" not in df.columns:
        return {
            "revenue_trend": [],
            "profit_trend": [],
            "orders_trend": [],
        }

    chart_df = df.copy()

    # Make sure dates are properly converted
    chart_df["order_date"] = pd.to_datetime(
        chart_df["order_date"],
        errors="coerce"
    )

    # Remove rows where date couldn't be understood
    chart_df = chart_df.dropna(subset=["order_date"])

    if chart_df.empty:
        return {
            "revenue_trend": [],
            "profit_trend": [],
            "orders_trend": [],
        }

    # Identify cancelled / returned / RTO orders
    if "status" in chart_df.columns:
        cancelled_mask = (
            chart_df["status"]
            .astype(str)
            .str.lower()
            .str.contains("cancel|return|rto", na=False)
        )
    else:
        cancelled_mask = pd.Series(
            [False] * len(chart_df),
            index=chart_df.index
        )

    # Only use delivered/non-cancelled orders for financial metrics
    delivered = chart_df[~cancelled_mask].copy()

    # Create monthly periods
    delivered["month"] = delivered["order_date"].dt.to_period("M")

    # Revenue
    revenue_trend = (
        delivered.groupby("month")["revenue"]
        .sum()
        .reset_index()
        if "revenue" in delivered.columns
        else pd.DataFrame(columns=["month", "revenue"])
    )

    # COGS
    cogs_trend = (
        delivered.groupby("month")["cost_of_goods"]
        .sum()
        .reset_index()
        if "cost_of_goods" in delivered.columns
        else pd.DataFrame(columns=["month", "cost_of_goods"])
    )

    # Shipping
    shipping_trend = (
        delivered.groupby("month")["shipping_cost"]
        .sum()
        .reset_index()
        if "shipping_cost" in delivered.columns
        else pd.DataFrame(columns=["month", "shipping_cost"])
    )

    # Marketing
    marketing_trend = (
        delivered.groupby("month")["marketing_spend"]
        .sum()
        .reset_index()
        if "marketing_spend" in delivered.columns
        else pd.DataFrame(columns=["month", "marketing_spend"])
    )

    # Orders
    orders_trend = (
        delivered.groupby("month")
        .size()
        .reset_index(name="orders")
    )

    # Combine all financial data
    trend = revenue_trend

    for extra_df in [
        cogs_trend,
        shipping_trend,
        marketing_trend,
    ]:
        trend = trend.merge(
            extra_df,
            on="month",
            how="outer"
        )

    # Fill missing values with zero
    numeric_columns = [
        "revenue",
        "cost_of_goods",
        "shipping_cost",
        "marketing_spend",
    ]

    for column in numeric_columns:
        if column in trend.columns:
            trend[column] = trend[column].fillna(0)

    # Calculate profits
    trend["gross_profit"] = (
        trend["revenue"]
        - trend["cost_of_goods"]
        - trend["shipping_cost"]
    )

    trend["net_profit"] = (
        trend["gross_profit"]
        - trend["marketing_spend"]
    )

    # Convert month to readable string
    trend["month"] = trend["month"].astype(str)

    # Sort chronologically
    trend = trend.sort_values("month")

    # Convert orders to a dictionary for easy frontend use
    orders_dict = {
        row["month"]: int(row["orders"])
        for _, row in orders_trend.iterrows()
    }

    # Build revenue/profit chart data
    revenue_profit_data = []

    for _, row in trend.iterrows():
        revenue_profit_data.append({
            "month": row["month"],
            "revenue": round(float(row["revenue"]), 2),
            "cogs": round(float(row["cost_of_goods"]), 2),
            "shipping": round(float(row["shipping_cost"]), 2),
            "marketing": round(float(row["marketing_spend"]), 2),
            "gross_profit": round(float(row["gross_profit"]), 2),
            "net_profit": round(float(row["net_profit"]), 2),
            "orders": orders_dict.get(row["month"], 0),
        })

    return {
        "revenue_trend": revenue_profit_data,
        "profit_trend": revenue_profit_data,
        "orders_trend": [
            {
                "month": month,
                "orders": orders
            }
            for month, orders in orders_dict.items()
        ],
    }


def generate_daily_timeline(df):
    """
    Returns one row per calendar day of delivered/non-cancelled orders, so the
    frontend can filter/aggregate by arbitrary date ranges client-side.

    Each row: {date, revenue, cogs, shipping, marketing, gross_profit,
    net_profit, orders, cancelled}.
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

    def col_sum(rows, name):
        return rows[name].sum() if name in rows.columns else 0

    delivered_by_date = {date: rows for date, rows in delivered.groupby("date")}

    rows = []
    for date in ordered_dates:
        day_rows = delivered_by_date.get(date, pd.DataFrame())
        revenue = col_sum(day_rows, "revenue")
        cogs = col_sum(day_rows, "cost_of_goods")
        shipping = col_sum(day_rows, "shipping_cost")
        marketing = col_sum(day_rows, "marketing_spend")
        gross_profit = revenue - cogs - shipping
        net_profit = gross_profit - marketing

        rows.append({
            "date": date,
            "revenue": round(float(revenue), 2),
            "cogs": round(float(cogs), 2),
            "shipping": round(float(shipping), 2),
            "marketing": round(float(marketing), 2),
            "gross_profit": round(float(gross_profit), 2),
            "net_profit": round(float(net_profit), 2),
            "orders": int(delivered_counts.get(date, 0)),
            "cancelled": int(cancelled_counts.get(date, 0)),
        })

    return rows


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

    if "customer_id" not in df.columns:
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

    if "product_id" not in df.columns:
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