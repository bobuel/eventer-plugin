"""Pure quote normalization. Untrusted source text never supplies authority."""

import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .errors import DomainError

PURPOSES = {"quote_request", "clarification", "acceptance", "count_change", "cancellation", "deadline_followup"}
COMMITTING = {"acceptance", "count_change", "cancellation"}


def money(value: Any, *, positive: bool = False) -> Decimal:
    if isinstance(value, (float, bool)) or not isinstance(value, (str, int, Decimal)):
        raise DomainError("VALIDATION_ERROR", "Use exact decimal strings for financial values")
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result > Decimal("999999999999.99"):
            raise ValueError()
        if result != result.quantize(Decimal(".01")) or (positive and result == 0):
            raise ValueError()
    except (InvalidOperation, ValueError) as exc:
        raise DomainError(
            "VALIDATION_ERROR", "Amount must be a finite nonnegative decimal with at most two places"
        ) from exc
    return result


def instant(value: Any) -> datetime:
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if result.tzinfo is None:
            raise ValueError()
        return result
    except (ValueError, TypeError) as exc:
        raise DomainError("VALIDATION_ERROR", "Timestamp must include a timezone offset") from exc


def normalize_quote(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "currency",
        "items",
        "tax",
        "fees",
        "deposit",
        "service_start",
        "service_end",
        "valid_until",
        "cancellation_terms",
        "minimums",
        "location",
        "confidence",
        "deadlines",
        "host_entered",
        "source_spans",
    }
    if set(data) - allowed:
        raise DomainError("VALIDATION_ERROR", "Quote has unknown fields; source instructions cannot set authority")
    currency = data.get("currency")
    if currency is not None and (not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)):
        raise DomainError("VALIDATION_ERROR", "Currency requires a three-letter uppercase code or explicit unknown")
    items = data.get("items", [])
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise DomainError("VALIDATION_ERROR", "Quote requires 1–100 line items")
    normalized = []
    subtotal = Decimal(0)
    complete = True
    for item in items:
        if set(item) - {"description", "quantity", "unit_price", "source_span"}:
            raise DomainError("VALIDATION_ERROR", "Unexpected line-item field")
        description, span = str(item.get("description", "")).strip(), str(item.get("source_span", "")).strip()
        if not description or len(description) > 255 or not span or len(span) > 1000:
            raise DomainError(
                "VALIDATION_ERROR", "Every line needs a description and source span or host-entered label"
            )
        quantity = item.get("quantity")
        try:
            if isinstance(quantity, (float, bool)):
                raise ValueError()
            quantity = Decimal(str(quantity))
            exponent = quantity.as_tuple().exponent
            if (
                not quantity.is_finite()
                or quantity <= 0
                or quantity > 1000000
                or not isinstance(exponent, int)
                or exponent < -3
            ):
                raise ValueError()
        except (InvalidOperation, ValueError) as exc:
            raise DomainError(
                "VALIDATION_ERROR", "Quantity must be an exact positive decimal up to three places"
            ) from exc
        price = money(item["unit_price"]) if item.get("unit_price") is not None else None
        amount = (quantity * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) if price is not None else None
        if amount is None:
            complete = False
        else:
            subtotal += amount
        normalized.append(
            {
                "description": description,
                "quantity": str(quantity),
                "unit_price": str(price) if price is not None else None,
                "amount": str(amount) if amount is not None else None,
                "source_span": span,
            }
        )
    result = {k: data.get(k) for k in allowed - {"items", "deadlines", "source_spans"}}
    result["items"] = normalized
    for key in ("tax", "fees", "deposit"):
        result[key] = str(money(data[key])) if data.get(key) is not None else None
    for key in ("service_start", "service_end", "valid_until"):
        result[key] = instant(data[key]).isoformat() if data.get(key) else None
    if (
        result["service_start"]
        and result["service_end"]
        and instant(result["service_end"]) <= instant(result["service_start"])
    ):
        raise DomainError("VALIDATION_ERROR", "Service end must follow service start")
    for key in ("cancellation_terms", "minimums", "location"):
        value = result[key]
        if value is not None and (not isinstance(value, str) or len(value) > 2000):
            raise DomainError("VALIDATION_ERROR", "Vendor-specific text exceeds 2000 characters")
    if data.get("confidence", "host_entered") not in {"host_entered", "high", "medium", "low", "unknown"}:
        raise DomainError("VALIDATION_ERROR", "Invalid source confidence")
    result["confidence"] = data.get("confidence", "host_entered")
    result["host_entered"] = data.get("host_entered", True)
    spans = data.get("source_spans", {})
    if not isinstance(spans, dict) or any(
        k not in allowed or not isinstance(v, str) or not 1 <= len(v) <= 1000 for k, v in spans.items()
    ):
        raise DomainError("VALIDATION_ERROR", "Invalid normalized-field source spans")
    if not result["host_entered"]:
        for key in allowed - {"items", "host_entered", "confidence", "source_spans", "deadlines"}:
            if result.get(key) is not None and key not in spans:
                raise DomainError("VALIDATION_ERROR", f"Extracted {key} requires an exact source span")
    result["source_spans"] = spans
    deadlines = data.get("deadlines", {})
    if not isinstance(deadlines, dict) or set(deadlines) - {"deposit", "balance", "final_count", "cancellation"}:
        raise DomainError("VALIDATION_ERROR", "Unsupported vendor deadline")
    if deadlines and not result["host_entered"] and "deadlines" not in spans:
        raise DomainError("VALIDATION_ERROR", "Extracted deadlines need source evidence")
    result["deadlines"] = {k: instant(v).isoformat() for k, v in deadlines.items()}
    result["subtotal"] = str(subtotal) if complete else None
    total = (
        subtotal + Decimal(result["tax"]) + Decimal(result["fees"])
        if complete and result["tax"] is not None and result["fees"] is not None
        else None
    )
    result["total"] = str(total) if total is not None else None
    result["unknown_fields"] = sorted(k for k, v in result.items() if v is None)
    if total is not None and result["deposit"] is not None and Decimal(result["deposit"]) > total:
        raise DomainError("VALIDATION_ERROR", "Deposit exceeds the known total")
    return result


def semantic_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"field": key, "before": before.get(key), "after": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    ]


def compare(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    currencies = {s.get("currency") for s in snapshots}
    comparable = len(currencies) == 1 and None not in currencies and all(s.get("total") is not None for s in snapshots)
    return {
        "comparable": comparable,
        "reason": "Same-currency known totals"
        if comparable
        else "Unknown totals or different currencies; no exchange rate is assumed",
        "quotes": snapshots,
        "differences": semantic_diff(snapshots[0], snapshots[1]) if len(snapshots) == 2 else [],
    }


def extract_candidate(content: str) -> dict[str, Any]:
    """Conservative offline extraction of explicit quote lines, never an authority input.

    Supports `6 x Dinner @ USD 21.95` and explicit `Tax: 0.00` lines.
    Everything else stays unknown and the host reviews the exact source spans.
    """
    if not isinstance(content, str) or len(content) > 50000:
        raise DomainError("VALIDATION_ERROR", "Quote source must be text up to 50000 characters")
    items, currencies = [], set()
    spans: dict[str, str] = {}
    for line in content.splitlines():
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d{1,3})?)\s*[x×]\s*(.{1,255}?)\s*@\s*([A-Z]{3})\s+(\d+(?:\.\d{1,2})?)\s*", line
        )
        if match:
            quantity, description, currency, price = match.groups()
            items.append({"quantity": quantity, "description": description, "unit_price": price, "source_span": line})
            currencies.add(currency)
            spans["currency"] = line
    result: dict[str, Any] = {
        "items": items,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "host_entered": False,
        "confidence": "low",
        "source_spans": spans,
        "deadlines": {},
    }
    if len(currencies) != 1:
        spans.pop("currency", None)
    for key in ("tax", "fees", "deposit"):
        found = list(re.finditer(rf"(?im)^{key}:\s*(\d+(?:\.\d{{1,2}})?)\s*$", content))
        result[key] = found[0].group(1) if len(found) == 1 else None
        if len(found) == 1:
            spans[key] = found[0].group(0)
    # No inferential currency conversion, dates, availability, payment status, or commitment.
    return {
        "snapshot": result,
        "requires_host_review": True,
        "committed": False,
        "sent": False,
        "unsupported_source": not items,
        "caveat": "Only explicit line items and labeled amounts extracted; all other terms remain unknown.",
    }
