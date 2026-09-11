"""
cleaning.py
Takes the raw uploaded dataframe + a user-confirmed column mapping,
and returns a cleaned, standardized dataframe plus a cleaning report.
"""

import pandas as pd
import numpy as np


def clean_dataframe(df, mapping):
    """
    df: raw uploaded dataframe
    mapping: dict {uploaded_col_name: standard_field}  (only confirmed mappings, no None values)

    Returns: (cleaned_df, report_dict)
    """
    report = {"rows_before": len(df)}

    # Resolve duplicate standard-field targets BEFORE renaming: each standard
    # field may be assigned to at most one uploaded column. Keeping the first
    # assignment (mapping dict order) prevents `pd.rename` from creating
    # duplicate columns that would silently corrupt every downstream metric.
    resolved_mapping = {}
    duplicated_targets = 0
    for raw_col, standard_field in mapping.items():
        if standard_field is None or standard_field == "":
            continue
        if standard_field in resolved_mapping.values():
            duplicated_targets += 1
            continue
        resolved_mapping[raw_col] = standard_field
    report["dropped_mapped_duplicates"] = duplicated_targets

    # Rename uploaded columns to standard names
    df = df.rename(columns=resolved_mapping)

    # Keep only columns we successfully mapped
    keep_cols = [c for c in resolved_mapping.values() if c in df.columns]
    df = df[keep_cols].copy()

    # Parse order_date
    if "order_date" in df.columns:
        parsed = pd.to_datetime(df["order_date"], errors="coerce")
        report["unparseable_dates"] = int(parsed.isna().sum())
        df["order_date"] = parsed

    # Clean numeric / currency columns (strip currency symbols, commas, etc.)
    numeric_cols = ["revenue", "unit_price", "cost_of_goods", "shipping_cost", "marketing_spend", "quantity"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[^\d.\-]", "", regex=True)
                .replace("", np.nan)
                .astype(float)
            )

    # Derive revenue from quantity × unit price when no revenue column exists.
    # This is the ONLY derived field in the pipeline: it is a pure product of
    # two confirmed line-item columns and never double-counts a real revenue
    # field (which always wins when present).
    if (
        "revenue" not in df.columns
        and "quantity" in df.columns
        and "unit_price" in df.columns
    ):
        df["revenue"] = df["quantity"] * df["unit_price"]
        report["revenue_derived_from"] = ["quantity", "unit_price"]

    # Drop duplicate orders (same order_id appearing more than once)
    if "order_id" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset="order_id")
        report["dropped_duplicate_rows"] = before - len(df)
    else:
        report["dropped_duplicate_rows"] = 0

    # Flag (not delete) revenue outliers using IQR method
    if "revenue" in df.columns and df["revenue"].notna().sum() > 3:
        q1, q3 = df["revenue"].quantile([0.25, 0.75])
        iqr = q3 - q1
        upper_bound = q3 + 3 * iqr
        df["is_outlier"] = df["revenue"] > upper_bound
    else:
        df["is_outlier"] = False

    report["rows_after"] = len(df)
    return df, report
