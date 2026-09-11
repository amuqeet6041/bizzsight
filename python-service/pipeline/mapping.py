"""
mapping.py
Auto-detects which uploaded column corresponds to which "standard field"
using fuzzy string matching against known aliases.
"""

from rapidfuzz import process, fuzz

STANDARD_FIELDS = [
    "order_id",
    "order_date",
    "customer_id",
    "product_id",
    "quantity",
    "revenue",
    "cost_of_goods",
    "shipping_cost",
    "marketing_spend",
    "status",
]

# Common real-world column name variations for each standard field.
# Add more aliases here anytime you test a new export format.
ALIASES = {
    "order_id": ["order id", "order no", "order number", "id", "invoice no"],
    "order_date": ["date", "order date", "created at", "purchase date", "timestamp"],
    "customer_id": ["customer", "customer id", "email", "phone", "buyer", "customer name"],
    "product_id": ["product", "product id", "product name", "sku", "item", "item name", "item sku", "variant", "title"],
    "quantity": ["qty", "quantity", "units", "no of items", "item qty"],
    "revenue": ["total", "grand total", "sales", "amount", "order total", "price", "net sales"],
    "cost_of_goods": ["cogs", "cost", "unit cost", "product cost", "cost price"],
    "shipping_cost": ["shipping", "delivery charges", "courier fee", "freight", "shipping cost"],
    "marketing_spend": ["ad spend", "marketing cost", "meta ads cost", "campaign spend", "ads cost"],
    "status": ["order status", "status", "delivery status", "fulfillment status"],
}


def suggest_column_mapping(uploaded_columns, threshold=55):
    """
    Given a list of raw column names from the uploaded file, suggest which
    standard field each one maps to.

    Returns: dict {uploaded_column_name: (standard_field_or_None, confidence_score)}
    """
    alias_lookup = {}
    for field, aliases in ALIASES.items():
        for a in aliases:
            alias_lookup[a] = field

    choices = list(alias_lookup.keys())
    suggestions = {}

    for col in uploaded_columns:
        col_clean = str(col).strip().lower()
        match = process.extractOne(col_clean, choices, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= threshold:
            matched_alias, score, _ = match
            suggestions[col] = (alias_lookup[matched_alias], score)
        else:
            suggestions[col] = (None, 0)

    return suggestions
