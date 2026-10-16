# Offline helper contracts

Run from anywhere using the installed path to `skills/eventer/scripts/eventer.py`:

```sh
python -B /path/to/skills/eventer/scripts/eventer.py rooming --input rooming.json --output proposal.json
```

Use Python 3.12+; install `tzdata` if the OS lacks IANA timezone data (notably
Windows). `-B` avoids writing caches into a read-only plugin installation. JSON
can also be piped to stdin. Output is `{ok: true, result: ...}`; failures exit 2
with `{ok: false, error, message}` on stderr. Output paths must be new files.
No network calls, credential reads, state commits or external actions occur.
The complete collection must be installed together; other skills use this helper.

| Operation | JSON input | Result |
|---|---|---|
| validate | event.json from setup template | Structural validation, not proof of truth |
| rooming | starts_on, ends_on, timezone, guests, beds, constraints; optional locked, fill_unlocked | Assignments, demand, violations, unassigned guests |
| meals | meal, guests, overrides, profiles, needs, accommodations, requirements | Counts and coverage, including unknowns |
| quote | currency, items, tax, fees; optional documented terms | Exact-decimal normalized quote |
| quote-extract | content | Conservative candidate only; review required |
| quote-diff | before, after (raw quote inputs) | Semantic differences and comparability |
| balance | currency, total, payments [{id, currency, amount}] | Reported paid, balance and overpayment; no money movement |
| research | candidate, constraints, now | Eligibility, freshness and rejection reasons |
| local-time | value, timezone | UTC instant or invalid DST offset error |
| audience | item, guests, segments | Eligible audience and exclusions |
| transport | ride, vehicle, existing, travelers | Assignments and deterministic waitlist |
| schedule-check | items [{id, starts_at, ends_at, guest_ids}] | Overlapping audiences |
| fingerprint | event_id, revision, recipients, content | Stable hash; never authorization |

All timestamps require explicit UTC offsets. Financial amounts are decimal strings.
IDs must be stable within the event. Duplicate guest identities are rejected.
Use the ready-to-run JSON files in the repository's `examples/inputs/` as input
templates. Their synthetic outputs are not records of real bookings or sends.

## Rooming

Guests: id, household_id, truth_state, rsvp_status, arrival, departure. Only
confirmed intervals become assignments. Beds: id, room_id, capacity, shareable,
accessible, private_room, quiet, bed_type; optional available_from/available_until
(inclusive available nights). Guest departure dates are exclusive lodging nights.
Constraints: id, guest_id, kind, hard, weight, details; optional other_guest_id.
Hard kinds: requires_accessibility, requires_own_bed, requires_private_room,
cannot_share_room, bed_type (details.bed_type). Soft kinds: keep_household_near,
prefers_private_room, prefers_quiet. Locks: guest_id, bed_id, night.
Limits: 250 guests, 500 beds, 31 nights, bounded search. Inspect search-limit and
unassigned explanations; a partial result is never a complete plan.

## Meals

Meal: service_start, service_end, timezone, status, serving_categories. Guests add
name and precision. Overrides: guest_id, response (in/out/uncertain), evidence_id.
Profiles: guest_id, serving_category, dietary_status (unknown/no_needs/has_needs).
Needs: guest_id, requirement_id, category, evidence_id, need_type (preference/restriction/allergy).
Accommodations: category, need_type, state (covered/provisional/confirm/uncovered/unknown), evidence_id. Requirements: id,
guest_id, kind, description, evidence_id. Keep individual rows private; share aggregates where appropriate.

## Transport and research

Ride: id, vehicle_id, driver_id, starts_at, ends_at, origin, destination, guest_ids,
buffer_minutes. Vehicle: driver_id, driver_authorized, passenger_seats, accessible,
child_seats. Travelers: guest_id, origin, destination, available_from,
available_until, pickup_permission; optional rsvp_status, accessible_required,
child_seat_required. Existing rides use the ride fields plus status.

Research candidate: source_url (public HTTPS), retrieved_at; optional accessible,
distance_km, travel_minutes, max_group_size, minimum_age. Constraints accept only
accessible_required, max_distance_km, max_travel_minutes, group_size, minimum_age.
The helper checks URL shape, not DNS or source authenticity; it never fetches URLs.
