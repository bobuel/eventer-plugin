# Extraction and scope

Extracted from bobuel/eventer at commit
`ba3e1d0e7347a0a7782146230403c23c09785a88`, under the owner's MIT publication instruction.
No original Git history, production exports, credentials or deployment settings
are included. The service repo and its infrastructure are not changed.

Reused: rooming_engine.py, meal_engine.py, vendor_engine.py, transport_engine.py,
research.py and six explicitly synthetic fixtures. Engines retain domain behavior;
service-bound DomainError imports now refer to a local error type. New CLI input
validation and plugin-specific regression tests sit around these engines.

Adapted: RSVP evidence/extraction scenarios; rooming/meal/transport/quote invariants;
approval, privacy, duplicate/uncertain-send and Gate B/C journey scenarios.
Service-only tests omitted: PostgreSQL isolation, migrations, transactional outbox,
web authentication, billing/entitlements, Railway health and backup restoration.
Their guarantees are not claimed by a filesystem-based plugin.

New: capability fallbacks, skill routing, scheduler setup/readback, portable
installation/update/removal, fresh-session resume and missing-resource handling.
Third-party dependencies are installed separately, not vendored. Runtime tzdata
provides timezone information (Apache-2.0 package, public-domain IANA data); test
dependencies are pytest (MIT), PyYAML (MIT), and jsonschema (MIT). Preserve their
upstream notices when redistributing them; the release does not bundle them.
