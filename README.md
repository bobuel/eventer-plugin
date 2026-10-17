# Eventer

**Plan and run a group event with the AI harness you already use.**

Eventer is a portable plugin: twelve skills, practical templates, offline planning
helpers, and a public evaluation suite. It helps a host turn invitations and guest
replies into accommodation, meals, vendor decisions, an agenda, rides, and a clear
plan for the day. It follows changes through to wrap-up.

No Eventer account, server, database, subscription, or background process. Your
harness supplies the model and connected tools. Your event records stay in a folder
you choose. Existing model and connected-service charges still apply. Your harness
and model provider may process files you share; see the [privacy policy](PRIVACY.md).

## Start here

In Claude Code, add the marketplace with `/plugin marketplace add bobuel/eventer-plugin`,
then install with `/plugin install eventer@eventer-plugins`.

Install with [the instructions for your harness](docs/installation.md), then ask:

> Use Eventer to help me host a three-day weekend for 12 people. Start with the
> event brief, the information we need from guests, and a useful next step.

For an existing event:

> Use Eventer to reconcile these replies, show what changed, and identify which
> room assignments, meal counts and ride plans need review.

The host chooses the folder and authority. Missing email or search access produces
useful drafts and research checklists. Scheduling uses your harness's existing
scheduler when available; installing skills alone does not create recurring work.

## What is included

| Skill | What it helps you produce |
|---|---|
| `eventer` | A coherent next step across the full event journey |
| `eventer-setup` | Event brief, records and connected-tool checklist |
| `eventer-guests` | Evidence-backed attendance, requirements and corrections |
| `eventer-communications` | Targeted drafts, authorized sends and receipt reconciliation |
| `eventer-lodging` | Per-night rooming proposals with unresolved conflicts |
| `eventer-meals` | Meal counts, dietary unknowns and documented accommodations |
| `eventer-vendors` | Quote comparisons, commitments and remaining balances |
| `eventer-research` | Sourced options checked against group constraints |
| `eventer-schedule-transport` | An audience-aware agenda and capacity-checked rides |
| `eventer-readiness-live` | Readiness review, change impacts and a safe guest digest |
| `eventer-wrap-up` | Outstanding actions, export and retention review |
| `eventer-setup-scheduling` | A verified schedule using an existing scheduler |

Install the collection together: specialist skills share the coordinator's
operating contract and helper library. The entrypoints stay short; references and
scripts are loaded only when relevant.

## Try the offline helpers

Python 3.12+ is needed only for the helpers and evaluation tooling. On Windows,
install timezone data; using the runtime requirements works on every platform:

```sh
python -m pip install -r requirements.txt
python -B skills/eventer/scripts/eventer.py rooming --input examples/inputs/rooming.json
python -B skills/eventer/scripts/eventer.py quote-diff --input examples/inputs/quote-diff.json
```

Planning helpers read JSON and return proposals or validation results. The archive
helper also creates explicitly requested, verified local copies. They do not contact
providers, send messages, book transport, or make payments. See the
[input contracts](skills/eventer/references/helpers.md) and
[synthetic complete journey](examples/journey/request.md).

## Evidence and limits

See [verification status](docs/verification.md) for executed checks and gaps.
The [OpenAI review brief](docs/openai-review.md) separates public installation
from directory submission and records the remaining policy question.
The [evaluation suite](evals/README.md) distinguishes deterministic tests from
actual model behavior and human review. A schema check is not a successful event.

Eventer is host-operated. Local files are not a multi-user authorization system,
and arbitrary providers cannot guarantee exactly-once delivery. Keep uncertain
actions pending until reconciled. Reviewed proposals do not establish real-world
availability, accommodation safety, bookings or delivery.

## Development

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate.py
python evals/run.py offline
python scripts/package.py
```

GitHub Actions runs offline checks on Windows, Linux and macOS without secrets or
provider calls. Actual harness evaluations are opt-in, bounded and reproducible.
See [contributing](CONTRIBUTING.md), [security](SECURITY.md),
[extraction provenance](docs/provenance.md) and [MIT license](LICENSE).
