"""Pure, bounded rooming engine. No model output or free text is executable policy."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

GENERATOR_VERSION = "rooming-v1"
MAX_GUESTS = 250
MAX_BEDS = 500
MAX_NIGHTS = 31
MAX_CANDIDATES = 250_000

HARD_KINDS = {
    "requires_accessibility",
    "requires_own_bed",
    "cannot_share_room",
    "requires_private_room",
    "bed_type",
}
SOFT_KINDS = {"keep_household_near", "prefers_private_room", "prefers_quiet"}


def nights(starts_on: date, ends_on: date) -> list[date]:
    count = (ends_on - starts_on).days
    if not 0 <= count <= MAX_NIGHTS:
        raise ValueError("Rooming requires 0-31 event nights")
    return [starts_on + timedelta(days=index) for index in range(count)]


def guest_nights(guest: dict[str, Any], event_nights: list[date], timezone: str) -> list[date]:
    if guest.get("truth_state") != "confirmed" or not guest.get("arrival") or not guest.get("departure"):
        return []
    zone = ZoneInfo(timezone)
    arrival = guest["arrival"].astimezone(zone).date()
    departure = guest["departure"].astimezone(zone).date()
    return [night for night in event_nights if arrival <= night < departure]


def interval_nights(guest: dict[str, Any], event_nights: list[date], timezone: str) -> list[date]:
    if not guest.get("arrival") or not guest.get("departure"):
        return []
    zone = ZoneInfo(timezone)
    arrival = guest["arrival"].astimezone(zone).date()
    departure = guest["departure"].astimezone(zone).date()
    return [night for night in event_nights if arrival <= night < departure]


def validate_constraint(item: dict[str, Any]) -> None:
    kind = item["kind"]
    hard = item["hard"]
    if kind not in (HARD_KINDS if hard else SOFT_KINDS):
        raise ValueError("Invalid hard or soft constraint kind")
    if not item.get("guest_id"):
        raise ValueError("Constraint requires guest_id")
    if kind == "cannot_share_room" and not item.get("other_guest_id"):
        raise ValueError("Cannot-share requires other_guest_id")
    if kind == "cannot_share_room" and str(item.get("other_guest_id")) == str(item.get("guest_id")):
        raise ValueError("A guest cannot be incompatible with self")
    allowed_bed_types = {"twin", "double", "queen", "king", "bunk", "sofa", "unspecified"}
    if kind == "bed_type" and item.get("details", {}).get("bed_type") not in allowed_bed_types:
        raise ValueError("Invalid required bed type")
    if not 0 <= int(item.get("weight", 0)) <= 100:
        raise ValueError("Invalid preference weight")


def nightly_capacity(
    starts_on: date, ends_on: date, timezone: str, guests: list[dict[str, Any]], beds: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Current demand before a proposal exists; uses the solver's interval rules."""
    event_nights = nights(starts_on, ends_on)
    result = []
    for night in event_nights:
        confirmed = sum(night in guest_nights(guest, event_nights, timezone) for guest in guests)
        possible = sum(
            guest.get("rsvp_status") != "declined"
            and (
                (guest.get("truth_state") != "confirmed" and night in interval_nights(guest, event_nights, timezone))
                or (not guest.get("arrival") and guest.get("rsvp_status") == "possible")
            )
            for guest in guests
        )
        capacity = sum(
            int(bed["capacity"])
            for bed in beds
            if (not bed.get("available_from") or night >= bed["available_from"])
            and (not bed.get("available_until") or night <= bed["available_until"])
        )
        result.append(
            {
                "night": night.isoformat(),
                "confirmed": confirmed,
                "possible": possible,
                "unknown": sum(
                    guest.get("rsvp_status") not in {"possible", "declined"} and not guest.get("arrival")
                    for guest in guests
                ),
                "capacity": capacity,
                "shortfall": max(0, confirmed - capacity),
            }
        )
    return result


def solve(
    *,
    starts_on: date,
    ends_on: date,
    timezone: str,
    guests: list[dict[str, Any]],
    beds: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    locked: list[dict[str, Any]] | None = None,
    fill_unlocked: bool = True,
) -> dict[str, Any]:
    """Return a reproducible valid partial assignment and explicit infeasibility.

    The engine prioritizes hard validity and stable order over global optimality. It
    never calls a model. A candidate budget prevents pathological requests.
    """
    if len(guests) > MAX_GUESTS or len(beds) > MAX_BEDS:
        raise ValueError("Rooming input exceeds bounded engine limits")
    event_nights = nights(starts_on, ends_on)
    for item in constraints:
        validate_constraint(item)
    by_guest: dict[str, dict[str, Any]] = {str(item["id"]): item for item in guests}
    by_bed: dict[str, dict[str, Any]] = {str(item["id"]): item for item in beds}
    if len(by_guest) != len(guests) or len(by_bed) != len(beds):
        raise ValueError("Duplicate guest or bed identity")
    guest_constraints: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sorted(constraints, key=lambda item: str(item["id"])):
        guest_id = str(item["guest_id"])
        if guest_id not in by_guest:
            raise ValueError("Constraint guest not in event")
        if item.get("other_guest_id") and str(item["other_guest_id"]) not in by_guest:
            raise ValueError("Related guest not in event")
        guest_constraints[guest_id].append(item)
    presence = {guest_id: guest_nights(guest, event_nights, timezone) for guest_id, guest in by_guest.items()}
    intervals = {guest_id: interval_nights(guest, event_nights, timezone) for guest_id, guest in by_guest.items()}
    occupied: dict[tuple[str, date], list[str]] = defaultdict(list)
    room_occupied: dict[tuple[str, date], list[str]] = defaultdict(list)
    assigned: dict[tuple[str, date], dict[str, Any]] = {}
    assignment_scores: dict[tuple[str, date], int] = {}
    violations: list[dict[str, Any]] = []
    attempts = 0

    def reject(guest_id: str, bed_id: str, night: date) -> list[str]:
        bed = by_bed.get(bed_id)
        if bed is None:
            return ["BED_NOT_FOUND"]
        reasons: list[str] = []
        if night not in presence.get(guest_id, []):
            reasons.append("GUEST_NOT_CONFIRMED_ON_NIGHT")
        if (bed.get("available_from") and night < bed["available_from"]) or (
            bed.get("available_until") and night > bed["available_until"]
        ):
            reasons.append("BED_UNAVAILABLE")
        occupants = occupied[(bed_id, night)]
        room_id = str(bed["room_id"])
        roommates = room_occupied[(room_id, night)]
        if len(occupants) >= int(bed["capacity"]) or (occupants and not bed["shareable"]):
            reasons.append("BED_CAPACITY")
        own_bed = any(item["kind"] == "requires_own_bed" and item["hard"] for item in guest_constraints[guest_id])
        if occupants and own_bed:
            reasons.append("OWN_BED_REQUIRED")
        if occupants and any(
            item["kind"] == "requires_own_bed" and item["hard"]
            for roommate in occupants
            for item in guest_constraints[roommate]
        ):
            reasons.append("OTHER_GUEST_OWN_BED_REQUIRED")
        for item in guest_constraints[guest_id]:
            if not item["hard"]:
                continue
            if item["kind"] == "requires_accessibility" and not bed["accessible"]:
                reasons.append("ACCESSIBILITY_REQUIRED")
            elif item["kind"] == "requires_private_room" and (roommates or not bed["private_room"]):
                reasons.append("PRIVATE_ROOM_REQUIRED")
            elif item["kind"] == "bed_type" and bed["bed_type"] != item["details"]["bed_type"]:
                reasons.append("BED_TYPE_REQUIRED")
            elif item["kind"] == "cannot_share_room" and str(item["other_guest_id"]) in roommates:
                reasons.append("INCOMPATIBLE_ROOMMATES")
        for roommate in roommates:
            for item in guest_constraints[roommate]:
                if item["hard"] and item["kind"] == "cannot_share_room" and str(item["other_guest_id"]) == guest_id:
                    reasons.append("INCOMPATIBLE_ROOMMATES")
                if item["hard"] and item["kind"] == "requires_private_room":
                    reasons.append("OTHER_GUEST_PRIVATE_ROOM_REQUIRED")
        if bed["private_room"] and roommates:
            reasons.append("ROOM_RESERVED_PRIVATE")
        return sorted(set(reasons))

    def place(
        guest_id: str,
        bed_id: str,
        night: date,
        locked_assignment: bool,
        source: str,
        code: str,
        placement_score: int = 0,
    ) -> None:
        bed = by_bed[bed_id]
        occupied[(bed_id, night)].append(guest_id)
        room_occupied[(str(bed["room_id"]), night)].append(guest_id)
        assigned[(guest_id, night)] = {
            "guest_id": guest_id,
            "bed_id": bed_id,
            "night": night.isoformat(),
            "locked": locked_assignment,
            "source": source,
            "explanation_code": code,
        }
        assignment_scores[(guest_id, night)] = placement_score

    def remove(guest_id: str, night: date) -> None:
        row = assigned.pop((guest_id, night))
        assignment_scores.pop((guest_id, night))
        occupied[(row["bed_id"], night)].remove(guest_id)
        room_occupied[(str(by_bed[row["bed_id"]]["room_id"]), night)].remove(guest_id)

    for item in sorted(locked or [], key=lambda item: (str(item["night"]), str(item["guest_id"]))):
        guest_id, bed_id, night = str(item["guest_id"]), str(item["bed_id"]), item["night"]
        if isinstance(night, str):
            night = date.fromisoformat(night)
        if guest_id not in by_guest or (guest_id, night) in assigned:
            violations.append({"guest_id": guest_id, "night": night.isoformat(), "codes": ["INVALID_LOCK"]})
            continue
        reasons = reject(guest_id, bed_id, night)
        if reasons:
            violations.append({"guest_id": guest_id, "night": night.isoformat(), "codes": reasons})
        else:
            place(guest_id, bed_id, night, True, "locked", "HOST_LOCK")

    def score(guest_id: str, bed: dict[str, Any], night: date) -> int:
        value = 0
        existing = [row for (g, _), row in assigned.items() if g == guest_id]
        if existing and existing[-1]["bed_id"] == str(bed["id"]):
            value += 30  # minimize moves
        household = by_guest[guest_id].get("household_id")
        if household and any(
            by_guest[other].get("household_id") == household for other in room_occupied[(str(bed["room_id"]), night)]
        ):
            value += 20
        for item in guest_constraints[guest_id]:
            if item["hard"]:
                continue
            weight = int(item.get("weight", 0))
            if item["kind"] == "prefers_private_room" and bed["private_room"]:
                value += weight
            elif item["kind"] == "prefers_quiet" and bed["quiet"]:
                value += weight
            elif (
                item["kind"] == "keep_household_near"
                and household
                and any(
                    by_guest[other].get("household_id") == household
                    for other in room_occupied[(str(bed["room_id"]), night)]
                )
            ):
                value += weight
        return value

    unassigned: list[dict[str, Any]] = []
    for night in event_nights:
        if not fill_unlocked:
            continue
        # Hardest guests first, then household and stable guest ID.
        people = sorted(
            (guest_id for guest_id in by_guest if night in presence[guest_id] and (guest_id, night) not in assigned),
            key=lambda guest_id: (
                -sum(item["hard"] for item in guest_constraints[guest_id]),
                str(by_guest[guest_id].get("household_id") or "~"),
                guest_id,
            ),
        )
        for guest_id in people:
            eligible: list[tuple[int, str, dict[str, Any]]] = []
            rejected: Counter[str] = Counter()
            for bed_id, bed in sorted(by_bed.items()):
                attempts += 1
                if attempts > MAX_CANDIDATES:
                    raise ValueError("Rooming candidate budget exceeded")
                reasons = reject(guest_id, bed_id, night)
                if reasons:
                    rejected.update(reasons)
                else:
                    eligible.append((score(guest_id, bed, night), bed_id, bed))
            if eligible:
                best = min(eligible, key=lambda item: (-item[0], item[1]))
                place(guest_id, best[1], night, False, "generated", "VALID_BEST_SCORE", best[0])
            else:
                unassigned.append(
                    {
                        "guest_id": guest_id,
                        "night": night.isoformat(),
                        "codes": sorted(rejected) or ["NO_INVENTORY"],
                        "candidate_failures": dict(sorted(rejected.items())),
                    }
                )
        if any(item["night"] == night.isoformat() for item in unassigned):
            # A greedy dead end is not evidence of global infeasibility. Search the
            # same night with prior nights and host locks fixed, within a hard budget.
            greedy_rows = [dict(assigned[(guest_id, night)]) for guest_id in people if (guest_id, night) in assigned]
            greedy_scores = {
                guest_id: assignment_scores[(guest_id, night)] for guest_id in people if (guest_id, night) in assigned
            }
            for row in reversed(greedy_rows):
                remove(row["guest_id"], night)
            search_limited = False

            def search(index: int, people: tuple[str, ...] = tuple(people), night: date = night) -> bool:
                nonlocal attempts, search_limited
                if index == len(people):
                    return True
                guest_id = people[index]
                candidates: list[tuple[int, str]] = []
                for bed_id, bed in sorted(by_bed.items()):
                    attempts += 1
                    if attempts > MAX_CANDIDATES:
                        search_limited = True
                        return False
                    if not reject(guest_id, bed_id, night):
                        candidates.append((score(guest_id, bed, night), bed_id))
                for placement_score, bed_id in sorted(candidates, key=lambda candidate: (-candidate[0], candidate[1])):
                    place(guest_id, bed_id, night, False, "generated", "VALID_BOUNDED_SEARCH", placement_score)
                    if search(index + 1):
                        return True
                    remove(guest_id, night)
                    if search_limited:
                        return False
                return False

            found = search(0)
            if found:
                unassigned = [item for item in unassigned if item["night"] != night.isoformat()]
            else:
                for row in greedy_rows:
                    place(
                        row["guest_id"],
                        row["bed_id"],
                        night,
                        False,
                        row["source"],
                        row["explanation_code"],
                        greedy_scores[row["guest_id"]],
                    )
                for item in unassigned:
                    if item["night"] == night.isoformat():
                        item["codes"].append("SEARCH_LIMIT" if search_limited else "GLOBAL_INFEASIBLE")
    demand = []
    for night in event_nights:
        demand.append(
            {
                "night": night.isoformat(),
                "confirmed": sum(night in dates for dates in presence.values()),
                "possible": sum(
                    guest.get("rsvp_status") != "declined"
                    and (
                        (guest.get("truth_state") != "confirmed" and night in intervals[guest_id])
                        or (not guest.get("arrival") and guest.get("rsvp_status") == "possible")
                    )
                    for guest_id, guest in by_guest.items()
                ),
                "unknown": sum(
                    guest.get("rsvp_status") not in {"possible", "declined"} and not guest.get("arrival")
                    for guest_id, guest in by_guest.items()
                ),
                "absent": sum(
                    bool(guest.get("arrival")) and night not in intervals[guest_id]
                    for guest_id, guest in by_guest.items()
                ),
                "declined": sum(guest.get("rsvp_status") == "declined" for guest in by_guest.values()),
                "assigned": sum(row["night"] == night.isoformat() for row in assigned.values()),
                "capacity": sum(
                    int(bed["capacity"])
                    for bed in beds
                    if (not bed.get("available_from") or night >= bed["available_from"])
                    and (not bed.get("available_until") or night <= bed["available_until"])
                ),
            }
        )
    soft_conflicts: list[dict[str, Any]] = []
    for night in event_nights:
        households: dict[str, set[str]] = defaultdict(set)
        counts: Counter[str] = Counter()
        for row in assigned.values():
            if row["night"] != night.isoformat():
                continue
            household = by_guest[row["guest_id"]].get("household_id")
            if household:
                households[str(household)].add(str(by_bed[row["bed_id"]]["room_id"]))
                counts[str(household)] += 1
        for household, rooms in sorted(households.items()):
            if counts[household] > 1 and len(rooms) > 1:
                soft_conflicts.append(
                    {
                        "household_id": household,
                        "night": night.isoformat(),
                        "code": "HOUSEHOLD_NOT_TOGETHER",
                        "rooms_used": len(rooms),
                    }
                )
    final_score = 0
    previous_bed: dict[str, str] = {}
    household_rooms: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in sorted(assigned.values(), key=lambda item: (item["night"], item["guest_id"])):
        guest_id, bed_id = row["guest_id"], row["bed_id"]
        bed = by_bed[bed_id]
        if previous_bed.get(guest_id) == bed_id:
            final_score += 30
        previous_bed[guest_id] = bed_id
        for item in guest_constraints[guest_id]:
            if item["hard"]:
                continue
            if item["kind"] == "prefers_private_room" and bed["private_room"]:
                final_score += int(item["weight"])
            elif item["kind"] == "prefers_quiet" and bed["quiet"]:
                final_score += int(item["weight"])
        household = by_guest[guest_id].get("household_id")
        if household:
            household_rooms[(row["night"], str(household), str(bed["room_id"]))].append(guest_id)
    for occupants in household_rooms.values():
        if len(occupants) > 1:
            final_score += 20 * (len(occupants) - 1)
            for guest_id in occupants:
                final_score += sum(
                    int(item["weight"])
                    for item in guest_constraints[guest_id]
                    if not item["hard"] and item["kind"] == "keep_household_near"
                )
    return {
        "generator_version": GENERATOR_VERSION,
        "assignments": sorted(assigned.values(), key=lambda row: (row["night"], row["guest_id"])),
        "unassigned_guests": unassigned,
        "hard_violations": violations,
        "soft_conflicts": soft_conflicts,
        "soft_score": final_score,
        "demand": demand,
        "candidates_evaluated": attempts,
    }
