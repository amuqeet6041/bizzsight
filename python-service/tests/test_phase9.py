"""
Phase 9 - Financial correctness & filter-driven charts.

Regression tests for three Phase-8 bugs that had to be fixed such that the
backend stays the source of truth:

1. Revenue / Gross Profit / Net Profit calculations:
   - A mapped `Revenue` column is ALWAYS the canonical revenue; `Quantity x
     UnitPrice` is never added on top of it (no double counting).
   - When no revenue column is mapped, revenue is derived as
     SUM(Quantity x UnitPrice) - the single derived field in the pipeline.
   - Gross Profit = Revenue - COGS (no shipping below the line).
   - Net Profit = Revenue - COGS - Shipping - Marketing.
   - A missing expense field makes the dependent metric NOT_AVAILABLE (None),
     never an implicit zero.
   - Duplicate mappings to the same standard field are dropped deterministically
     (first column wins) instead of silently corrupting every metric.

2. Graphical Analysis filters / slicers:
   - /process accepts date_start/date_end/group_by/compare and returns
     windowed chart_specs plus chart_specs_previous.
   - The chart summary/counts always match the returned specs.

3. Revenue / Gross Profit / Net Profit trend charts:
   - Trend rows are driven by the backend window; weekly/monthly groupings
     produce the expected period labels.
   - Comparison specs are returned separately so the frontend can overlay them.

Run from the python-service directory:
    pytest -q tests/test_phase9.py
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.cleaning import clean_dataframe  # noqa: E402
from pipeline.metrics import evaluate_metrics  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

A_MAP = {
    "Date": "order_date",
    "OrderID": "order_id",
    "CustomerID": "customer_id",
    "Product": "product_id",
    "Quantity": "quantity",
    "Revenue": "revenue",
    "COGS": "cost_of_goods",
    "Shipping": "shipping_cost",
    "Marketing": "marketing_spend",
    "City": "city",
    "Country": "country",
    "Status": "status",
    "Payment": "payment",
    "Channel": "channel",
}

# ---------------------------------------------------------------------------
# 1. Revenue / Gross Profit / Net Profit
# ---------------------------------------------------------------------------


def _values(df, mapping):
    cleaned, report = clean_dataframe(df, mapping)
    return cleaned, report, evaluate_metrics(cleaned)


def test_revenue_is_sum_of_revenue_column_not_double_counted():
    """Revenue is SUM(canonical revenue field); Quantity x UnitPrice is NOT added on top."""
    df = pd.DataFrame({
        "Date": ["2026-01-03", "2026-01-10", "2026-01-17"],
        "OrderID": ["O1", "O2", "O3"],
        "Quantity": [2, 3, 1],
        "UnitPrice": [100, 100, 50],
        # qty*price = 550  !=  revenue sum = 600  -> double counting would yield 1150.
        "Revenue": [250, 300, 50],
        "Status": ["Delivered", "Delivered", "Delivered"],
    })
    mapping = {
        "Date": "order_date", "OrderID": "order_id", "Quantity": "quantity",
        "UnitPrice": "unit_price", "Revenue": "revenue", "Status": "status",
    }
    cleaned, _, mr = _values(df, mapping)
    assert cleaned["revenue"].sum() == 600
    assert mr["metric_values"]["revenue"] == 600
    assert mr["metric_values"]["orders"] == 3


def test_derived_revenue_quantity_times_unit_price():
    """With NO revenue column, revenue is derived as SUM(Quantity x UnitPrice)."""
    df = pd.DataFrame({
        "Date": ["2026-01-03", "2026-01-10", "2026-01-17"],
        "OrderID": ["O1", "O2", "O3"],
        "Quantity": [2, 3, 1],
        "UnitPrice": [100, 100, 50],
        "Status": ["Delivered", "Delivered", "Delivered"],
    })
    mapping = {
        "Date": "order_date", "OrderID": "order_id", "Quantity": "quantity",
        "UnitPrice": "unit_price", "Status": "status",
    }
    cleaned, report, mr = _values(df, mapping)
    assert report["revenue_derived_from"] == ["quantity", "unit_price"]
    assert "revenue" in cleaned.columns
    assert mr["metric_values"]["revenue"] == 550  # 2*100 + 3*100 + 1*50


def test_gross_profit_is_revenue_minus_cogs():
    df = pd.DataFrame({
        "Date": ["2026-01-03", "2026-01-10"],
        "OrderID": ["O1", "O2"],
        "Revenue": [250, 350],
        "COGS": [120, 180],
        "Status": ["Delivered", "Delivered"],
    })
    mapping = {
        "Date": "order_date", "OrderID": "order_id",
        "Revenue": "revenue", "COGS": "cost_of_goods", "Status": "status",
    }
    _, _, mr = _values(df, mapping)
    assert mr["metric_values"]["revenue"] == 600
    assert mr["metric_values"]["cogs"] == 300
    assert mr["metric_values"]["gross_profit"] == 300
    assert mr["metric_status"]["gross_profit"]["status"] == "AVAILABLE"


def test_net_profit_includes_every_expense_below_revenue():
    df = pd.DataFrame({
        "Date": ["2026-01-03", "2026-01-10"],
        "OrderID": ["O1", "O2"],
        "Revenue": [250, 350],
        "COGS": [120, 180],
        "Shipping": [30, 20],
        "Marketing": [20, 10],
        "Status": ["Delivered", "Delivered"],
    })
    mapping = {
        "Date": "order_date", "OrderID": "order_id", "Revenue": "revenue",
        "COGS": "cost_of_goods", "Shipping": "shipping_cost",
        "Marketing": "marketing_spend", "Status": "status",
    }
    _, _, mr = _values(df, mapping)
    assert mr["metric_values"]["gross_profit"] == 300
    # 600 - 300 - 50 - 30 = 220 (shipping and marketing are both BELOW gross).
    assert mr["metric_values"]["net_profit"] == 220


def test_net_profit_missing_shipping_is_never_zero():
    """Missing shipping expense must make Net Profit NOT_AVAILABLE, not 270."""
    df = pd.DataFrame({
        "Date": ["2026-01-03", "2026-01-10"],
        "OrderID": ["O1", "O2"],
        "Revenue": [250, 350],
        "COGS": [120, 180],
        "Marketing": [20, 10],
        "Status": ["Delivered", "Delivered"],
    })
    mapping = {
        "Date": "order_date", "OrderID": "order_id", "Revenue": "revenue",
        "COGS": "cost_of_goods", "Marketing": "marketing_spend", "Status": "status",
    }
    _, _, mr = _values(df, mapping)
    assert mr["metric_values"]["gross_profit"] == 300
    assert mr["metric_values"]["net_profit"] is None
    status = mr["metric_status"]["net_profit"]
    assert status["status"] == "NOT_AVAILABLE"
    assert "shipping" in status["reason"]


def test_duplicate_revenue_mapping_does_not_double_count():
    """Two columns mapped to 'revenue' are deduped (first wins), never summed."""
    df = pd.DataFrame({
        "Date": ["2026-01-03", "2026-01-10", "2026-01-17"],
        "OrderID": ["O1", "O2", "O3"],
        "Quantity": [2, 3, 1],
        "UnitPrice": [100, 100, 50],
        "Revenue": [250, 300, 50],
        "Status": ["Delivered", "Delivered", "Delivered"],
    })
    # UnitPrice is (incorrectly) mapped to revenue AND Revenue is mapped to revenue.
    mapping = {
        "Date": "order_date", "OrderID": "order_id", "Quantity": "quantity",
        "UnitPrice": "revenue", "Revenue": "revenue", "Status": "status",
    }
    cleaned, report, mr = _values(df, mapping)
    assert report["dropped_mapped_duplicates"] == 1
    # First-kept target column wins: UnitPrice column values [100, 100, 50].
    assert list(cleaned.columns).count("revenue") == 1
    assert mr["metric_values"]["revenue"] == 250


def test_mapping_suggests_unit_price_not_revenue_for_price_column():
    """UnitPrice must no longer auto-map to revenue (that caused double counting)."""
    from pipeline.mapping import suggest_column_mapping

    df = pd.DataFrame({
        "Date": ["2026-01-03"], "OrderID": ["O1"], "Quantity": [1],
        "UnitPrice": [100], "Revenue": [100],
    })
    suggestions = suggest_column_mapping(df.columns.tolist())
    assert suggestions["Revenue"][0] == "revenue"
    assert suggestions["UnitPrice"][0] == "unit_price"


# ---------------------------------------------------------------------------
# Validation bridge: role 'price' -> standard field 'unit_price'
# ---------------------------------------------------------------------------


def test_validation_bridges_price_to_unit_price():
    from pipeline.validation import role_to_standard

    assert role_to_standard("price") == "unit_price"
    assert role_to_standard("revenue") == "revenue"


# ---------------------------------------------------------------------------
# 2 & 3. Filter-driven chart specs + previous comparison specs
# ---------------------------------------------------------------------------


def _process(client, name, mapping, **extra):
    with open(FIXTURES / name, "rb") as fh:
        response = client.post(
            "/process",
            files={"file": (name, fh, "text/csv")},
            data={"mapping": json.dumps(mapping), **extra},
        )
    assert response.status_code == 200, response.text
    return response.json()


def test_process_default_unchanged_18_specs_no_filters():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    payload = _process(client, "cap_full_dataset.csv", A_MAP)
    specs = payload["chart_specs"]
    assert len(specs) == 18
    assert payload["chart_filters"]["applied"] is False
    assert isinstance(payload["chart_specs_previous"], list)
    assert payload["chart_specs_previous"] == []
    assert payload["chart_summary"]["total"] == len(specs)
    present = {s["id"] for s in specs}
    assert {"revenue_trend", "gross_profit_trend", "net_profit_trend"}.issubset(present)


def test_process_windowed_specs_and_weekly_grouping():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    payload = _process(
        client, "cap_full_dataset.csv", A_MAP,
        date_start="2026-02-01", date_end="2026-02-28",
        group_by="weekly",
    )
    assert payload["chart_filters"]["applied"] is True
    assert payload["chart_filters"]["group_by"] == "weekly"

    specs = payload["chart_specs"]
    assert payload["chart_summary"]["total"] == len(specs)
    revenue_trend = next((s for s in specs if s["id"] == "revenue_trend"), None)
    assert revenue_trend is not None
    periods = [d["period"] for d in revenue_trend["data"]]
    assert periods == ["2026-02-02", "2026-02-09", "2026-02-16"]

    # Every trend period row is backend-driven: revenue per week drops only when
    # no delivered rows exist for the week (never an invented 0).
    for row in revenue_trend["data"]:
        assert "revenue" in row


def test_process_previous_year_returns_separate_specs():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    payload = _process(
        client, "cap_full_dataset.csv", A_MAP,
        date_start="2026-01-01", date_end="2026-01-31",
        group_by="monthly", compare="previous_year",
    )
    assert payload["chart_filters"]["compare"] == "previous_year"
    # Dataset starts 2026-01-03; the previous year window is empty -> [].
    assert isinstance(payload["chart_specs_previous"], list)
    assert payload["chart_specs_previous"] == []
    assert payload["chart_summary"]["total"] == len(payload["chart_specs"])


def test_process_compare_none_does_not_compute_previous_specs():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    payload = _process(
        client, "cap_full_dataset.csv", A_MAP,
        date_start="2026-01-01", date_end="2026-01-31",
        group_by="monthly", compare="none",
    )
    assert payload["chart_specs_previous"] == []
    assert payload["chart_filters"]["compare"] == "none"


def test_net_profit_trend_missing_in_invoice_dataset():
    """Invoice-line data (revenue + cogs only) must never emit a net profit trend."""
    from fastapi.testclient import TestClient

    from main import app

    B_MAP = {
        "Date": "order_date",
        "InvoiceID": "invoice_id",
        "Product": "product_id",
        "Quantity": "quantity",
        "Revenue": "revenue",
        "COGS": "cost_of_goods",
    }
    client = TestClient(app)
    payload = _process(client, "cap_invoiceline.csv", B_MAP)
    ids = {s["id"] for s in payload["chart_specs"]}
    assert "net_profit_trend" not in ids
    assert "gross_profit_trend" in ids
    assert payload["metric_status"]["net_profit"]["status"] == "NOT_AVAILABLE"