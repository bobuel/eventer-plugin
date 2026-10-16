"""Source-grounded manual research and offline adapter. No implicit network access."""

import ipaddress
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlsplit

from .errors import DomainError
from .meal_engine import instant

DISCLAIMER = "Recommendation only. Hours, prices, availability and accessibility require direct confirmation."
CONSTRAINT_KEYS = {"max_distance_km", "max_travel_minutes", "accessible_required", "group_size", "minimum_age"}


def public_source(value: str) -> str:
    try:
        parsed = urlsplit(value)
        _ = parsed.port  # Access validates malformed or out-of-range ports.
    except ValueError as exc:
        raise DomainError("VALIDATION_ERROR", "Source must be a valid public HTTPS URL") from exc
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment:
        raise DomainError("VALIDATION_ERROR", "Source must be a public HTTPS URL without credentials or fragment")
    if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal")) or "." not in host:
        raise DomainError("VALIDATION_ERROR", "Private source hosts are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise DomainError("VALIDATION_ERROR", "Private source addresses are not allowed")
    if len(value) > 2000:
        raise DomainError("VALIDATION_ERROR", "Source URL too long")
    return value


def evaluate(candidate: dict[str, Any], constraints: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if set(constraints) - CONSTRAINT_KEYS:
        raise DomainError("VALIDATION_ERROR", "Research accepts only explicit aggregate group constraints")
    public_source(candidate["source_url"])
    try:
        retrieved = instant(candidate["retrieved_at"])
    except (ValueError, AttributeError, TypeError) as exc:
        raise DomainError("VALIDATION_ERROR", "Retrieval time requires an explicit UTC offset") from exc
    if retrieved > now + timedelta(minutes=5):
        raise DomainError("VALIDATION_ERROR", "Retrieval time cannot be in the future")
    failures = []
    if constraints.get("accessible_required") and candidate.get("accessible") is not True:
        failures.append("accessibility_not_confirmed")
    for key, fact in (("max_distance_km", "distance_km"), ("max_travel_minutes", "travel_minutes")):
        if constraints.get(key) is not None and (candidate.get(fact) is None or candidate[fact] > constraints[key]):
            failures.append(f"exceeds_or_unknown_{key}")
    if constraints.get("group_size") and (
        candidate.get("max_group_size") is None or candidate["max_group_size"] < constraints["group_size"]
    ):
        failures.append("group_capacity_not_confirmed")
    if constraints.get("minimum_age") is not None and (
        candidate.get("minimum_age") is None or candidate["minimum_age"] > constraints["minimum_age"]
    ):
        failures.append("age_fit_not_confirmed")
    stale = now > retrieved + timedelta(hours=24)
    return {
        "eligible": not failures and not stale,
        "disqualified_reasons": failures,
        "stale": stale,
        "refresh_due_at": (retrieved + timedelta(hours=24)).isoformat(),
        "disclaimer": DISCLAIMER,
    }


class ResearchAdapter(Protocol):
    def search(self, constraints: dict[str, Any]) -> list[dict[str, Any]]: ...


class FakeResearchAdapter:
    def __init__(self, candidates: list[dict[str, Any]] | None = None, fail: bool = False):
        self.candidates, self.fail = candidates or [], fail

    def search(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        if set(constraints) - CONSTRAINT_KEYS:
            raise DomainError("VALIDATION_ERROR", "Raw guest data is not a research query")
        if self.fail:
            raise DomainError("PROVIDER_TEMPORARY_FAILURE", "Research unavailable; retry the saved request")
        return self.candidates
