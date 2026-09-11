"""
llm.py  —  Phase 2 LLM provider abstraction for BizSight.

Provider-agnostic interface. Env config (read once, never logged):
    LLM_PROVIDER   : "openai" | "openai-compatible" | "mock"
    LLM_API_KEY    : API key (never returned in responses)
    LLM_MODEL      : model name (e.g. "gpt-4o")
    LLM_MODE       : "mock" overrides LLM_PROVIDER with deterministic profiler-based output

Usage:
    from pipeline.llm import LLMConfig, get_llm_provider
    provider = get_llm_provider()
    result = provider.generate_semantic_mapping(context_dict)
"""

import json
import os
import re
import time
import uuid

import httpx


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class LLMConfig:
    """Immutable snapshot of env-based configuration."""

    def __init__(self):
        self.provider: str = os.environ.get("LLM_PROVIDER", "").strip().lower()
        self.api_key: str = os.environ.get("LLM_API_KEY", "").strip()
        self.model: str = os.environ.get("LLM_MODEL", "").strip()
        self.mode: str = os.environ.get("LLM_MODE", "").strip().lower()

    @property
    def is_configured(self) -> bool:
        return bool(self.provider and self.api_key)

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    def __repr__(self):
        return (
            "LLMConfig("
            f"provider='{self.provider}', "
            f"model='{self.model}', "
            f"mode='{self.mode}', "
            f"api_key={'***' if self.api_key else ''})"
        )


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class LLMProvider:
    """Abstract base — all providers implement these methods."""

    def generate_semantic_mapping(self, context: dict) -> dict:
        raise NotImplementedError

    def complete(self, system_prompt: str, user_prompt: str, context: dict | None = None) -> str:
        """
        Returns the raw completion text (expected to hold one JSON object)
        for the given prompt pair. `context` carries pipeline metadata such as
        the business-advisor fact pack (`_task`, `_fact_pack`).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock provider (deterministic, based on profiler output)
# ---------------------------------------------------------------------------

# Profiler role names that are NOT valid LLM roles (must be translated or dropped)
_PROFILER_TO_LLM_ROLE = {
    "order": "order_id",
    "date": "date",
    "revenue": "revenue",
    "quantity": "quantity",
    "price": "price",
    "cost": "cost",
    "shipping": "shipping",
    "marketing": "marketing",
    "discount": "discount",
    "tax": "tax",
    "profit": "profit",
    "customer": "customer",
    "product": "product",
    "category": "category",
    "city": "city",
    "country": "country",
    "region": "region",
    "payment": "payment",
    "channel": "channel",
    "status": "status",
}
_VALID_LLM_ROLES = set(_PROFILER_TO_LLM_ROLE.values()) | {
    "order_id", "customer_id", "product_id", "invoice_id", "transaction_id",
}


def _squash_name(text: str) -> str:
    """Lower-case, remove separators/case-boundaries so 'CustomerID' == 'customerid'."""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _matches_id_spelling(column: str, possible_type: str) -> bool:
    """
    True when the column's name literally spells out the identifier type
    (e.g. 'CustomerID' contains 'customerid'). Used to prefer the precise
    identifier role over a generic dimension role, WITHOUT mistaking a
    plain 'Customer' name column for a stable customer ID.
    """
    col = _squash_name(column)
    ptype = _squash_name(possible_type)
    return bool(ptype) and ptype in col


class MockLLMProvider(LLMProvider):
    """
    Deterministic profiler-based responses. Clearly labeled as mock.
    Uses identifiers + detected_fields from the context to produce sensible,
    vocabulary-valid role assignments without any network call.
    """

    def generate_semantic_mapping(self, context: dict) -> dict:
        time.sleep(0.01)  # simulate latency

        # Accept either the full llm_context (with .context wrapper) or the
        # inner compact context directly.
        inner = context.get("context", context)
        columns = inner.get("columns", [])
        identifiers = inner.get("identifiers", [])

        # identifiers: column -> (possible_type, confidence); e.g. order_id.
        # Only identifiers whose type is literally spelled in the column name
        # are treated as stable IDs (a 'Customer Name' column is never a
        # 'customer_id', per the capability engine's safe-ID rule).
        id_by_col: dict[str, tuple[str, float]] = {}
        for entry in identifiers:
            col = entry.get("column")
            ptype = entry.get("possible_type", "identifier")
            conf = entry.get("confidence", 0.0)
            if col and ptype in _VALID_LLM_ROLES and _matches_id_spelling(col, ptype):
                if col not in id_by_col or conf > id_by_col[col][1]:
                    id_by_col[col] = (ptype, round(conf, 2))

        # candidate roles (from profiler detected_fields), column -> best role
        field_by_col: dict[str, tuple[str, float]] = {}
        for col_info in columns:
            for cand in col_info.get("candidate_roles", []):
                role = cand.get("role")
                conf = cand.get("confidence", 0.0)
                role_name = _PROFILER_TO_LLM_ROLE.get(role)
                if role_name is None:
                    continue  # e.g. unknown profiler role
                if col_info["name"] not in field_by_col or \
                        conf > field_by_col[col_info["name"]][1]:
                    field_by_col[col_info["name"]] = (role_name, round(conf, 2))

        mappings = []
        for col_info in columns:
            col = col_info["name"]
            id_role = id_by_col.get(col)
            field_role = field_by_col.get(col)

            if id_role:
                role, conf = id_role
                reason = (
                    f"Mock provider: profiler identified '{col}' as identifier "
                    f"'{role}'."
                )
            elif field_role:
                role, conf = field_role
                reason = (
                    f"Mock provider: profiler detected role '{role}' from column "
                    f"name/content."
                )
            else:
                role, conf = None, 0.0
                reason = "Mock provider: no confident role detected by profiler."

            mappings.append({
                "column": col,
                "role": role,
                "confidence": round(conf, 2),
                "reason": reason,
            })

        return {
            "mappings": mappings,
            "mock": True,
            "model": "mock/profiler-based",
            "request_id": f"mock-{uuid.uuid4().hex[:8]}",
        }

    def complete(self, system_prompt: str, user_prompt: str, context: dict | None = None) -> str:
        time.sleep(0.01)  # simulate latency
        task = (context or {}).get("_task")
        if task == "business-advisor" and (context or {}).get("_fact_pack"):
            from pipeline.advisor import mock_advisor_response
            return json.dumps(mock_advisor_response(context["_fact_pack"]))
        return json.dumps({
            "mock": True,
            "task": task,
            "message": "Mock provider placeholder completion.",
        })


# ---------------------------------------------------------------------------
# OpenAI-compatible HTTP provider
# ---------------------------------------------------------------------------

_OPENAI_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
}

# Models known to use OpenAI-compatible /chat/completions format
_OPENAI_COMPATIBLE_MODELS = (
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "claude-3", "claude-3.5", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
)


class OpenAICompatibleProvider(LLMProvider):
    """
    Generic httpx-based provider for OpenAI-compatible APIs.
    Reads LLM_PROVIDER / LLM_API_KEY / LLM_MODEL from env.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self.endpoint = _OPENAI_ENDPOINTS.get(config.provider)
        if not self.endpoint:
            # fallback: try as a custom endpoint URL
            self.endpoint = config.provider if config.provider.startswith("http") else None

    def generate_semantic_mapping(self, context: dict) -> dict:
        content, request_id = self._post_chat(
            context.get("_system_prompt", ""), context.get("_user_prompt", "")
        )
        return {
            "mappings": content.get("mappings", []),
            "mock": False,
            "model": self.config.model,
            "request_id": request_id,
        }

    def complete(self, system_prompt: str, user_prompt: str, context: dict | None = None) -> str:
        content, _request_id = self._post_chat(system_prompt, user_prompt)
        return json.dumps(content)

    def _post_chat(self, system_prompt: str, user_prompt: str):
        """Shared chat-completions HTTP call. Returns (parsed_json, request_id)."""
        if not self.config.api_key or not self.config.model:
            raise LLMSemanticError("LLM provider is not configured (missing API key or model).")
        if not self.endpoint:
            raise LLMSemanticError(
                f"Unsupported LLM_PROVIDER: '{self.config.provider}'. "
                "Use 'openai', 'openai-compatible', or a full HTTP endpoint URL."
            )

        request_id = f"req-{uuid.uuid4().hex[:12]}"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    self.endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMSemanticError(
                f"LLM API returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMSemanticError(f"LLM API request failed: {exc}") from exc

        try:
            body = resp.json()
        except Exception as exc:
            raise LLMSemanticError("LLM API returned non-JSON response.") from exc

        raw_content = _extract_content(body)
        if not raw_content:
            raise LLMSemanticError("LLM API returned empty message content.")

        return raw_content, request_id


def _extract_content(body: dict) -> dict:
    """Navigate OpenAI-style response to extract the JSON assistant message."""
    try:
        choices = body.get("choices", [])
        if not choices:
            return {}
        message = choices[0].get("message", {})
        content_str = message.get("content", "")
        if not content_str:
            return {}
        # strip markdown code fences if present
        content_str = re.sub(r"^```(?:json)?\s*", "", content_str.strip())
        content_str = re.sub(r"\s*```$", "", content_str.strip())
        return json.loads(content_str)
    except (json.JSONDecodeError, KeyError, IndexError):
        return {}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

class LLMSemanticError(Exception):
    """Raised when the LLM call or JSON parsing fails."""


def get_llm_provider(config: LLMConfig | None = None) -> LLMProvider:
    """
    Factory: returns the appropriate provider based on env config.
    LLM_MODE=mock always overrides to MockLLMProvider.
    """
    if config is None:
        config = LLMConfig()
    if config.is_mock or not config.is_configured:
        return MockLLMProvider()
    return OpenAICompatibleProvider(config)


def generate_semantic_mapping(context: dict, config: LLMConfig | None = None) -> dict:
    """
    Convenience wrapper: resolve provider, call it, return raw dict.
    Raises LLMSemanticError on failure.
    """
    provider = get_llm_provider(config)
    return provider.generate_semantic_mapping(context)
