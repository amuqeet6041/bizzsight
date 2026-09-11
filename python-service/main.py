"""
main.py — FastAPI microservice that wraps the tested mapping/cleaning/metrics
pipeline and exposes it over HTTP for the Next.js app to call.

Run with: uvicorn main:app --reload --port 8000
"""

import io
import base64

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from pipeline.mapping import suggest_column_mapping, STANDARD_FIELDS
from pipeline.cleaning import clean_dataframe
from pipeline.metrics import (
    compute_metrics,
    format_metrics_for_display,
    generate_insights,
    generate_chart_data,
    generate_daily_timeline,
    compute_customer_data,
    compute_product_data,
)
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
    metrics = compute_metrics(cleaned_df)
    display_metrics = format_metrics_for_display(metrics)
    insights = generate_insights(metrics)
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

    fields_present = {
        "has_date": "order_date" in cleaned_df.columns,
        "has_customer": "customer_id" in cleaned_df.columns,
        "has_product": "product_id" in cleaned_df.columns,
        "has_quantity": "quantity" in cleaned_df.columns,
        "has_status": "status" in cleaned_df.columns,
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
        "display_metrics": display_metrics,
        "insights": insights,
        "excel_file_base64": excel_base64,
        "chart_data": chart_data,
        "daily_timeline": daily_timeline,
        "customer_data": customer_data,
        "product_data": product_data,
        "date_range": date_range,
        "fields_present": fields_present,
    }
