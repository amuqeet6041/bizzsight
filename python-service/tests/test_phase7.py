"""
Phase 7 - Business Advisor / AI Analysis Engine.

Tests the advisor pipeline (pipeline/advisor.py + prompt + mock provider):

- Fact pack construction: verified metrics, top entities, trends, capabilities,
  insight snapshot, business summary; NEVER raw rows, PII or unverified numbers.
- Data honesty: unavailable metrics are absent as facts (never invented, never
  zero, never "net == gross"), and become labelled data limitations.
- Datasets A-J: full, invoice-line, no-date, no-customer, no-product, small,
  missing-expenses, LLM failure, malformed response, hallucinated number.
- Validation: schema, enums, lengths, list caps, fact-ID whitelist.
- Hallucination guard: unsupported numeric tokens are rejected.
- Mock provider determinism and the /process endpoint integration with all
  legacy fields preserved.

Run from the python-service directory:
    pytest -q tests/test_phase7.py
"""

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

# Deterministic mock LLM for every test in this file.
os.environ.setdefault("LLM_MODE", "mock")
os.environ.pop("LLM_PROVIDER", None)
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("LLM_MODEL", None)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.advisor import (  # noqa: E402
    KNOWN_FACT_IDS,
    FACT_REVENUE,
    FACT_COGS,
    FACT_SHIPPING,
    FACT_MARKETING,
    FACT_GROSS_PROFIT,
    FACT_GROSS_MARGIN,
    FACT_NET_PROFIT,
    FACT_NET_MARGIN,
    FACT_ORDERS,
    FACT_AOV,
    FACT_TOP_PRODUCT,
    FACT_TOP_CUSTOMER,
    FACT_TOP_CITY,
    FACT_CUSTOMER_CONCENTRATION,
    FACT_REVENUE_TREND,
    FACT_REVENUE_GROWTH,
    FACT_ORDERS_TREND,
    FACT_ROW_COUNT,
    FACT_DATE_RANGE,
    FACT_PERIOD_COUNT,
    _hallucination_errors,
    _safe_entity_label,
    build_advisor_fact_pack,
    generate_business_advice,
    mock_advisor_response,
    validate_advisor_response,
)
from pipeline.charts import generate_chart_specs  # noqa: E402
from pipeline.cleaning import clean_dataframe  # noqa: E402
from pipeline.insights import generate_structured_insights  # noqa: E402
from pipeline.llm import MockLLMProvider  # noqa: E402
from pipeline.metrics import evaluate_metrics  # noqa: E402
from pipeline.prompts import (  # noqa: E402
    BUSINESS_ADVISOR_PROMPT_VERSION,
    BUSINESS_ADVISOR_SYSTEM_PROMPT,
    build_business_advisor_context,
)

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
C_MAP = {"Revenue": "revenue", "Product": "product_id", "Customer": "customer_id"}
D_MAP = {"Date": "order_date", "Revenue": "revenue", "City": "city", "Country": "country"}
E_MAP = {"Date": "order_date", "OrderID": "order_id", "CustomerID": "customer_id", "Revenue": "revenue"}
F_MAP = {"Date": "order_date", "OrderID": "order_id", "Revenue": "revenue", "Product": "product_id"}


def _load(name):
    return pd.read_csv(FIXTURES / name)


def _prepared(name, mapping):
    df, _ = clean_dataframe(_load(name), mapping)
    mr = evaluate_metrics(df)
    return df, mr


def _fact_pack(name, mapping):
    df, mr = _prepared(name, mapping)
    ins = generate_structured_insights(
        df, metric_status=mr["metric_status"], metrics=mr["metrics"]
    )
    specs = generate_chart_specs(
        df, mapping=mapping, metric_values=mr["metric_values"],
        metric_status=mr["metric_status"],
    )
    return build_advisor_fact_pack(
        df, mapping=mapping, metric_values=mr["metric_values"],
        metric_status=mr["metric_status"], structured_insights=ins,
        chart_specs=specs,
    )


def _facts_by_id(fact_pack):
    return {f["id"]: f for f in fact_pack["facts"]}


def _advisor(name, mapping, **kwargs):
    df, mr = _prepared(name, mapping)
    ins = generate_structured_insights(
        df, metric_status=mr["metric_status"], metrics=mr["metrics"]
    )
    specs = generate_chart_specs(
        df, mapping=mapping, metric_values=mr["metric_values"],
        metric_status=mr["metric_status"],
    )
    return generate_business_advice(
        df, mapping=mapping, metric_values=mr["metric_values"],
        metric_status=mr["metric_status"], structured_insights=ins,
        chart_specs=specs, **kwargs,
    )


def _used_fact_ids(advisor):
    used = set()
    for key in ("priorities", "opportunities", "risks", "observations"):
        for item in advisor.get(key) or []:
            used.update(item.get("fact_ids") or [])
    return used


def _string_leaves(obj):
    out = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_string_leaves(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_string_leaves(v))
    return out


def _dict_literal_leaves(obj, key):
    """All literal values for a specific dict key (deep, no recursion guard)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                out.append(v)
            out.extend(_dict_literal_leaves(v, key))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_dict_literal_leaves(v, key))
    return out


# ------------------------------ Fact pack -----------------------------------


def test_known_fact_ids_stable():
    required = {
        "FACT_REVENUE", "FACT_GROSS_MARGIN", "FACT_NET_PROFIT",
        "FACT_TOP_CITY", "FACT_REVENUE_GROWTH", "FACT_ORDERS",
        "FACT_CUSTOMER_CONCENTRATION", "FACT_DATE_RANGE",
    }
    assert required.issubset(KNOWN_FACT_IDS)


def test_fact_pack_verified_metrics_match_metric_values():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    df, mr = _prepared("cap_full_dataset.csv", A_MAP)
    facts = _facts_by_id(fp)
    assert facts[FACT_REVENUE]["value"] == mr["metric_values"]["revenue"]
    assert facts[FACT_GROSS_PROFIT]["value"] == mr["metric_values"]["gross_profit"]
    assert facts[FACT_NET_PROFIT]["value"] == mr["metric_values"]["net_profit"]
    assert facts[FACT_ORDERS]["value"] == mr["metric_values"]["orders"]
    assert facts[FACT_AOV]["value"] == mr["metric_values"]["average_order_value"]
    assert facts[FACT_GROSS_MARGIN]["value"] == mr["metric_values"]["gross_profit_margin"]
    assert facts[FACT_NET_MARGIN]["value"] == mr["metric_values"]["net_profit_margin"]
    high_level = fp["metrics"]
    assert any(m["key"] == FACT_REVENUE and m["value"] == mr["metric_values"]["revenue"]
               for m in high_level)


def test_fact_pack_contains_top_entities():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    facts = _facts_by_id(fp)
    assert FACT_TOP_PRODUCT in facts
    assert FACT_TOP_CUSTOMER in facts
    assert FACT_TOP_CITY in facts
    assert facts[FACT_TOP_CUSTOMER]["detail"]
    assert all(len(row["name"]) and row["revenue"] is not None
               for row in facts[FACT_TOP_CUSTOMER]["detail"])


def test_fact_pack_concentration_matches_revenue():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    facts = _facts_by_id(fp)
    if FACT_CUSTOMER_CONCENTRATION in facts:
        concentration = facts[FACT_CUSTOMER_CONCENTRATION]["value"]
        top = facts[FACT_TOP_CUSTOMER]["detail"][0]["revenue"]
        revenue = facts[FACT_REVENUE]["value"]
        assert concentration == pytest.approx(top / revenue, abs=1e-3)


def test_fact_pack_trends_match_chart_specs():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    df, mr = _prepared("cap_full_dataset.csv", A_MAP)
    specs = generate_chart_specs(
        df, mapping=A_MAP, metric_values=mr["metric_values"],
        metric_status=mr["metric_status"],
    )
    revenue_spec = next(s for s in specs if s["id"] == "revenue_trend")
    trend_fact = _facts_by_id(fp)[FACT_REVENUE_TREND]
    assert [(p["period"], p["revenue"])
            for p in revenue_spec["data"]] == [
        (p["period"], p["revenue"]) for p in trend_fact["detail"]
    ]


def test_fact_pack_business_summary_and_date_range():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    df, _ = _prepared("cap_full_dataset.csv", A_MAP)
    summary = fp["business_summary"]
    assert summary["row_count"] == len(df)
    assert summary["date_range"]["start"] <= summary["date_range"]["end"]
    assert FACT_DATE_RANGE in _facts_by_id(fp)
    assert FACT_ROW_COUNT in _facts_by_id(fp)


def test_fact_pack_no_raw_rows_and_no_pii():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    # Only bounded aggregations: top entities (products/customers/cities) and
    # trend series. Never a raw row dump.
    assert "rows" not in fp
    assert len(_dict_literal_leaves(fp["facts"], "detail")) <= 6
    # No email addresses anywhere in the pack.
    for text in _string_leaves(fp):
        assert "@" not in text
        # Dates/periods are not phone numbers: skip any string that already
        # contains an ISO date.
        if re.search(r"\d{4}-\d{2}-\d{2}", text):
            continue
        assert re.search(r"(?<!\w)\+?\d[\d\s().-]{6,}\d", text) is None


def test_fact_pack_insight_snapshot_is_bounded():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    assert len(fp["insight_snapshot"]) <= 6
    for item in fp["insight_snapshot"]:
        assert item["type"] != "missing_data"


def test_fact_pack_available_capabilities():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    assert isinstance(fp["business_summary"]["available_capabilities"], list)


def test_safe_entity_label_redacts_pii():
    assert _safe_entity_label("aisha@example.com") == "[redacted identifier]"
    assert _safe_entity_label("+1 202 555 0147") == "[redacted identifier]"
    assert _safe_entity_label("C-02") == "C-02"


# --------------------------- Data honesty (A/B/G) ---------------------------


def test_full_dataset_net_profit_fact_exists():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    facts = _facts_by_id(fp)
    assert FACT_NET_PROFIT in facts
    assert facts[FACT_NET_PROFIT]["value"] is not None


def test_invoice_net_profit_not_invented():
    fp = _fact_pack("cap_invoiceline.csv", B_MAP)
    facts = _facts_by_id(fp)
    assert FACT_GROSS_PROFIT in facts  # revenue and COGS verified
    assert FACT_NET_PROFIT not in facts  # expense fields missing -> never invented
    assert FACT_MARKETING not in facts
    assert FACT_ORDERS_TREND in facts
    assert FACT_NET_MARGIN not in facts
    assert all("shipping" in t.lower() and "detected" in t.lower()
               for t in fp["data_limitations"] if "shipping" in t.lower())


def test_invoice_advisor_never_mentions_net_profit():
    adv = _advisor("cap_invoiceline.csv", B_MAP)
    assert adv["status"] == "AVAILABLE"
    assert FACT_NET_PROFIT not in _used_fact_ids(adv)
    joined = " ".join(_string_leaves(adv)).lower()
    assert "net profit could not be assessed" in joined


def test_invoice_advisor_limits_present():
    adv = _advisor("cap_invoiceline.csv", B_MAP)
    limitation_text = " ".join(adv["data_limitations"]).lower()
    assert "shipping expense data was not detected" in limitation_text
    assert "marketing expense data was not detected" in limitation_text
    assert len(adv["data_limitations"]) <= 5


# ----------------------- Missing data (C, D, E, F) --------------------------


def test_nodate_no_trend_facts_and_advisor_available():
    fp = _fact_pack("cap_nodate.csv", C_MAP)
    facts = _facts_by_id(fp)
    assert FACT_REVENUE in facts
    assert FACT_REVENUE_TREND not in facts
    assert FACT_PERIOD_COUNT not in facts
    assert FACT_DATE_RANGE not in facts
    assert any("order date data was not detected" in t.lower()
               for t in fp["data_limitations"])
    adv = _advisor("cap_nodate.csv", C_MAP)
    assert adv["status"] == "AVAILABLE"


def test_geography_no_customer_analysis():
    fp = _fact_pack("cap_geography.csv", D_MAP)
    facts = _facts_by_id(fp)
    assert FACT_TOP_CUSTOMER not in facts
    assert FACT_CUSTOMER_CONCENTRATION not in facts
    assert any("customer data was not detected" in t.lower()
               for t in fp["data_limitations"])
    adv = _advisor("cap_geography.csv", D_MAP)
    assert adv["status"] == "AVAILABLE"
    assert FACT_TOP_CUSTOMER not in _used_fact_ids(adv)


def test_customers_no_product_analysis():
    fp = _fact_pack("cap_customers.csv", E_MAP)
    facts = _facts_by_id(fp)
    assert FACT_TOP_PRODUCT not in facts
    adv = _advisor("cap_customers.csv", E_MAP)
    assert adv["status"] == "AVAILABLE"
    assert FACT_TOP_PRODUCT not in _used_fact_ids(adv)


def test_small_dataset_cautious_language():
    fp = _fact_pack("cap5_small.csv", F_MAP)
    assert any("initial signals" in t.lower() for t in fp["data_limitations"])
    adv = _advisor("cap5_small.csv", F_MAP)
    assert adv["status"] == "AVAILABLE"
    assert any("initial signals" in t.lower() for t in adv["data_limitations"])


# --------------------------- Advisor contract -------------------------------


def test_advisor_contract_full():
    adv = _advisor("cap_full_dataset.csv", A_MAP)
    assert adv["status"] == "AVAILABLE"
    assert adv["prompt_version"] == BUSINESS_ADVISOR_PROMPT_VERSION
    assert isinstance(adv["summary"], str) and adv["summary"]
    assert adv["health"]["overall"] in (
        "positive", "mixed", "negative", "insufficient_data")
    assert adv["health"]["explanation"]
    for key in ("priorities", "opportunities", "risks", "observations"):
        assert isinstance(adv[key], list)
    assert isinstance(adv["data_limitations"], list)
    assert len(adv["data_limitations"]) <= 5
    # Every cited fact must exist in the verified fact pack.
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    present = set(f["id"] for f in fp["facts"])
    assert _used_fact_ids(adv) <= present


def test_advisor_priorities_grounded():
    adv = _advisor("cap_full_dataset.csv", A_MAP)
    assert 0 < len(adv["priorities"]) <= 6
    for p in adv["priorities"]:
        assert {"title", "action", "reason", "priority", "impact", "effort",
                "fact_ids"}.issubset(p.keys())
        assert p["priority"] in ("high", "medium", "low")
        assert p["impact"] in ("high", "medium", "low")
        assert p["effort"] in ("high", "medium", "low")
        assert p["fact_ids"]
        assert len(p["title"]) <= 500


# ------------------------- Determinism & prompt -----------------------------


def test_mock_provider_deterministic_advisor():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    provider = MockLLMProvider()
    context = build_business_advisor_context(fp)
    first = provider.complete(context["_system_prompt"], context["_user_prompt"], context=context)
    second = provider.complete(context["_system_prompt"], context["_user_prompt"], context=context)
    assert first == second
    data = json.loads(first)
    assert validate_advisor_response(data, fp) == []


def test_generate_business_advice_deterministic():
    adv1 = _advisor("cap_full_dataset.csv", A_MAP)
    adv2 = _advisor("cap_full_dataset.csv", A_MAP)
    assert adv1 == adv2


def test_advisor_has_no_identifiers():
    adv = _advisor("cap_full_dataset.csv", A_MAP)
    assert "request_id" not in adv
    for text in _string_leaves(adv):
        assert "@" not in text


def test_advisor_prompt_guards():
    prompt = BUSINESS_ADVISOR_SYSTEM_PROMPT
    assert "business-advisor" in BUSINESS_ADVISOR_PROMPT_VERSION
    assert "NEVER recalculate" in prompt
    assert "NEVER invent missing values" in prompt
    assert "Correlation is not causation" in prompt
    assert "health.overall" in prompt
    assert "FACT_" in prompt
    assert "valid JSON" in prompt
    assert "insufficient_data" in prompt


# ------------------------------ Validation ----------------------------------


def _valid_response():
    fp = _fact_pack("cap_full_dataset.csv", A_MAP)
    return mock_advisor_response(fp), fp


def test_validation_passes_valid_response():
    data, fp = _valid_response()
    assert validate_advisor_response(data, fp) == []


def test_validation_rejects_bad_overall():
    data, fp = _valid_response()
    data["health"]["overall"] = "amazing"
    assert validate_advisor_response(data, fp)


def test_validation_rejects_missing_summary():
    data, fp = _valid_response()
    del data["summary"]
    assert validate_advisor_response(data, fp)


def test_validation_rejects_unknown_fact_id():
    data, fp = _valid_response()
    data["observations"][0]["fact_ids"] = ["FACT_UNKNOWN"]
    assert validate_advisor_response(data, fp)


def test_validation_rejects_absent_fact_id():
    fp = _fact_pack("cap_invoiceline.csv", B_MAP)
    data = mock_advisor_response(fp)
    data["observations"][0]["fact_ids"] = [FACT_NET_PROFIT]
    assert validate_advisor_response(data, fp)


def test_validation_rejects_bad_priority_enum():
    data, fp = _valid_response()
    data["priorities"][0]["priority"] = "critical"
    assert validate_advisor_response(data, fp)


def test_validation_rejects_long_string():
    data, fp = _valid_response()
    data["summary"] = "x" * 2001
    assert validate_advisor_response(data, fp)


def test_validation_rejects_too_many_priorities():
    data, fp = _valid_response()
    data["priorities"] = [data["priorities"][0]] * 7
    assert validate_advisor_response(data, fp)


def test_validation_rejects_too_many_limitations():
    data, fp = _valid_response()
    data["data_limitations"] = ["lim"] * 6
    assert validate_advisor_response(data, fp)


# --------------------------- Hallucination guard ----------------------------


def test_hallucination_passes_verified_numbers():
    data, fp = _valid_response()
    assert _hallucination_errors(data, fp) == []


def test_hallucination_flags_invented_number():
    data, fp = _valid_response()
    data["summary"] = "Revenue was 999999.00 last quarter, quite a surprise."
    errors = _hallucination_errors(data, fp)
    assert errors and "999999" in errors[0]


def test_hallucination_allows_dates_and_listing():
    data, fp = _valid_response()
    date_text = fp["business_summary"]["date_range"]["end"]
    data["observations"][0]["message"] = (
        f"As of {date_text} orders totaled 11; top 3 products led sales.")
    assert _hallucination_errors(data, fp) == []


def test_hallucination_allows_logical_small_ints():
    data, fp = _valid_response()
    data["summary"] = "3 priorities and 2 opportunities are recommended for the 11 orders."
    assert _hallucination_errors(data, fp) == []


# --------------------------- Failure paths (H/I/J) --------------------------


class _FakeLLM:
    def __init__(self, payload=None, exc=None):
        self._payload = payload
        self._exc = exc

    def complete(self, system_prompt, user_prompt, context=None):
        if self._exc:
            raise self._exc
        if callable(self._payload):
            return self._payload(context["_fact_pack"])
        return self._payload


def _fake_advisor(**kwargs):
    return _advisor("cap_full_dataset.csv", A_MAP, provider=_FakeLLM(**kwargs))


def test_llm_failure_returns_unavailable():
    adv = _fake_advisor(exc=RuntimeError("api down"))
    assert adv == {
        "status": "UNAVAILABLE",
        "summary": None,
        "reason": "Business advisor is currently unavailable.",
    }


def test_llm_non_json_returns_unavailable():
    assert _fake_advisor(payload="this is not json")["status"] == "UNAVAILABLE"


def test_llm_malformed_schema_returns_unavailable():
    assert _fake_advisor(payload=json.dumps({"summary": "hi"}))["status"] == "UNAVAILABLE"


def test_llm_hallucinated_number_rejected():
    def fake(fact_pack):
        data = mock_advisor_response(fact_pack)
        data["summary"] = "Verified revenue was 999999.00 (a wildly unlikely figure)."
        return json.dumps(data)

    adv = _advisor("cap_full_dataset.csv", A_MAP, provider=_FakeLLM(payload=fake))
    assert adv["status"] == "UNAVAILABLE"


def test_llm_empty_response_returns_unavailable():
    assert _fake_advisor(payload="")["status"] == "UNAVAILABLE"


def test_generate_business_advice_never_raises():
    # Even a broken provider must not crash the caller.
    adv = _fake_advisor(exc=Exception("boom"))
    assert adv["status"] == "UNAVAILABLE"


# ------------------------------ /process ------------------------------------


def _process_payload(client, name, mapping):
    with open(FIXTURES / name, "rb") as fh:
        response = client.post(
            "/process",
            files={"file": (name, fh, "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
    assert response.status_code == 200, response.text
    return response.json()


def test_process_adds_advisor_and_keeps_legacy_fields():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    payload = _process_payload(client, "cap_full_dataset.csv", A_MAP)

    legacy_keys = {
        "cleaning_report", "cleaned_preview", "metrics", "metric_values",
        "metric_status", "metric_definitions", "display_metrics", "insights",
        "structured_insights", "insight_summary", "excel_file_base64",
        "chart_data", "daily_timeline", "customer_data", "product_data",
        "date_range", "fields_present", "chart_specs", "chart_summary",
    }
    assert legacy_keys.issubset(payload.keys())

    advisor = payload["advisor"]
    assert advisor["status"] == "AVAILABLE"
    assert advisor["summary"]
    assert advisor["health"]["overall"] in (
        "positive", "mixed", "negative", "insufficient_data")
    assert advisor["prompt_version"] == "business-advisor-v1"
    assert advisor["priorities"]
    present = {s["id"] for s in payload["chart_specs"]}
    assert "revenue_trend" in present


def test_process_invoice_advisor_safe():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    payload = _process_payload(client, "cap_invoiceline.csv", B_MAP)
    advisor = payload["advisor"]
    assert advisor["status"] == "AVAILABLE"
    assert FACT_NET_PROFIT not in _used_fact_ids(advisor)
    limitation_text = " ".join(advisor["data_limitations"]).lower()
    assert "shipping expense data was not detected" in limitation_text


def test_process_advisor_never_breaks_api(monkeypatch):
    from fastapi.testclient import TestClient

    from main import app

    def broken_advisor(df, **kwargs):
        return {"status": "UNAVAILABLE", "summary": None,
                "reason": "Business advisor is currently unavailable."}

    monkeypatch.setattr("main.generate_business_advice", broken_advisor)
    client = TestClient(app)
    payload = _process_payload(client, "cap_full_dataset.csv", A_MAP)
    assert payload["advisor"]["status"] == "UNAVAILABLE"
    # Everything else still works.
    assert payload["metric_values"]["revenue"] is not None
    assert payload["chart_summary"]["total"] == len(payload["chart_specs"])