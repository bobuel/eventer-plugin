"""Pure interval, audience and transportation checks; no booking or safety claims."""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .errors import DomainError
from .meal_engine import instant

VERSION = "transport-v1"


def local_instant(value: str | datetime, timezone: str) -> datetime:
    """Require a real wall time and explicit offset, including both DST folds."""
    try:
        supplied = datetime.fromisoformat(value) if isinstance(value, str) else value
        result = instant(supplied)
        local = result.astimezone(ZoneInfo(timezone))
        if supplied.utcoffset() != local.utcoffset() or supplied.replace(tzinfo=None) != local.replace(tzinfo=None):
            raise ValueError("Offset does not match event-local time")
        return result
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise DomainError(
            "VALIDATION_ERROR", "Use an event-local timestamp with its correct explicit UTC offset"
        ) from exc


def overlaps(a: Any, b: Any, c: Any, d: Any, buffer: int = 0) -> bool:
    pad = timedelta(minutes=buffer)
    return instant(a) < instant(d) + pad and instant(c) < instant(b) + pad


def audience(item: dict[str, Any], guests: list[dict[str, Any]], segments: list[dict[str, Any]]) -> dict[str, Any]:
    selected = {str(g) for g in item.get("guest_ids", [])}
    opted_out = {str(g) for g in item.get("opt_out_ids", [])}
    rows = []
    for guest in sorted(guests, key=lambda g: str(g["id"])):
        gid = str(guest["id"])
        reason = "confirmed_present"
        if item.get("status") == "cancelled":
            reason = "item_cancelled"
        elif gid in opted_out:
            reason = "explicit_opt_out"
        elif item.get("audience_rule") == "selected" and gid not in selected:
            reason = "outside_selected_audience"
        elif guest["rsvp_status"] != "confirmed":
            reason = "attendance_unconfirmed"
        elif not any(
            str(s["guest_id"]) == gid
            and s["truth_state"] == "confirmed"
            and s["active"]
            and instant(s["arrival_at"]) <= instant(item["starts_at"])
            and instant(s["departure_at"]) >= instant(item["ends_at"])
            for s in segments
        ):
            reason = "outside_attendance_window"
        rows.append({"guest_id": gid, "eligible": reason == "confirmed_present", "reason": reason})
    return {"members": rows, "guest_ids": [r["guest_id"] for r in rows if r["eligible"]]}


def plan_ride(
    ride: dict[str, Any], vehicle: dict[str, Any], existing: list[dict[str, Any]], travelers: list[dict[str, Any]]
) -> dict[str, Any]:
    start, end = instant(ride["starts_at"]), instant(ride["ends_at"])
    if end <= start or (end - start).total_seconds() > 86400:
        raise DomainError("VALIDATION_ERROR", "Ride interval must be positive and at most 24 hours")
    driver = str(ride["driver_id"])
    if not vehicle["driver_authorized"] or str(vehicle["driver_id"]) != driver:
        raise DomainError("FORBIDDEN", "Vehicle requires an explicitly authorized driver")
    for other in existing:
        if other.get("status") == "cancelled" or str(other.get("id")) == str(ride.get("id", "")):
            continue
        if overlaps(start, end, other["starts_at"], other["ends_at"], ride.get("buffer_minutes", 0)):
            if str(other["vehicle_id"]) == str(ride["vehicle_id"]) or str(other["driver_id"]) == driver:
                raise DomainError("VALIDATION_ERROR", "Driver or vehicle overlaps another ride, including buffer")
            if driver in [str(g) for g in other.get("guest_ids", [])]:
                raise DomainError("VALIDATION_ERROR", "Driver is already a passenger on another ride")
    assigned: list[str] = []
    waitlist: list[dict[str, str]] = []
    child_used = 0
    for gid in sorted({str(g) for g in ride["guest_ids"]}):
        matching = [t for t in travelers if str(t["guest_id"]) == gid]
        record = next(
            (t for t in matching if t["origin"] == ride["origin"] and t["destination"] == ride["destination"]),
            matching[0] if matching else None,
        )
        reason = None
        if gid == driver:
            reason = "driver_not_passenger"
        elif record and record.get("rsvp_status", "confirmed") != "confirmed":
            reason = "attendance_unconfirmed"
        elif not record or not record.get("pickup_permission"):
            reason = "pickup_permission_missing"
        elif instant(record["available_from"]) > start or instant(record["available_until"]) < end:
            reason = "outside_travel_window"
        elif record["origin"] != ride["origin"] or record["destination"] != ride["destination"]:
            reason = "pickup_or_destination_mismatch"
        elif record.get("accessible_required") and not vehicle["accessible"]:
            reason = "vehicle_inaccessible"
        elif record.get("child_seat_required") and child_used >= vehicle["child_seats"]:
            reason = "child_seat_unavailable"
        elif any(
            o.get("status") != "cancelled"
            and overlaps(start, end, o["starts_at"], o["ends_at"], ride.get("buffer_minutes", 0))
            and (gid == str(o["driver_id"]) or gid in [str(g) for g in o.get("guest_ids", [])])
            for o in existing
        ):
            reason = "guest_ride_overlap"
        elif len(assigned) >= vehicle["passenger_seats"]:
            reason = "capacity_waitlist"
        if reason:
            waitlist.append({"guest_id": gid, "reason": reason})
        else:
            assigned.append(gid)
            child_used += int(bool(record and record.get("child_seat_required")))
    return {
        "generator_version": VERSION,
        "assigned": assigned,
        "waitlist": waitlist,
        "passenger_seats": vehicle["passenger_seats"],
        "driver_seat_excluded": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": "Host-recorded permissions and equipment; no transport safety certification or booking.",
    }
