"""
profiler.py  —  PHASE 1 of the new BizSight architecture: the Dataset Profiler.

The profiler inspects an uploaded CSV / XLSX / XLS dataset BEFORE final semantic
mapping and reports what the dataset actually contains:

    - workbook structure (all sheets, sizes, empty areas, column names)
    - per-column profiles (type, nulls, uniques, duplicates, samples, ranges)
    - likely business-field candidates  (date, revenue, customer, product, ...)
    - identifier-like columns            (OrderID, SKU, CustomerID, ...)
    - categorical dimension candidates   (city, channel, status, ...)
    - dataset-level data quality summary
    - date range detection
    - cross-sheet key relationships (Excel only)
    - primary transaction-sheet candidate (Excel only)
    - a *preliminary* capability preview

Profiling is ANALYSIS ONLY. The source dataframe is never modified and no
values are ever invented (e.g. if marketing is not detected, the profiler says
so -- it does NOT assume marketing = 0).

This module is deliberately self-contained so later phases (LLM mapping,
capability engine, dynamic metrics/insights/charts, advisor) can be added
without rewriting the profiler.

Main entry point:
    profile_dataset(file_path_or_dataframe, filename=None, sheet_name=None)
"""

import io
import os
import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz


# ---------------------------------------------------------------------------
# 0. Error type (mapped to a clear HTTP 400 in main.py)
# ---------------------------------------------------------------------------

class ProfileError(Exception):
    """Raised when a dataset cannot be profiled (bad file, empty, no headers...)."""


# ---------------------------------------------------------------------------
# 1. Small shared helpers
# ---------------------------------------------------------------------------

def _json_safe(value):
    """Convert a pandas value into a plain JSON-serializable Python value."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        ts = pd.Timestamp(value)
        if ts.hour == 0 and ts.minute == 0 and ts.second == 0:
            return ts.strftime("%Y-%m-%d")
        return ts.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_name(name):
    """
    Normalise a raw column name for matching, e.g.:
        "AdSpend"       -> "ad spend"
        "Sale_Value"    -> "sale value"
        "Cust_Name"     -> "cust name"
        "Txn_Date"      -> "txn date"
    """
    text = str(name)
    # split camelCase ("AdSpend" -> "Ad Spend") before lowering
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _squash(name):
    """Remove spaces so 'ad spend' and 'adspend' compare equal."""
    return re.sub(r"\s+", "", _canonical_name(name))


def _name_similarity(name, alias):
    """0..1 similarity that also rewards camelCase/squashed forms."""
    canonical = _canonical_name(name)
    alias_canon = _canonical_name(alias)
    if not canonical or not alias_canon:
        return 0.0
    if canonical == alias_canon:
        return 1.0
    squashed = _squash(canonical)
    alias_squashed = _squash(alias_canon)
    if squashed == alias_squashed:
        return 1.0
    fuzzy = fuzz.token_sort_ratio(canonical, alias_canon)
    fuzzy_squashed = fuzz.ratio(squashed, alias_squashed)
    return max(fuzzy, fuzzy_squashed) / 100.0


# ---------------------------------------------------------------------------
# 2. Field-candidate alias table (exact + fuzzy matching, confidence scores)
# ---------------------------------------------------------------------------

FIELD_ALIASES = {
    "date": [
        "order date", "invoice date", "transaction date", "txn date", "delivery date",
        "ship date", "payment date", "created at", "created", "purchase date",
        "booked date", "date created", "date paid", "date", "timestamp", "datetime",
        "order_date", "invoicedate", "txndate", "transdate", "createdat", "datetime",
    ],
    "revenue": [
        "revenue", "sales", "sale amount", "order amount", "invoice amount",
        "invoice total", "total amount", "grand total", "net sales", "gross sales",
        "sale value", "amount", "total", "value", "gross revenue", "net revenue",
        "order total", "amount paid", "sales amount", "salevalue", "salesvalue",
        "grossamount", "netamount", "invoiceamount", "ordertotal", "amount due",
    ],
    "quantity": [
        "quantity", "qty", "units", "units sold", "unit count", "no of items",
        "items sold", "quantity sold", "item qty", "total qty", "pcs", "pieces",
        "item count", "product count",
    ],
    "price": [
        "price", "unit price", "selling price", "list price", "rate",
        "price per unit", "sale price", "item price", "unitprice", "selprice",
        "unit rate",
    ],
    "cost": [
        "cost", "unit cost", "purchase cost", "product cost", "cogs",
        "cost price", "total cost", "cost of goods", "cost of goods sold",
        "unitcost", "productcost", "cogs amount", "gross cost",
    ],
    "shipping": [
        "shipping", "delivery cost", "freight", "shipping fee", "shipping cost",
        "delivery fee", "courier fee", "shipping charge", "delivery charges",
        "delcost", "shippingcost", "freightcost", "shippingfees", "deliverycost",
        "courier fee", "shipping amount",
    ],
    "marketing": [
        "marketing", "advertising", "ad spend", "ads cost", "ad spend amount",
        "marketing spend", "adspend", "marketingcost", "ads", "adcost",
        "campaign spend", "meta ads cost", "google ads", "facebook ads",
        "marketing spend amount",
    ],
    "discount": [
        "discount", "discount amount", "coupon", "coupon discount", "discount value",
        "disc", "deal discount", "promo", "promo discount", "discountamount",
        "coupon amount", "discount applied",
    ],
    "tax": [
        "tax", "gst", "vat", "sales tax", "tax amount", "cgst", "sgst", "igst",
        "taxvalue", "taxamount", "tax exclusive", "tax inclusive",
    ],
    "profit": [
        "profit", "gross profit", "net profit", "margin", "gross margin",
        "net margin", "net income", "profitamount", "grossprofit", "netprofit",
        "operating profit",
    ],
    "customer": [
        "customer", "customer name", "customer id", "buyer", "buyer name",
        "cust name", "email", "phone", "customer email", "client", "customer_name",
        "cust", "customername", "cusname", "customer no", "customer number",
        "contact name", "mobile",
    ],
    "product": [
        "product", "product name", "item", "item name", "sku", "product id",
        "item sku", "variant", "title", "product title", "product code",
        "item code", "product_code", "itemcode", "articleno", "article no",
        "variant name",
    ],
    "category": [
        "category", "product category", "type", "item type", "product type",
        "group", "category name", "product group", "subcategory",
        "product category name",
    ],
    "city": ["city", "town", "ship city", "billing city", "delivery city"],
    "country": ["country", "country name", "ship country", "delivery country"],
    "region": [
        "region", "state", "province", "territory", "emirate", "state/region",
        "region state", "county",
    ],
    "order": [
        "order", "order id", "order no", "order number", "orderid", "orderno",
        "invoice", "invoice id", "invoice no", "invoice number", "invoiceno",
        "transaction id", "transaction", "transaction number", "txn id",
        "ref", "reference", "receipt no", "po number", "po", "order ref",
    ],
    "payment": [
        "payment method", "payment type", "payment mode", "payment", "pay method",
        "gateway", "payment gateway", "payment method name",
    ],
    "channel": [
        "channel", "sales channel", "source", "medium", "platform", "store",
        "channel name", "sales source",
    ],
    "status": [
        "status", "order status", "delivery status", "fulfillment status",
        "fulfilment status", "order state", "orderstatus", "order status name",
    ],
}

# Roles that should normally hold numeric values
NUMERIC_ROLES = {
    "revenue", "quantity", "price", "cost", "shipping",
    "marketing", "discount", "tax", "profit",
}

# Roles that normally hold categorical / label values
CATEGORY_ROLES = {
    "customer", "product", "category", "city", "country", "region",
    "payment", "channel", "status",
}


def _best_alias(name, role):
    """Return the best (alias, similarity) for a column name against a role."""
    best_alias, best_score = None, 0.0
    for alias in FIELD_ALIASES.get(role, []):
        score = _name_similarity(name, alias)
        if score > best_score:
            best_alias, best_score = alias, score
    return best_alias, best_score


def _candidate_roles(column_name, profile):
    """
    Return the most likely business role for one column (at most one role),
    with a 0..1 confidence score.

    Strategy:
      1. Score every role by name similarity.
      2. If any role matches EXACTLY (name == an alias), that role wins —
         the name already tells us what the column is.
      3. Otherwise the single best fuzzy match wins, but only if its score is
         strong enough AND the column's content agrees with the role.
    This keeps the output clean (no noisy secondary labels like 'City' also
    being labelled 'customer') while still recognising non-standard spellings
    such as Sale_Amt, ItemDesc, Txn_Date.
    """
    name = str(column_name)
    inferred = profile.get("inferred_type")

    scored = []
    best_score = 0.0
    for role in FIELD_ALIASES:
        score = _best_alias(name, role)[1]
        scored.append((role, score))
        best_score = max(best_score, score)

    if best_score < 0.55:
        return []

    # Exact / squash match (e.g. "ad spend" == "AdSpend") wins immediately.
    for role, score in scored:
        if score >= 0.97:
            return [_role_with_content(role, score, inferred)]

    # Fuzzy fallback: keep the single best match when it clears the bar.
    scored.sort(key=lambda item: item[1], reverse=True)
    role, score = scored[0]
    if score < 0.70:
        return []

    adjusted = _role_with_content(role, score, inferred)
    return [adjusted] if adjusted["confidence"] >= 0.50 else []


def _role_with_content(role, base_score, inferred):
    """Apply content-based confidence adjustments to a candidate role."""
    if role == "date":
        if inferred == "datetime":
            base_score = min(0.99, base_score + 0.12)
        elif inferred in ("integer", "text"):
            # possible date stored as a code or string
            base_score = base_score * 0.75
    elif role in NUMERIC_ROLES:
        if inferred in ("integer", "float"):
            base_score = min(0.99, base_score + 0.08)
        elif inferred == "text":
            # values could be currency strings like "$1,200"
            base_score = base_score * 0.70
        elif inferred in ("categorical", "boolean", "datetime"):
            base_score = base_score * 0.40
    elif role in CATEGORY_ROLES:
        if inferred in ("categorical", "text", "integer", "boolean"):
            base_score = min(0.99, base_score + 0.05)
        elif inferred in ("float", "datetime"):
            base_score = base_score * 0.45

    return {"role": role, "confidence": round(base_score, 2)}


# ---------------------------------------------------------------------------
# 3. Type inference (better than raw pandas dtypes)
# ---------------------------------------------------------------------------

def _clean_numeric(value):
    """
    Try to coerce a value into a float, handling real-world messy numerics:
        "$1,200.50" -> 1200.5, "USD 500" -> 500.0, "(50)" -> -50.0
    Returns np.nan when the value is not numeric. Profiling only - the source
    dataframe is never modified.
    """
    if value is None:
        return np.nan
    try:
        if pd.isna(value):
            return np.nan
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text = str(value).strip()
    if not text:
        return np.nan
    text = _unparenthesize_negative(text)
    # Dates ('7/3/2025'), times ('12:30') and words ('USD 500', 'Size-M') are
    # not numbers - leave them for the date/text inference stages.
    if re.search(r"[A-Za-z/:]", text):
        return np.nan
    text = text.replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if text in ("", ".", "-", "-.", "+"):
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def _unparenthesize_negative(text):
    """Turn accounting-style '(50)' into '-50'."""
    if text[0] == "(" and text[-1] == ")":
        return "-" + text[1:-1]
    return text


def _sample_is_numeric(values, frac_threshold=0.92):
    if not values:
        return None
    cleaned = pd.Series([_clean_numeric(v) for v in values])
    good = float(cleaned.notna().sum()) / len(values)
    if good < frac_threshold:
        return None
    return cleaned


def _is_all_integral(values):
    numeric = _sample_is_numeric(values)
    if numeric is None or len(numeric.dropna()) == 0:
        return False
    cleaned = numeric.dropna()
    return bool((cleaned % 1 == 0).all())


def _infer_column_type(series):
    """
    Value-based type inference. Possible results:
        empty | datetime | boolean | integer | float | categorical | text
    'identifier' is applied later in profile_dataset using identifier heuristics.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return "empty"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"

    # object / mixed columns -> inspect the actual values
    sample = non_null.head(60).tolist()

    # boolean-ish strings
    lowered = {str(v).strip().lower() for v in sample}
    if lowered and lowered.issubset({"true", "false", "yes", "no", "y", "n", "0", "1"}):
        return "boolean"

    # numbers stored as text (check BEFORE dates - pure numbers are not dates)
    numeric = _sample_is_numeric(sample)
    if numeric is not None:
        return "integer" if _is_all_integral(sample) else "float"

    # dates stored as text
    date_coerced = pd.to_datetime(
        pd.Series(sample), errors="coerce", format="mixed"
    )
    if len(sample) and float(date_coerced.notna().sum()) / len(sample) >= 0.92:
        return "datetime"

    # labels with repetition -> categorical, otherwise free text
    unique_ratio = float(non_null.nunique()) / len(non_null)
    if unique_ratio <= 0.5 and float(non_null.nunique()) >= 1:
        return "categorical"
    return "text"


# ---------------------------------------------------------------------------
# 4. Reading files / Excel workbooks
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _load_sheets(source, filename=None):
    """
    Return {'file_type': ..., 'sheets': [{'name': ..., 'raw': df, 'parse_headers': bool}]}
    where 'raw' is read with header=None so we can inspect structure freely.
    """
    if isinstance(source, pd.DataFrame):
        frame = source.copy()
        name = filename or "DataFrame"
        return {
            "file_type": "dataframe",
            "sheets": [{"name": name, "raw": _to_raw_frame(frame), "parse_headers": False}],
        }

    if isinstance(source, (bytes, bytearray)):
        if not filename:
            raise ProfileError("Reading raw bytes requires a filename so the file type can be detected.")
        return _load_from_bytes(bytes(source), filename)

    if isinstance(source, str):
        if not os.path.isfile(source):
            raise ProfileError(f"File not found: {source}")
        with open(source, "rb") as fh:
            file_bytes = fh.read()
        return _load_from_bytes(file_bytes, os.path.basename(source))

    raise ProfileError(f"Unsupported source type: {type(source).__name__}")


def _to_raw_frame(frame):
    """Convert a normal dataframe into the internal header=None-style frame,
    keeping the original column names for the parse_headers=False path."""
    df = frame.copy()
    df = df.reset_index(drop=True)
    # to_numpy() keeps datetime values in datetime64 columns; object columns
    # keep python values, which the profiler inspects value-by-value.
    return pd.DataFrame(
        df.to_numpy(),
        columns=[str(c) for c in df.columns],
        index=range(len(df)),
    )


def _load_from_bytes(file_bytes, filename):
    if len(file_bytes) == 0:
        raise ProfileError("The uploaded file is empty.")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ProfileError(
            f"Unsupported file type '{ext}'. Please upload a .csv, .xlsx, or .xls file."
        )

    if ext == ".csv":
        try:
            raw = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=object)
        except Exception as exc:
            raise ProfileError(f"Could not parse the CSV file: {exc}") from exc
        sheets = [{"name": _csv_sheet_name(filename), "raw": raw, "parse_headers": True}]
        return {"file_type": "csv", "sheets": sheets}

    # Excel: inspect EVERY sheet, not just the first one
    try:
        workbook = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None, dtype=object)
    except ImportError as exc:
        raise ProfileError(
            "Reading legacy .xls files is not supported in this environment "
            "(xlrd is not installed). Please convert the file to .xlsx or CSV."
        ) from exc
    except Exception as exc:
        raise ProfileError(f"Could not read the Excel workbook: {exc}") from exc

    if not workbook:
        raise ProfileError("The Excel workbook contains no sheets.")

    sheets = [
        {"name": sheet_name, "raw": frame, "parse_headers": True}
        for sheet_name, frame in workbook.items()
    ]
    return {"file_type": ext.lstrip("."), "sheets": sheets}


def _csv_sheet_name(filename):
    stem = os.path.splitext(os.path.basename(filename))[0].strip()
    return stem if stem else "CSV"


# ---------------------------------------------------------------------------
# 5. Sheet structure profiling
# ---------------------------------------------------------------------------

def _sheet_structure(sheet_name, raw):
    rows_used = int((~raw.isna().all(axis=1)).sum())
    raw_row_count = len(raw)
    empty_row_count = raw_row_count - rows_used

    columns_used = int(raw.notna().any(axis=0).sum())
    raw_column_count = len(raw.columns)
    empty_column_count = raw_column_count - columns_used

    is_empty = rows_used == 0 or columns_used == 0

    return {
        "sheet_name": sheet_name,
        "row_count": rows_used,
        "raw_row_count": raw_row_count,
        "empty_row_count": empty_row_count,
        "column_count": columns_used,
        "raw_column_count": raw_column_count,
        "empty_column_count": empty_column_count,
        "column_names": _best_effort_headers(raw),
        "is_empty": is_empty,
    }


def _best_effort_headers(raw):
    """Names from the first mostly-populated row; best effort, never relied on."""
    for _, row in raw.iterrows():
        labels = [_json_safe(v) for v in row.tolist()]
        present = [lbl for lbl in labels if lbl is not None and str(lbl).strip() != ""]
        if present and float(len(present)) / len(row) >= 0.5:
            return [str(lbl) for lbl in present[:20]]
    return []


def _header_frame(raw, sheet_name, parse_headers):
    """
    Build a working dataframe using the first data row as column headers.
    Raises ProfileError when headers are missing or the sheet has no rows.
    """
    if raw.empty:
        raise ProfileError(f"Sheet '{sheet_name}' has no data.")

    work = raw.dropna(how="all")
    if work.empty:
        raise ProfileError(f"Sheet '{sheet_name}' has no data (only empty rows).")

    if not parse_headers:
        # dataframe source already has headers
        data = work.reset_index(drop=True).copy()
        data.columns = _uniqueify([str(c) for c in data.columns])
        return data

    header_cells = work.iloc[0]
    labels = []
    for idx, value in enumerate(header_cells):
        text = "" if pd.isna(value) else str(value).strip()
        labels.append(text if text else f"Unnamed: {idx}")

    unnamed = sum(1 for lbl in labels if lbl.startswith("Unnamed:"))
    data_like = sum(1 for lbl in labels if _looks_like_data_header(lbl))
    if len(labels) and (
        float(unnamed) / len(labels) > 0.5
        or float(data_like) / len(labels) >= 0.5
    ):
        raise ProfileError(
            f"Sheet '{sheet_name}': column headers could not be detected "
            "(missing or empty header row)."
        )

    data = work.iloc[1:].reset_index(drop=True).copy()
    if data.empty:
        raise ProfileError(
            f"Sheet '{sheet_name}' contains column headers but no data rows."
        )

    data.columns = _uniqueify(labels)
    return data


def _uniqueify(labels):
    seen = {}
    result = []
    for lbl in labels:
        if lbl not in seen:
            seen[lbl] = 1
            result.append(lbl)
        else:
            seen[lbl] += 1
            result.append(f"{lbl}_{seen[lbl]}")
    return result


def _looks_like_data_header(label):
    """Feels like a data cell rather than a column name (used to detect missing headers)."""
    text = str(label).strip()
    if not text:
        return True
    if re.fullmatch(r"-?\d*\.?\d+", text):  # plain numbers
        return True
    if re.search(r"\b(19|20)\d{2}\b", text) and re.search(r"[-/]", text):  # dates
        return True
    if re.match(r"^\d{1,2}:\d{2}", text):  # times
        return True
    return False


# ---------------------------------------------------------------------------
# 6. Per-column profiling
# ---------------------------------------------------------------------------

def _profile_column(series, total_rows, max_sample_values):
    name = str(series.name)
    non_null = series.dropna()
    null_count = int(series.isna().sum())
    null_percentage = round(null_count / total_rows, 4) if total_rows else 0.0
    unique_count = int(non_null.nunique()) if len(non_null) else 0
    duplicate_count = max(len(non_null) - unique_count, 0)
    unique_ratio = round(
        unique_count / len(non_null), 4
    ) if len(non_null) else 0.0

    inferred_type = _infer_column_type(series)

    profile = {
        "name": name,
        "pandas_dtype": str(series.dtype),
        "inferred_type": inferred_type,
        "null_count": null_count,
        "null_percentage": null_percentage,
        "unique_count": unique_count,
        "unique_ratio": unique_ratio,
        "duplicate_count": duplicate_count,
        "sample_values": _sample_values(non_null, max_sample_values),
    }

    # numeric min/max
    if inferred_type in ("integer", "float"):
        numeric = pd.Series([_clean_numeric(v) for v in non_null.tolist()]).dropna()
        if len(numeric):
            profile["min"] = _round_number(numeric.min())
            profile["max"] = _round_number(numeric.max())

    # date min/max
    if inferred_type == "datetime":
        dates = pd.to_datetime(non_null, errors="coerce").dropna()
        if len(dates):
            profile["min_date"] = dates.min().strftime("%Y-%m-%d")
            profile["max_date"] = dates.max().strftime("%Y-%m-%d")

    return profile


def _sample_values(non_null, max_sample_values):
    out = []
    seen = set()
    for value in non_null.tolist():
        safe = _json_safe(value)
        key = str(safe)
        if key in seen:
            continue
        seen.add(key)
        out.append(safe)
        if len(out) >= max_sample_values:
            break
    return out


def _round_number(value):
    value = float(value)
    if value.is_integer():
        return int(value)
    return round(value, 4)


# ---------------------------------------------------------------------------
# 7. Identifier detection
# ---------------------------------------------------------------------------

ID_ROLE_ALIASES = {
    "order_id": [
        "order id", "order no", "order number", "ord", "po number",
        "order reference", "orderid", "orderno",
    ],
    "invoice_id": ["invoice id", "invoice number", "invoice no", "invoiceno"],
    "customer_id": [
        "customer id", "customer no", "customer number", "cust id", "buyer id",
        "client id", "customerid", "custid",
    ],
    "product_id": [
        "product id", "product no", "product code", "item id", "item code",
        "sku", "article no", "productid", "itemid",
    ],
    "transaction_id": [
        "transaction id", "txn id", "transaction no", "reference", "ref",
        "payment id", "receipt id", "transactionid",
    ],
}

ID_NAME_HINTS = {
    "email": "customer_id", "phone": "customer_id", "mobile": "customer_id",
}


def _detect_identifiers(column_profiles, df):
    result = []
    for profile in column_profiles:
        name = profile["name"]
        inferred = profile["inferred_type"]
        # dates and plain measures are never identifiers
        if inferred in ("datetime", "float", "boolean"):
            continue

        non_null = len(df[name].dropna())
        if non_null < 5:
            continue

        unique_ratio = profile["unique_ratio"]

        # name-based signal (strict: no noisy fuzzy on generic names)
        name_score, name_role = _identifier_name_score(name)

        # content-based signal - only for string-like code columns
        content_score = 0.0
        if inferred in ("text", "categorical") and _looks_like_code(
            df[name].dropna().head(80), "text"
        ):
            content_score = 0.35
            if unique_ratio >= 0.9:
                content_score += 0.30
            if unique_ratio >= 0.99:
                content_score += 0.10

        if name_score < 0.60 and content_score < 0.50:
            continue

        confidence = max(content_score, name_score * 0.75 + content_score * 0.25)
        confidence = min(0.99, round(confidence, 2))

        possible_type = name_role or _guess_id_type_from_name(name) or "identifier"
        result.append({
            "column": name,
            "possible_type": possible_type,
            "confidence": confidence,
        })

    result.sort(key=lambda r: r["confidence"], reverse=True)
    return result[:10]


def _identifier_name_score(name):
    """
    Return (score, possible_id_type). Exact/squashed matches win (e.g.
    'CustomerId' == 'customer id'). A fuzzy match is only accepted when the
    name clearly contains an ID keyword (id/no/number/code/sku/ref) so plain
    names like 'revenue' or 'Txn_Date' are never misread as IDs.
    """
    canonical = _canonical_name(name)
    squashed = _squash(canonical)

    best_score, best_role = 0.0, None
    exact_only = True
    for role, aliases in ID_ROLE_ALIASES.items():
        for alias in aliases:
            alias_squashed = _squash(alias)
            if canonical == _canonical_name(alias) or squashed == alias_squashed:
                if 1.0 > best_score:
                    best_score, best_role = 1.0, role
                continue
            if not exact_only:
                continue
            if not _has_id_keyword(canonical):
                continue
            score = _name_similarity(name, alias)
            if score > best_score:
                best_score, best_role = score, role
        exact_only = False  # second pass allows fuzzy with keyword guard

    # email / phone / mobile under a customer-style name
    hint = ID_NAME_HINTS.get(squashed)
    if hint and best_score < 0.95:
        hint_score = max(_name_similarity(name, ali) for ali in FIELD_ALIASES["customer"])
        if hint_score > best_score:
            best_score, best_role = hint_score, hint
    return best_score, best_role


def _has_id_keyword(canonical):
    """Does the canonical name contain an ID-ish keyword, e.g. 'order code'?"""
    if re.search(r"\b(id|no|nu|num|number|code|ref|refno|sku)\b", canonical):
        return True
    return canonical.endswith(("id", "no", "num", "code", "ref", "sku"))


def _guess_id_type_from_name(name):
    best_score, best_role = 0.0, None
    for role, aliases in ID_ROLE_ALIASES.items():
        score = max(_name_similarity(name, alias) for alias in aliases)
        if score > best_score:
            best_score, best_role = score, role
    return best_role


def _looks_like_code(values, inferred_type):
    if inferred_type == "integer":
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        if len(numeric) == 0:
            return False
        return float((numeric >= 0).mean()) >= 0.8
    texts = [str(v).strip() for v in values.head(20)]
    if not texts:
        return False
    pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_/.#]*$")
    matched = sum(1 for t in texts if t and pattern.match(t) and len(t) <= 40)
    return float(matched) / len(texts) >= 0.8


# ---------------------------------------------------------------------------
# 8. Dimension / segmentation candidates
# ---------------------------------------------------------------------------

DIMENSION_ROLES = {
    "customer": "customer", "product": "product", "category": "category",
    "city": "city", "country": "country", "region": "region",
    "payment": "payment_method", "channel": "channel", "status": "status",
}


def _detect_dimensions(column_profiles, df, detected_fields):
    profile_by_name = {p["name"]: p for p in column_profiles}
    dims = []
    seen = set()

    # 1) columns already flagged with a dimension-like role
    for role, entries in detected_fields.items():
        dim_role = DIMENSION_ROLES.get(role)
        if not dim_role:
            continue
        for entry in entries:
            col_name = entry["column"]
            if col_name in seen:
                continue
            profile = profile_by_name.get(col_name)
            if not profile:
                continue
            if profile["unique_count"] < 2:
                continue
            seen.add(col_name)
            confidence = min(0.99, round(entry["confidence"] * 0.75 + 0.20, 2))
            dims.append({
                "column": col_name,
                "unique_count": profile["unique_count"],
                "unique_ratio": profile["unique_ratio"],
                "confidence": confidence,
                "possible_role": dim_role,
            })

    # 2) any other nicely-categorical column as a generic segment
    for profile in column_profiles:
        if profile["name"] in seen:
            continue
        if profile["inferred_type"] not in ("categorical", "text", "boolean"):
            continue
        if profile["unique_count"] < 2 or profile["unique_count"] > 500:
            continue
        if profile["unique_ratio"] >= 1.0 and profile["inferred_type"] == "text":
            continue
        confidence = round(min(0.90, 0.50 + (1 - profile["unique_ratio"]) * 0.40), 2)
        seen.add(profile["name"])
        dims.append({
            "column": profile["name"],
            "unique_count": profile["unique_count"],
            "unique_ratio": profile["unique_ratio"],
            "confidence": confidence,
            "possible_role": "segment",
        })

    dims.sort(key=lambda d: d["confidence"], reverse=True)
    return dims[:20]


# ---------------------------------------------------------------------------
# 9. Data quality profile
# ---------------------------------------------------------------------------

def _data_quality_profile(df, column_profiles, dropped_empty_rows):
    total_rows = len(df)
    total_columns = len(df.columns)
    total_cells = total_rows * total_columns

    duplicate_rows = int(df.duplicated().sum())
    duplicate_pct = round(duplicate_rows / total_rows, 4) if total_rows else 0.0

    total_missing = int(df.isna().sum().sum())
    missing_pct = round(total_missing / total_cells, 4) if total_cells else 0.0

    empty_columns = [p["name"] for p in column_profiles if p["inferred_type"] == "empty"]
    constant_columns = [
        p["name"] for p in column_profiles
        if p["inferred_type"] != "empty" and p["unique_count"] == 1
    ]
    mostly_empty_columns = [
        p["name"] for p in column_profiles
        if p["inferred_type"] != "empty"
        and 0.8 <= p["null_percentage"] < 1.0
    ]

    return {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "duplicate_row_count": duplicate_rows,
        "duplicate_row_percentage": duplicate_pct,
        "total_missing_cells": total_missing,
        "missing_cell_percentage": missing_pct,
        "completely_empty_columns": empty_columns,
        "completely_empty_rows_dropped": dropped_empty_rows,
        "constant_columns": constant_columns,
        "mostly_empty_columns": mostly_empty_columns,
    }


# ---------------------------------------------------------------------------
# 10. Date analysis
# ---------------------------------------------------------------------------

def _date_analysis(column_profiles, df, detected_fields):
    date_role_columns = {
        entry["column"]: entry["confidence"]
        for entry in detected_fields.get("date", [])
    }
    candidates = []
    for profile in column_profiles:
        # never treat pure numeric columns as dates (pandas would read
        # numbers as nanoseconds since epoch)
        if profile["inferred_type"] not in ("datetime", "text"):
            continue
        dates = pd.to_datetime(
            df[profile["name"]], errors="coerce", format="mixed"
        ).dropna()
        if len(dates) == 0:
            continue
        is_date_like = profile["inferred_type"] == "datetime"
        name_hint = _best_alias(profile["name"], "date")[1] >= 0.55
        if not (is_date_like or name_hint):
            continue
        confidence = date_role_columns.get(profile["name"])
        if confidence is None:
            confidence = 0.6 if is_date_like else 0.5
        candidates.append({
            "column": profile["name"],
            "min_date": dates.min().strftime("%Y-%m-%d"),
            "max_date": dates.max().strftime("%Y-%m-%d"),
            "confidence": round(min(0.99, confidence), 2),
        })

    earliest = None
    latest = None
    if candidates:
        earliest = min(c["min_date"] for c in candidates)
        latest = max(c["max_date"] for c in candidates)

    return {
        "date_like_column_count": len(candidates),
        "has_date": len(candidates) > 0,
        "date_candidates": candidates,
        "earliest_date": earliest,
        "latest_date": latest,
    }


# ---------------------------------------------------------------------------
# 11. Primary / transaction sheet candidate + relationships (Excel workbooks)
# ---------------------------------------------------------------------------

def _pick_primary_sheet(sheet_names, header_frames):
    """Return the sheet_name most likely to be the primary transaction dataset."""
    best_name, best_score = None, -1.0
    for name in sheet_names:
        if name not in header_frames:
            continue
        frame = header_frames[name]
        score = 0.0
        size_bonus = min(len(frame), 5000) / 5000.0
        score += size_bonus

        for col in frame.columns:
            col_name = str(col)
            has_date = _best_alias(col_name, "date")[1] >= 0.8
            if has_date:
                score += 0.30
            # check date-ish type as a stronger signal
            if pd.api.types.is_datetime64_any_dtype(frame[col]):
                score += 0.45
            if _best_alias(col_name, "revenue")[1] >= 0.8:
                score += 0.55
            if _best_alias(col_name, "order")[1] >= 0.8:
                score += 0.35
            if _best_alias(col_name, "quantity")[1] >= 0.8:
                score += 0.20
            if _best_alias(col_name, "customer")[1] >= 0.8:
                score += 0.15
            if _best_alias(col_name, "product")[1] >= 0.8:
                score += 0.10

        if score > best_score:
            best_score, best_name = score, name

    if best_name is None:
        # fall back to the largest sheet
        best_name = max(header_frames, key=lambda n: len(header_frames[n])) \
            if header_frames else None

    confidence = min(0.99, round(0.50 + best_score / 10.0, 2))
    return best_name, confidence, round(best_score, 3)


def _detect_relationships(primary_name, header_frames, max_results=6):
    """
    Heuristic-only key detection between the primary sheet and other sheets.
    Uses matching/overlapping column values; does NOT build joins.
    """
    relationships = []
    primary_frame = header_frames.get(primary_name)
    if primary_frame is None:
        return relationships

    other_names = [name for name in header_frames if name != primary_name]
    other_frames = [(name, header_frames[name]) for name in other_names]

    for other_name, other_frame in other_frames:
        for primary_col in primary_frame.columns:
            for other_col in other_frame.columns:
                name_score = max(
                    _name_similarity(primary_col, other_col),
                    _squash(primary_col) == _squash(other_col),
                )
                overlap = _value_overlap(
                    primary_frame[primary_col], other_frame[other_col]
                )
                if overlap <= 0.05 or name_score < 0.5:
                    continue
                confidence = round(min(0.99, 0.45 * name_score + 0.60 * overlap), 2)
                relationships.append({
                    "from_sheet": primary_name,
                    "from_column": str(primary_col),
                    "to_sheet": other_name,
                    "to_column": str(other_col),
                    "overlap_ratio": round(overlap, 4),
                    "confidence": confidence,
                })

    # dedupe mirrored pairs, keep the best scoring pair per sheet pair
    relationships.sort(key=lambda r: r["confidence"], reverse=True)

    deduped = []
    seen_pairs = set()
    for rel in relationships:
        pair_key = tuple(sorted([rel["from_sheet"], rel["to_sheet"]]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        deduped.append(rel)
        if len(deduped) >= max_results:
            break
    return deduped


def _value_overlap(series_a, series_b, max_sample=1500):
    a = series_a.dropna().astype(str).str.strip()
    b = series_b.dropna().astype(str).str.strip()
    if len(a) == 0 or len(b) == 0:
        return 0.0
    if len(a) > max_sample:
        a = a.sample(max_sample, random_state=1)
    if len(b) > max_sample:
        b = b.sample(max_sample, random_state=1)
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / min(len(set_a), len(set_b))


# ---------------------------------------------------------------------------
# 12. Preliminary capability preview
# ---------------------------------------------------------------------------

def _capability_preview(detected_fields):
    def has(role):
        return role in detected_fields and len(detected_fields[role]) > 0

    preview = {
        "time_series_analysis": has("date"),
        "revenue_analysis": has("revenue"),
        "order_analysis": has("order"),
        "product_analysis": has("product"),
        "customer_analysis": has("customer"),
        "city_analysis": has("city"),
        "country_analysis": has("country"),
        "region_analysis": has("region"),
        "cost_analysis": has("cost"),
        "shipping_analysis": has("shipping"),
        "marketing_analysis": has("marketing"),
        "quantity_analysis": has("quantity"),
        "price_analysis": has("price"),
        "profit_analysis": has("profit"),
        "category_analysis": has("category"),
        "payment_analysis": has("payment"),
        "channel_analysis": has("channel"),
        "status_analysis": has("status"),
        "discount_analysis": has("discount"),
        "tax_analysis": has("tax"),
    }

    notes = []
    if not has("date"):
        notes.append("date: not detected - time-series analysis is not possible.")
    if not has("revenue"):
        notes.append("revenue: not detected - core revenue metrics cannot be computed.")
    if not has("marketing"):
        notes.append(
            "marketing: not detected - CAC/ROAS and Net Profit cannot be computed; "
            "marketing is never assumed to be zero."
        )
    if not has("cost"):
        notes.append("cost: not detected - Gross Profit cannot be computed from this dataset.")
    if not has("order"):
        notes.append(
            "order: not detected - order-level analysis may be limited (no order identifier found)."
        )
    preview["notes"] = notes
    return preview


# ---------------------------------------------------------------------------
# 13. Main entry point
# ---------------------------------------------------------------------------

def profile_dataset(file_path_or_dataframe, filename=None, sheet_name=None, max_sample_values=5):
    """
    Profile a CSV / XLSX / XLS file (path or raw bytes) or an in-memory DataFrame.

    Returns a JSON-serializable dict describing the workbook, columns,
    detected business fields, identifiers, dimensions, data quality,
    date analysis, sheet relationships and a capability preview.
    """
    loaded = _load_sheets(file_path_or_dataframe, filename=filename)
    file_type = loaded["file_type"]
    sheets = loaded["sheets"]

    # ---- workbook section ------------------------------------------------
    sheet_meta = [_sheet_structure(s["name"], s["raw"]) for s in sheets]
    workbook = {
        "file_type": file_type,
        "sheet_count": len(sheets),
        "sheets": sheet_meta,
    }

    non_empty = [m for m in sheet_meta if not m["is_empty"]]
    if not non_empty:
        names = [m["sheet_name"] for m in sheet_meta]
        raise ProfileError(
            "No usable data found in the workbook/file "
            f"(every sheet is empty or blank). Sheets inspected: {names}."
        )

    # parse headers for every readable sheet so we can score and relate them
    header_frames = {}
    for s in sheets:
        if s["raw"].dropna(how="all").empty:
            continue
        try:
            header_frames[s["name"]] = _header_frame(
                s["raw"], s["name"], s["parse_headers"]
            )
        except ProfileError:
            continue  # this sheet cannot be used as a primary/profile sheet

    if not header_frames:
        usable = [m["sheet_name"] for m in non_empty]
        raise ProfileError(
            "Column headers could not be detected in any readable sheet. "
            f"Sheets present: {usable}."
        )

    # ---- choose the sheet to profile -------------------------------------
    primary_confidence = None
    if sheet_name is not None:
        if sheet_name not in {m["sheet_name"] for m in non_empty}:
            raise ProfileError(
                f"Sheet '{sheet_name}' was not found or is empty. "
                f"Available sheets: {[m['sheet_name'] for m in sheet_meta]}."
            )
        selected = sheet_name
    else:
        selected, primary_confidence, _ = _pick_primary_sheet(
            [m["sheet_name"] for m in non_empty], header_frames
        )

    if len(non_empty) == 1:
        primary_confidence = 1.0

    sheet_spec = next(s for s in sheets if s["name"] == selected)

    # ---- build the working dataframe with real headers -------------------
    raw = sheet_spec["raw"]
    dropped_empty_rows = int(raw.isna().all(axis=1).sum())
    data = _header_frame(raw, selected, sheet_spec["parse_headers"])

    # ---- per-column profile ----------------------------------------------
    column_profiles = [
        _profile_column(data[col], len(data), max_sample_values)
        for col in data.columns
    ]

    # build detected_fields (confident candidates only)
    detected_fields = {role: [] for role in FIELD_ALIASES}
    for profile in column_profiles:
        if profile["inferred_type"] == "empty":
            continue
        for cand in _candidate_roles(profile["name"], profile):
            detected_fields[cand["role"]].append({
                "column": profile["name"],
                "confidence": cand["confidence"],
            })

    # apply identifier overlay to column inferred_type
    identifiers = _detect_identifiers(column_profiles, data)
    identifier_columns = {entry["column"] for entry in identifiers}
    for profile in column_profiles:
        if profile["name"] in identifier_columns and profile["inferred_type"] in (
            "integer", "text", "categorical",
        ):
            profile["inferred_type"] = "identifier"

    detected_fields = {role: entries for role, entries in detected_fields.items() if entries}

    missing_common_fields = [
        role for role in ("marketing", "cost", "shipping", "tax", "discount", "profit", "date", "revenue")
        if role not in detected_fields
    ]

    dimensions = _detect_dimensions(column_profiles, data, detected_fields)
    data_quality = _data_quality_profile(data, column_profiles, dropped_empty_rows)
    date_analysis = _date_analysis(column_profiles, data, detected_fields)

    # ---- relationships (Excel workbooks with multiple non-empty sheets) ---
    relationships = []
    if workbook["sheet_count"] > 1:
        relationships = _detect_relationships(selected, header_frames)

    capability_preview = _capability_preview(detected_fields)

    dataset_section = {
        "primary_sheet_candidate": selected,
        "primary_sheet_confidence": primary_confidence,
        "row_count": len(data),
        "column_count": len(data.columns),
        "header_row_index": 0,
        "has_headers": True,
    }

    return {
        "file_type": file_type,
        "workbook": workbook,
        "dataset": dataset_section,
        "columns": column_profiles,
        "detected_fields": detected_fields,
        "missing_common_fields": missing_common_fields,
        "identifiers": identifiers,
        "dimensions": dimensions,
        "data_quality": data_quality,
        "date_analysis": date_analysis,
        "relationships": relationships,
        "capability_preview": capability_preview,
    }