"""
metrics.py
Computes standard SME eCommerce business metrics from the cleaned dataframe,
and generates simple rule-based plain-English insights.
"""

import pandas as pd


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
