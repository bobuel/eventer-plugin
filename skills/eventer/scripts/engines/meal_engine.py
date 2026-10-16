"""Deterministic meal presence and documented accommodation comparison.

This module never interprets free text or certifies allergen safety.
"""

from collections import Counter
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

GENERATOR_VERSION = "meals-v1"
DIETARY_CATEGORIES = (
    "vegetarian",
    "vegan",
    "gluten_free",
    "dairy_free",
    "nut_free",
    "peanut_free",
    "egg_free",
    "soy_free",
    "fish_free",
    "shellfish_free",
    "sesame_free",
    "halal",
    "kosher",
    "other",
)
NEED_TYPES = ("preference", "restriction", "allergy")
COVERAGE_STATES = ("covered", "provisional", "confirm", "uncovered", "unknown")
DISCLAIMER = "Coverage records documented accommodations; Eventer does not certify allergen safety."
TEMPLATES = (
    {"key": "breakfast", "name": "Breakfast", "start_time": "08:00", "end_time": "09:30"},
    {"key": "lunch", "name": "Lunch", "start_time": "12:00", "end_time": "13:30"},
    {"key": "dinner", "name": "Dinner", "start_time": "18:00", "end_time": "20:00"},
)


def instant(value: str | datetime) -> datetime:
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if result.tzinfo is None:
        raise ValueError("An explicit UTC offset is required")
    return result.astimezone(UTC)


def attendance(meal: dict[str, Any], guest: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if override:
        return {
            "state": {"in": "confirmed", "out": "absent", "uncertain": "possible"}[override["response"]],
            "reason": "explicit_" + override["response"],
            "evidence_id": str(override["evidence_id"]),
        }
    if meal["status"] == "cancelled":
        return {"state": "absent", "reason": "meal_cancelled", "evidence_id": None}
    if guest["rsvp_status"] == "declined":
        return {"state": "absent", "reason": "declined", "evidence_id": None}
    if not guest.get("arrival") or not guest.get("departure"):
        return {"state": "unknown", "reason": "missing_interval", "evidence_id": None}
    start, end = instant(meal["service_start"]), instant(meal["service_end"])
    arrival, departure = instant(guest["arrival"]), instant(guest["departure"])
    zone = ZoneInfo(meal["timezone"])
    uncertain_boundary = guest.get("precision") != "exact_time" and (
        arrival.astimezone(zone).date() in {start.astimezone(zone).date(), end.astimezone(zone).date()}
        or departure.astimezone(zone).date() in {start.astimezone(zone).date(), end.astimezone(zone).date()}
    )
    if uncertain_boundary:
        state, reason = "possible", "imprecise_boundary"
    elif arrival >= end or departure <= start:
        state, reason = "absent", "outside_service_window"
    elif guest["rsvp_status"] != "confirmed" or guest.get("truth_state") != "confirmed":
        state, reason = "possible", "unconfirmed_interval"
    else:
        state, reason = "confirmed", "interval_overlap"
    return {"state": state, "reason": reason, "evidence_id": guest.get("attendance_evidence_id")}


def calculate(
    meal: dict[str, Any],
    guests: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    needs: list[dict[str, Any]],
    accommodations: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Each guest counts once; missing categories are explicit, never inferred from age/name."""
    override_by_guest = {str(row["guest_id"]): row for row in overrides}
    profile_by_guest = {str(row["guest_id"]): row for row in profiles}
    menu = {(row["category"], row["need_type"]): row for row in accommodations}
    need_by_guest: dict[str, list[dict[str, Any]]] = {}
    for need in needs:
        if need.get("active", True):
            need_by_guest.setdefault(str(need["guest_id"]), []).append(need)
    requirement_by_guest: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        requirement_by_guest.setdefault(str(requirement["guest_id"]), []).append(requirement)
    counts = dict.fromkeys(("confirmed", "possible", "unknown", "absent"), 0)
    serving = {category: counts.copy() for category in [*meal["serving_categories"], "unknown"]}
    coverage: Counter[tuple[str, str, str]] = Counter()
    people, details = [], []
    unknown_dietary, unmapped_count = 0, 0
    for guest in sorted(guests, key=lambda row: str(row["id"])):
        gid = str(guest["id"])
        counted: set[tuple[str, str, str]] = set()
        presence = attendance(meal, guest, override_by_guest.get(gid))
        if meal["status"] == "cancelled":
            presence = {"state": "absent", "reason": "meal_cancelled", "evidence_id": None}
        profile = profile_by_guest.get(gid, {})
        category = profile.get("serving_category")
        if category not in serving:
            category = "unknown"
        state = presence["state"]
        counts[state] += 1
        serving[category][state] += 1
        people.append({"guest_id": gid, "name": guest.get("name"), "serving_category": category, **presence})
        if state == "absent":
            continue
        guest_needs = need_by_guest.get(gid, [])
        mapped = {str(row["requirement_id"]) for row in guest_needs}
        unmapped = [row for row in requirement_by_guest.get(gid, []) if str(row["id"]) not in mapped]
        for req in unmapped:
            unmapped_count += 1
            key = ("unmapped", "allergy" if req["kind"] == "allergy" else "restriction", "confirm")
            coverage[key] += int(key not in counted)
            counted.add(key)
            details.append(
                {
                    "guest_id": gid,
                    "requirement_id": str(req["id"]),
                    "category": "unmapped",
                    "need_type": "allergy" if req["kind"] == "allergy" else "restriction",
                    "state": "confirm",
                    "restricted_note": req["description"],
                    "evidence_id": str(req["evidence_id"]),
                    "reason": "normalization_required",
                }
            )
        if profile.get("dietary_status", "unknown") == "unknown" or (
            profile.get("dietary_status") == "has_needs" and not guest_needs and not unmapped
        ):
            unknown_dietary += 1
            coverage[("unknown", "unknown", "unknown")] += 1
            details.append(
                {
                    "guest_id": gid,
                    "category": "unknown",
                    "need_type": "unknown",
                    "state": "unknown",
                    "reason": "dietary_answer_missing",
                    "restricted_note": None,
                    "evidence_id": None,
                }
            )
        elif profile.get("dietary_status") == "no_needs" and not guest_needs and not unmapped:
            coverage[("no_declared_needs", "none", "covered" if state == "confirmed" else "unknown")] += 1
        for need in guest_needs:
            accommodation = menu.get((need["category"], need["need_type"]))
            covered = accommodation["state"] if accommodation else "uncovered"
            if state != "confirmed" and covered == "covered":
                covered = "provisional" if state == "possible" else "unknown"
            key = (need["category"], need["need_type"], covered)
            coverage[key] += int(key not in counted)
            counted.add(key)
            details.append(
                {
                    "guest_id": gid,
                    "category": need["category"],
                    "need_type": need["need_type"],
                    "state": covered,
                    "reason": "documented_accommodation" if accommodation else "no_accommodation",
                    "requirement_id": str(need["requirement_id"]),
                    "evidence_id": str(need["evidence_id"]),
                    "restricted_note": need.get("restricted_note"),
                    "accommodation_evidence_id": str(accommodation["evidence_id"]) if accommodation else None,
                }
            )
    return {
        "generator_version": GENERATOR_VERSION,
        "counts": counts,
        "serving_counts": serving,
        "coverage": [
            {"category": key[0], "need_type": key[1], "state": key[2], "count": count}
            for key, count in sorted(coverage.items())
        ],
        "unknown_dietary_count": unknown_dietary,
        "unmapped_requirement_count": unmapped_count,
        "attendance": people,
        "details": details,
        "disclaimer": DISCLAIMER,
    }
