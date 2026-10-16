# Event records

Write durable JSON, JSONL and Markdown as UTF-8 explicitly, including on Windows.
Read back saved files with that encoding before reporting completion. Check that
every source reference resolves, including receipt IDs used by blockers or notices.

Keep `brief.md`, `event.json`, `evidence/`, `proposals/`, `decisions.jsonl`,
`communications.jsonl`, and `summary.md` in a private event folder. Create only what
the event currently needs. These are working artifacts, not an installed database.

`event.json`: schema_version=1, event_id, revision, name, timezone, starts_on,
ends_on, host, capabilities, guests, requirements, and unresolved. Dates are ISO
dates; unknown dates are null. An initialized dated event requires an IANA timezone.
Each guest has id, name, rsvp_status (unknown/possible/confirmed/declined),
truth_state (unknown/proposed/confirmed), arrival/departure (offset timestamps or
null), precision (unknown/date/part_of_day/exact_time), and evidence_ids.
Never invent exact times from date-only replies. Maintain date-only claims
separately until a task requires and obtains a precise interval.

Evidence entries: id, event_id, source_type, source_reference, received_at, actor,
authority, exact excerpt, sensitivity. Raw source files remain private. Claims
reference evidence; excerpt matching alone does not prove semantic support.
Use `exact_excerpt` for the quoted text. Reuse a supplied `source_id` verbatim as
the evidence `id`, including when correcting attendance. Index a structured
document's original source id before adding more granular citations. Renaming a
source breaks continuity with later replies and corrections. Run `audit-records`
on saved records and resolve its issues before reporting the update complete.

Structured RSVP claim: guest_id, field (attendance/requirement/plus_one),
evidence_span, source_id; attendance adds status, arrival_day, departure_day,
precision and correction; requirements add kind (dietary/allergy/sleep/mobility/transport/other),
sensitivity (operational/personal/sensitive), required (true/false/null), and text.
Plus-one adds plus_one_name and ambiguous=true. A response includes claims and
ambiguities. Declining need not invent dates. Part-of-day expressions retain text.

Decisions: event_id, revision, action, proposal_reference, decided_by, decided_at,
authority_reference and supersedes. Only actual user evidence supplies authority.
Every proposal includes input_revision; changed inputs require recalculation/review.

Communications: action_id, fingerprint, event_id, input_revision, recipients,
content_reference, approval_reference, attempt_at, state, provider_reference,
observed_at. A tool timeout after submission stays uncertain until reconciled.

Summary: upcoming milestones, confirmed arrangements, pending decisions,
unresolved questions, affected/stale plans and next actions with owners. Do not
store credentials. Exclude event folders from Git and cloud sync unless the host
explicitly chooses a suitable private destination.
