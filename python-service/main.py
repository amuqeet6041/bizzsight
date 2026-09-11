"""
main.py — FastAPI microservice that wraps the tested mapping/cleaning/metrics
pipeline and exposes it over HTTP for the Next.js app to call.

Run with: uvicorn main:app --reload --port 8000
"""

import io
import base64

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pipeline.mapping import suggest_column_mapping, STANDARD_FIELDS
from pipeline.cleaning import clean_dataframe
from pipeline.profiler import profile_dataset, ProfileError
from pipeline.llm import LLMConfig, generate_semantic_mapping, LLMSemanticError
from pipeline.prompts import build_llm_context
from pipeline.validation import validate_and_map, MappingValidationError
from pipeline.capabilities import build_capability_map
from pipeline.metrics import (
    compute_metrics,
    format_metrics_for_display,
    generate_chart_data,
    generate_daily_timeline,
    compute_customer_data,
    compute_product_data,
    evaluate_metrics,
    METRIC_DEFINITIONS,
)
from pipeline.insights import (
    generate_structured_insights,
    insights_summary,
    insights_as_strings,
)
from pipeline.charts import (
    generate_chart_specs,
    summarize_chart_specs,
)
from pipeline.advisor import generate_business_advice
app = FastAPI(title="SME Insights Pipeline Service")

# Allow the Next.js dev server (and later, your deployed frontend) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your actual frontend URL before going to production
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_upload_to_df(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    return pd.read_excel(io.BytesIO(file_bytes))


def _safe_preview(df: pd.DataFrame, n: int = 20):
    """
    Converts a dataframe (which may contain datetime/NaT/NaN values) into a
    JSON-safe list of dicts for the API response. Handles datetime columns
    explicitly since fillna("") does not reliably clear NaT values.
    """
    preview_df = df.head(n).copy()
    for col in preview_df.columns:
        if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
            preview_df[col] = preview_df[col].dt.strftime("%Y-%m-%d")
    preview_df = preview_df.fillna("").astype(str)
    return preview_df.to_dict(orient="records")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/suggest-mapping")
async def suggest_mapping_endpoint(file: UploadFile = File(...)):
    """
    Takes an uploaded file, returns:
      - a preview of the first rows
      - the raw column names
      - suggested standard-field mapping for each column
      - the full list of standard fields (so the frontend can build dropdowns)
    """
    file_bytes = await file.read()
    df = _read_upload_to_df(file_bytes, file.filename)

    suggestions = suggest_column_mapping(df.columns.tolist())
    suggestions_json = {
        col: {"suggested_field": field, "confidence": score}
        for col, (field, score) in suggestions.items()
    }

    preview = _safe_preview(df, 10)

    return {
        "columns": df.columns.tolist(),
        "suggestions": suggestions_json,
        "standard_fields": STANDARD_FIELDS,
        "preview": preview,
    }


@app.post("/profile")
async def profile_endpoint(file: UploadFile = File(...), sheet_name: str = Form(None)):
    """
    Phase 1 Dataset Profiler.

    Accepts an uploaded CSV / XLSX / XLS file (optionally a specific Excel
    sheet via the 'sheet_name' form field) and returns a structured profile:
    workbook structure, column profiles, likely business fields, identifier
    and dimension candidates, data quality, date analysis, cross-sheet
    relationships, and a preliminary capability preview.

    This endpoint does NOT replace /process or /suggest-mapping; it is a
    pre-mapping analysis used by later phases (capability engine, dynamic
    metrics, insights, charts, advisor).
    """
    file_bytes = await file.read()
    try:
        return profile_dataset(file_bytes, filename=file.filename, sheet_name=sheet_name)
    except ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # unreadable Excel, unexpected dtype errors, etc.
        raise HTTPException(
            status_code=500,
            detail=f"Failed to profile the dataset: {exc}",
        ) from exc


def _ai_semantic_mapping(profile: dict) -> dict:
    """
    Shared Phase 2 pipeline: compact context -> LLM provider (or mock) ->
    Python validation. Returns the validated mapping dict. Raises
    LLMSemanticError / MappingValidationError on provider or contract failure.
    """
    config = LLMConfig()
    llm_context = build_llm_context(profile)
    llm_response = generate_semantic_mapping(llm_context, config=config)
    return validate_and_map(
        llm_response,
        profile,
        is_mock=config.is_mock or not config.is_configured,
    )


@app.post("/ai-suggest-mapping")
async def ai_suggest_mapping_endpoint(
    file: UploadFile = File(...),
    sheet_name: str = Form(None),
):
    """
    Phase 2 LLM-assisted semantic mapping.

    1. Profiles the uploaded file (Phase 1 profiler).
    2. Builds a compact, safe LLM context from the profile.
    3. Sends the context to the configured LLM provider (or mock).
    4. Validates the LLM response against profiler data.
    5. Returns the validated mapping with warnings, errors, and rejected entries.

    Does NOT touch /suggest-mapping or /process.
    """
    # 1. Profile
    file_bytes = await file.read()
    try:
        profile = profile_dataset(file_bytes, filename=file.filename, sheet_name=sheet_name)
    except ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to profile the dataset: {exc}",
        ) from exc

    # 2-4. LLM mapping + validation
    try:
        return _ai_semantic_mapping(profile)
    except LLMSemanticError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MappingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM mapping pipeline failed: {exc}",
        ) from exc


@app.post("/capabilities")
async def capabilities_endpoint(
    file: UploadFile = File(...),
    sheet_name: str = Form(None),
):
    """
    Phase 3 Capability Engine.

    1. Profiles the dataset (Phase 1 profiler).
    2. Runs the AI semantic mapping + validation pipeline (Phase 2; works in
       LLM_MODE=mock too, since capability determination is pure Python).
    3. Builds the capability map: exactly which analyses/metrics/dimensions can
       be SAFELY provided, based on data that actually exists and is usable.

    The engine NEVER calculates or reports a metric whose required data does
    not exist. This does NOT modify /process or any existing endpoint.
    """
    file_bytes = await file.read()
    try:
        profile = profile_dataset(file_bytes, filename=file.filename, sheet_name=sheet_name)
    except ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to profile the dataset: {exc}",
        ) from exc

    try:
        validated_mapping = _ai_semantic_mapping(profile)
    except LLMSemanticError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MappingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM mapping pipeline failed: {exc}",
        ) from exc

    try:
        capability_map = build_capability_map(profile, validated_mapping)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build the capability map: {exc}",
        ) from exc

    return capability_map


@app.post("/process")
async def process_endpoint(file: UploadFile = File(...), mapping: str = Form(...)):
    """
    Takes the uploaded file again plus the user-confirmed mapping (JSON string,
    e.g. '{"Order No": "order_id", "Grand Total": "revenue"}'), and returns:
      - the cleaning report
      - a preview of cleaned data
      - the metrics (raw + display-formatted)
      - auto-generated insights
      - a base64-encoded Excel file (Orders + Metrics sheets) for Power BI export
    """
    import json

    file_bytes = await file.read()
    df = _read_upload_to_df(file_bytes, file.filename)
    confirmed_mapping = json.loads(mapping)

    cleaned_df, report = clean_dataframe(df, confirmed_mapping)

    # Phase 4: capability-aware metrics. evaluate_metrics() decides, purely in
    # Python from the cleaned data, which metrics are AVAILABLE (value) versus
    # NOT_AVAILABLE (value None + reason). Missing data is never reported as 0.
    metric_result = evaluate_metrics(cleaned_df)
    metrics = metric_result["metrics"]
    metric_values = metric_result["metric_values"]
    metric_status = metric_result["metric_status"]

    display_metrics = format_metrics_for_display(metrics)
    chart_data = generate_chart_data(cleaned_df)

    daily_timeline = generate_daily_timeline(cleaned_df)
    customer_data = compute_customer_data(cleaned_df)
    product_data = compute_product_data(cleaned_df)

    date_range = {}
    if daily_timeline:
        date_range = {
            "min": daily_timeline[0]["date"],
            "max": daily_timeline[-1]["date"],
        }

    # Phase 5: dynamic structured business insights. Python computes every fact;
    # the LLM is not involved. `insights` remains a flat string list so the
    # existing frontend keeps working; `structured_insights` + `insight_summary`
    # add the structured objects the UI can consume later.
    structured_insights = generate_structured_insights(
        cleaned_df,
        metric_status=metric_status,
        metrics=metrics,
        daily_timeline=daily_timeline,
        customer_data=customer_data,
        product_data=product_data,
    )
    insights = insights_as_strings(structured_insights)
    insight_summary = insights_summary(structured_insights)

    # Phase 6: backend-driven Dynamic Chart Engine. The engine inspects the
    # cleaned dataframe, the confirmed mapping and the metric availability and
    # returns validated chart specifications. It never invents data. The legacy
    # `chart_data` field is preserved untouched so the current frontend keeps
    # working; `chart_specs` is the new, renderer-agnostic contract.
    chart_specs = generate_chart_specs(
        cleaned_df,
        mapping=confirmed_mapping,
        metric_values=metric_values,
        metric_status=metric_status,
    )
    chart_summary = summarize_chart_specs(chart_specs)

    # Phase 7: Business Advisor. Python builds a sanitized, verified fact pack
    # from the artifacts above; the LLM (or the deterministic mock provider)
    # interprets it only. Any failure degrades to {"status": "UNAVAILABLE", ...}
    # and never breaks /process.
    advisor = generate_business_advice(
        cleaned_df,
        mapping=confirmed_mapping,
        metric_values=metric_values,
        metric_status=metric_status,
        structured_insights=structured_insights,
        chart_specs=chart_specs,
    )

    fields_present = {
        "has_date": "order_date" in cleaned_df.columns,
        "has_customer": "customer_id" in cleaned_df.columns,
        "has_product": "product_id" in cleaned_df.columns,
        "has_quantity": "quantity" in cleaned_df.columns,
        "has_status": "status" in cleaned_df.columns,
        "has_city": "city" in cleaned_df.columns,
        "has_country": "country" in cleaned_df.columns,
        "has_region": "region" in cleaned_df.columns,
        "has_payment": "payment" in cleaned_df.columns,
        "has_channel": "channel" in cleaned_df.columns,
        "has_category": "category" in cleaned_df.columns,
    }

    # Build the same two-sheet Excel file as before, in-memory, for download
    metrics_wide_df = pd.DataFrame([metrics])
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        cleaned_df.to_excel(writer, sheet_name="Orders", index=False)
        metrics_wide_df.to_excel(writer, sheet_name="Metrics", index=False)
    excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode("utf-8")

    cleaned_preview = _safe_preview(cleaned_df, 20)

    return {
        "cleaning_report": report,
        "cleaned_preview": cleaned_preview,
        "metrics": metrics,
        "metric_values": metric_values,
        "metric_status": metric_status,
        "metric_definitions": METRIC_DEFINITIONS,
        "display_metrics": display_metrics,
        "insights": insights,
        "structured_insights": structured_insights,
        "insight_summary": insight_summary,
        "chart_specs": chart_specs,
        "chart_summary": chart_summary,
        "advisor": advisor,
        "excel_file_base64": excel_base64,
        "chart_data": chart_data,
        "daily_timeline": daily_timeline,
        "customer_data": customer_data,
        "product_data": product_data,
        "date_range": date_range,
        "fields_present": fields_present,
    }
