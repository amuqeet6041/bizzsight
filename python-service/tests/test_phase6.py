"""
Phase 6 - Dynamic Chart Engine.

Tests the backend-driven chart specification engine (pipeline/charts.py):

- Registry shape, uniqueness and metadata.
- Chart specification contract (id, type, title, description, category,
  x_key, series, data, priority, value_format, unit, requirements,
  source_fields).
- Deterministic, prioritised output with duplicate prevention.
- Data honesty: net profit charts require all expense fields, margins are
  derived from field sums, values are never zero-filled, single-category
  charts are omitted, empty / tiny / no-date datasets never crash.
- Backward compatibility of the /process response (all legacy fields kept and
  chart_specs added).

Run from the python-service directory:
    pytest -q tests/test_phase6.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.charts import (
    CHART_REGISTRY,
    evaluate_chart_availability,
    generate_chart_specs,
    summarize_chart_specs,
)
from pipeline.cleaning import clean_dataframe
from pipeline.metrics import evaluate_metrics

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
B_MAP = {
    "Date": "order_date",
    "InvoiceID": "invoice_id",
    "Product": "product_id",
    "Quantity": "quantity",
    "Revenue": "revenue",
    "COGS": "cost_of_goods",
}
C_MAP = {"Date": "order_date", "Revenue": "revenue", "City": "city", "Country": "country"}
D_MAP = {"Date": "order_date", "OrderID": "order_id", "CustomerID": "customer_id", "Revenue": "revenue"}
E_MAP = {"Revenue": "revenue", "Product": "product_id", "Customer": "customer_id"}
F_MAP = {
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
G_MAP = {"Product": "product_id", "COGS": "cost_of_goods"}
H_MAP = {"Date": "order_date", "OrderID": "order_id", "Revenue": "revenue", "Product": "product_id"}


def _load(name):
    return pd.read_csv(FIXTURES / name)


def _prepared(name, mapping):
    df, _report = clean_dataframe(_load(name), mapping)
    mr = evaluate_metrics(df)
    return df, mr


def _specs(name, mapping, **kwargs):
    df, mr = _prepared(name, mapping)
    return generate_chart_specs(
        df, mapping=kwargs.pop("mapping", mapping),
        metric_values=mr["metric_values"], metric_status=mr["metric_status"], **kwargs,
    )


def _by_id(specs):
    return {s["id"]: s for s in specs}


# ------------------------------- REGISTRY -----------------------------------


def test_registry_is_reasonable_size():
    assert len(CHART_REGISTRY) >= 20


def test_registry_ids_unique():
    ids = [e["id"] for e in CHART_REGISTRY]
    assert len(ids) == len(set(ids))


def test_registry_entries_have_full_metadata():
    allowed_types = {"line", "bar", "area", "pie", "donut", "composed"}
    allowed_priorities = {"high", "medium", "low"}
    for entry in CHART_REGISTRY:
        assert entry["id"] and not entry["id"].isspace()
        assert entry["type"] in allowed_types
        assert entry["category"]
        assert entry["title"]
        assert entry["description"]
        assert entry["priority"] in allowed_priorities
        assert callable(entry["generator"])
        assert isinstance(entry["requires_fields"], tuple)
        assert isinstance(entry["requires_capabilities"], tuple)
        assert isinstance(entry["requires_metrics"], tuple)


# ------------------------------- CONTRACT -----------------------------------


def test_spec_contract_on_full_dataset():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    assert specs
    required = {"id", "type", "title", "description", "category", "x_key",
                "series", "data", "priority", "value_format", "unit",
                "requirements", "source_fields"}
    for spec in specs:
        assert required.issubset(spec.keys()), spec["id"]
        assert isinstance(spec["data"], list) and spec["data"]
        assert isinstance(spec["series"], list) and spec["series"]
        for series in spec["series"]:
            assert series["key"] in spec["data"][0], (spec["id"], series)
        for row in spec["data"]:
            assert spec["x_key"] in row, (spec["id"], spec["x_key"], row)
            for key, value in row.items():
                if key == spec["x_key"]:
                    continue
                assert value is not None, (spec["id"], "zero-filling or empty values are not allowed")
                assert isinstance(value, (int, float))
        assert spec["unit"] == ("%" if spec["value_format"] == "percent" else "")


def test_specs_are_deterministic():
    a = _specs("cap_full_dataset.csv", A_MAP)
    b = _specs("cap_full_dataset.csv", A_MAP)
    assert [s["id"] for s in a] == [s["id"] for s in b]
    assert [len(s["data"]) for s in a] == [len(s["data"]) for s in b]


def test_specs_have_no_duplicate_ids():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    ids = [s["id"] for s in specs]
    assert len(ids) == len(set(ids))


def test_specs_sorted_by_priority_then_id():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    rank = {"high": 0, "medium": 1, "low": 2}
    keyed = [(rank[s["priority"]], s["id"]) for s in specs]
    assert keyed == sorted(keyed)


# ------------------------------ AVAILABILITY --------------------------------


def test_availability_model_statuses_are_valid():
    df, mr = _prepared("cap_full_dataset.csv", A_MAP)
    availability = evaluate_chart_availability(
        df, mapping=A_MAP, metric_values=mr["metric_values"], metric_status=mr["metric_status"],
    )
    assert availability
    assert len(availability) == len(CHART_REGISTRY)
    statuses = {entry["status"] for entry in availability}
    assert statuses <= {"AVAILABLE", "NOT_AVAILABLE", "INSUFFICIENT_DATA"}
    for entry in availability:
        if entry["status"] != "AVAILABLE":
            assert entry["reason"], entry["id"]


def test_availability_matches_generated_specs():
    df, mr = _prepared("cap_full_dataset.csv", A_MAP)
    availability = {a["id"]: a["status"] for a in evaluate_chart_availability(
        df, mapping=A_MAP, metric_values=mr["metric_values"], metric_status=mr["metric_status"])}
    specs = generate_chart_specs(df, mapping=A_MAP, metric_values=mr["metric_values"], metric_status=mr["metric_status"])
    assert set(specs_by_id(specs)) == {cid for cid, status in availability.items() if status == "AVAILABLE"}


def specs_by_id(specs):
    return {s["id"] for s in specs}


# ------------------------------ FULL DATASET --------------------------------


def test_full_dataset_coverage():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    ids = specs_by_id(specs)
    expected = {
        "revenue_trend", "orders_trend", "gross_profit_trend", "net_profit_trend",
        "gross_margin_trend", "net_margin_trend", "cost_breakdown",
        "product_revenue", "product_quantity",
        "customer_revenue", "customer_orders",
        "city_revenue", "orders_by_city",
        "payment_distribution", "payment_revenue",
        "channel_distribution", "channel_revenue",
        "status_distribution",
    }
    assert ids == expected
    # No category or region data: those charts must not appear (no fabrication).
    assert "category_revenue" not in ids
    assert "category_quantity" not in ids
    assert "region_revenue" not in ids
    # Single unique country -> INSUFFICIENT_DATA (concept valid, too thin).
    assert "country_revenue" not in ids


def test_full_dataset_trend_values_match_metrics():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    df, mr = _prepared("cap_full_dataset.csv", A_MAP)
    by_id = _by_id(specs)
    delivered = df[~df["status"].astype(str).str.lower().isin(["cancelled", "returned"])]

    revenue_total = sum(row["revenue"] for row in by_id["revenue_trend"]["data"])
    assert round(revenue_total, 2) == round(mr["metric_values"]["revenue"], 2)
    assert round(revenue_total, 2) == round(float(delivered["revenue"].sum()), 2)

    gross_total = sum(row["gross_profit"] for row in by_id["gross_profit_trend"]["data"])
    assert gross_total == pytest.approx(
        float(delivered["revenue"].sum() - delivered["cost_of_goods"].sum()), abs=0.01)

    net_total = sum(row["net_profit"] for row in by_id["net_profit_trend"]["data"])
    assert net_total == pytest.approx(
        float(delivered["revenue"].sum() - delivered["cost_of_goods"].sum()
              - delivered["shipping_cost"].sum() - delivered["marketing_spend"].sum()), abs=0.01)


def test_full_dataset_orders_trend_matches_orders_metric():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    df, mr = _prepared("cap_full_dataset.csv", A_MAP)
    assert sum(r["orders"] for r in _by_id(specs)["orders_trend"]["data"]) == mr["metric_values"]["orders"]
    delivered = df[~df["status"].astype(str).str.lower().isin(["cancelled", "returned"])]
    assert mr["metric_values"]["orders"] == delivered["order_id"].nunique()


def test_full_dataset_cost_breakdown_matches_actual_costs():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    df, _mr = _prepared("cap_full_dataset.csv", A_MAP)
    delivered = df[~df["status"].astype(str).str.lower().isin(["cancelled", "returned"])]
    slices = {r["name"]: r["value"] for r in _by_id(specs)["cost_breakdown"]["data"]}
    expected = {
        "COGS": float(delivered["cost_of_goods"].sum(min_count=1)),
        "Shipping": float(delivered["shipping_cost"].sum(min_count=1)),
        "Marketing": float(delivered["marketing_spend"].sum(min_count=1)),
    }
    for name, value in expected.items():
        assert abs(slices[name] - value) < 0.01
    assert set(slices) == set(expected)


def test_full_dataset_top_n_limit():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    for cid in ("product_revenue", "customer_revenue", "city_revenue", "customer_orders", "orders_by_city"):
        assert len(_by_id(specs)[cid]["data"]) <= 10, cid


def test_status_distribution_includes_cancelled():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    rows = {(r["name"]): r["value"] for r in _by_id(specs)["status_distribution"]["data"]}
    assert "Cancelled" in rows and rows["Cancelled"] >= 1


def test_full_generates_between_six_and_twenty_charts():
    specs = _specs("cap_full_dataset.csv", A_MAP)
    assert 6 <= len(specs) <= 20
    summary = summarize_chart_specs(specs)
    assert summary["total"] == len(specs)
    assert summary["available"] == len(specs)
    assert sum(summary["categories"].values()) == len(specs)
    assert list(summary["categories"]) == sorted(summary["categories"])


def test_weekly_grouping_produces_iso_week_labels():
    specs = _specs("cap_full_dataset.csv", A_MAP, grouping="weekly")
    assert "revenue_trend" in specs_by_id(specs)
    points = _by_id(specs)["revenue_trend"]["data"]
    for point in points:
        # ISO week label is the Monday of that week (YYYY-MM-DD, weekday()==0).
        monday = datetime.strptime(point["period"], "%Y-%m-%d")
        assert monday.weekday() == 0
        assert monday.year >= 2015


def test_top_n_cap_respected():
    specs = _specs("cap_full_dataset.csv", A_MAP, top_n=3)
    for spec in specs:
        if spec["type"] in ("pie", "donut"):
            assert len(spec["data"]) <= 3
        elif spec["x_key"] != "period":
            assert len(spec["data"]) <= 3, spec["id"]


# --------------------------- DATASET-SPECIFIC -------------------------------


def test_invoiceline_omits_net_profit_charts():
    specs = _specs("cap_invoiceline.csv", B_MAP)
    ids = specs_by_id(specs)
    assert "revenue_trend" in ids
    assert "orders_trend" in ids
    assert "gross_profit_trend" in ids
    assert "gross_margin_trend" in ids
    assert "product_revenue" in ids
    assert "product_quantity" in ids
    # Missing shipping / marketing: no expense data is never assumed zero.
    assert "net_profit_trend" not in ids
    assert "net_margin_trend" not in ids


def test_invoiceline_cost_breakdown_only_real_costs():
    specs = _specs("cap_invoiceline.csv", B_MAP)
    slices = {r["name"] for r in _by_id(specs)["cost_breakdown"]["data"]}
    assert slices == {"COGS"}


def test_geography_dataset_limited_charts():
    specs = _specs("cap_geography.csv", C_MAP)
    ids = specs_by_id(specs)
    assert "revenue_trend" in ids
    assert "city_revenue" in ids
    assert "country_revenue" in ids
    assert "product_revenue" not in ids
    assert "customer_revenue" not in ids
    assert "orders_trend" not in ids
    assert "net_profit_trend" not in ids


def test_no_date_dataset_has_no_time_charts():
    specs = _specs("cap_nodate.csv", E_MAP)
    ids = specs_by_id(specs)
    assert "revenue_trend" not in ids
    assert "orders_trend" not in ids
    assert "gross_profit_trend" not in ids
    assert "product_revenue" in ids
    assert "customer_revenue" in ids


def test_no_revenue_dataset_only_cost_breakdown():
    specs = _specs("cap5_norevenue.csv", G_MAP)
    ids = specs_by_id(specs)
    assert ids == {"cost_breakdown"}
    df, mr = _prepared("cap5_norevenue.csv", G_MAP)
    availability = evaluate_chart_availability(
        df, mapping=G_MAP, metric_values=mr["metric_values"], metric_status=mr["metric_status"])
    by_id = {a["id"]: a["status"] for a in availability}
    assert by_id["revenue_trend"] == "NOT_AVAILABLE"


def test_single_country_insufficient_not_available():
    specs = _specs("cap5_geosingle.csv", F_MAP)
    ids = specs_by_id(specs)
    assert "city_revenue" in ids
    df, mr = _prepared("cap5_geosingle.csv", F_MAP)
    availability = {a["id"]: a["status"] for a in evaluate_chart_availability(
        df, mapping=F_MAP, metric_values=mr["metric_values"], metric_status=mr["metric_status"])}
    assert availability["country_revenue"] == "INSUFFICIENT_DATA"
    assert availability["region_revenue"] == "NOT_AVAILABLE"
    assert availability["city_revenue"] == "AVAILABLE"
    assert "country_revenue" not in ids


def test_small_dataset_no_crash():
    specs = _specs("cap5_small.csv", H_MAP)
    assert specs
    ids = specs_by_id(specs)
    assert "revenue_trend" in ids
    assert "product_revenue" in ids
    assert "orders_trend" in ids
    assert all(s["data"] for s in specs)


def test_single_category_charts_are_omitted():
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "OrderID": ["1", "2", "3"],
        "Product": ["P", "P", "P"],
        "Country": ["UAE", "UAE", "UAE"],
        "Revenue": [10, 20, 30],
    })
    mapping = {"Date": "order_date", "OrderID": "order_id",
               "Product": "product_id", "Country": "country", "Revenue": "revenue"}
    df, _report = clean_dataframe(df, mapping)
    mr = evaluate_metrics(df)
    specs = generate_chart_specs(df, mapping=mapping, metric_values=mr["metric_values"], metric_status=mr["metric_status"])
    ids = specs_by_id(specs)
    assert "product_revenue" not in ids
    assert "country_revenue" not in ids
    assert "revenue_trend" in ids


# -------------------------------- EMPTY -------------------------------------


def test_empty_dataframe_returns_no_specs():
    df = pd.DataFrame()
    mr = evaluate_metrics(df)
    specs = generate_chart_specs(df, metric_values=mr["metric_values"], metric_status=mr["metric_status"])
    assert specs == []
    assert summarize_chart_specs(specs) == {"total": 0, "available": 0, "categories": {}}
    availability = evaluate_chart_availability(
        df, metric_values=mr["metric_values"], metric_status=mr["metric_status"])
    assert all(a["status"] == "NOT_AVAILABLE" for a in availability)


def test_none_dataframe_returns_no_specs():
    assert generate_chart_specs(None) == []


# --------------------------------- /process ---------------------------------


def test_process_endpoint_adds_chart_specs_and_keeps_legacy_fields():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    with open(FIXTURES / "cap_full_dataset.csv", "rb") as fh:
        response = client.post(
            "/process",
            files={"file": ("cap_full_dataset.csv", fh, "text/csv")},
            data={"mapping": json.dumps(A_MAP)},
        )
    assert response.status_code == 200, response.text
    payload = response.json()

    legacy_keys = {
        "cleaning_report", "cleaned_preview", "metrics", "metric_values",
        "metric_status", "metric_definitions", "display_metrics", "insights",
        "structured_insights", "insight_summary", "excel_file_base64",
        "chart_data", "daily_timeline", "customer_data", "product_data",
        "date_range", "fields_present",
    }
    assert legacy_keys.issubset(payload.keys())
    assert isinstance(payload["chart_data"], dict)

    chart_specs = payload["chart_specs"]
    assert isinstance(chart_specs, list) and len(chart_specs) >= 10
    ids = {s["id"] for s in chart_specs}
    assert "revenue_trend" in ids
    assert "status_distribution" in ids

    summary = payload["chart_summary"]
    assert summary["total"] == len(chart_specs)
    assert summary["available"] == len(chart_specs)

    re_summary = summarize_chart_specs(chart_specs)
    assert re_summary == summary