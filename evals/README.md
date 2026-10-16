# Evaluation suite

This repository ships both regression tests and real harness evaluation tooling.
Offline passing results must never be presented as proof of model behavior.

## Run

```sh
python -m pip install -r requirements-dev.txt
python evals/run.py offline
python evals/run.py harness --harness codex --suite rsvp
python evals/run.py harness --harness codex --suite behavior
python evals/run.py harness --harness codex --suite critical --repeats 3
python evals/run.py harness --harness codex --suite journey
python evals/hosting.py harness --harness codex --package full-weekend --run .eval-runs/weekend-run
python evals/hosting.py harness --harness codex --package correspondence --run .eval-runs/mail-run
python evals/hosting.py harness --harness codex --package live-operations --run .eval-runs/live-run
```

Replace `codex` with `claude` for Claude Code. Use `--executable /absolute/path`
when the CLI is not on PATH. Use the harness's existing subscription login. The
runner removes ambient OpenAI and Anthropic API-key variables; it never discovers
or copies secrets. Model runs consume the existing harness allowance. Each run is
bounded by `--timeout` (600 seconds default); repeats are limited to three. No
model runs execute in ordinary CI.

Private local artifacts go under ignored `.eval-runs/`: reports, generated event
files, stdout traces, and errors. Publish only reviewed, sanitized reports. The
runner does not upload these automatically. It records the exact skill content
hash and CLI version; inspect the trace for the resolved model and tool activity.

## What is tested

- **Offline:** adapted engine assertions, CLI boundaries, install/update/remove,
  package metadata, complete resource loading, reproducibility and grader failures.
- **RSVP:** 12 clear and 6 ambiguous original synthetic messages, exact evidence
  spans, identity, requirement categories, dates and non-confirmation of ambiguity.
- **Behavior:** 24 requests covering a useful output and a boundary for each skill.
  Expected results stay in the parent grader, not in the agent's workspace.
- **Critical:** repeated privacy, authority, uncertainty, correction, resume,
  unavailable-tool and scheduling decisions.
- **Journey:** real event files produced by the installed collection, actual helper
  calls, fake mail timeout/reconciliation, fake scheduler create/read/cancel/read,
  wrap-up and a fresh process resuming from files after an arrival correction.

The journey simulator intentionally records every send attempt, including retries.
A blind retry creates a duplicate and fails the grader. It never calls a provider.
Expected artifacts are graded after execution. The agent receives raw inputs and
user requests, not solution files, grader code, or previous conclusions.

The runner installs the complete portable skill collection in an isolated work
folder. Native plugin installation is a separate release check. Instructions tell
the agent to remain inside its workspace; the host harness controls sandboxing.
This is not an adversarial security sandbox against an unrestricted agent.

## Full hosting packages

The additional [packages](packages/coverage.json) begin with a 24-person CSV,
raw replies, host authority and source documents. They require the installed
skills to produce usable event records and run the actual offline helpers.

| Package | Phases and principal checks |
|---|---|
| `full-weekend` | Setup, household/partial RSVP truth, nightly rooming, private meal needs, limited rides, quotes and reported deposit, one authorized send and daily review; fresh-session cancellations and withdrawn accessible inventory; closeout, duplicate receipt reconciliation, scheduler cancellation, export and restoration |
| `correspondence` | Cross-event claims, unauthorized household reply, tentative guests, plus-one, injection, duplicate evidence, timeout and bounce; verified address correction, opt-out before reminder, duplicate/out-of-order delivery events |
| `live-operations` | Multiple vendor quotes and price correction, missing terms, sourced research constraints/freshness, overlapping agenda and future check-in dependency; vendor delay, cancelled activity, targeted notice, private check-in code and unapproved quantity increase |

Each phase runs in a fresh harness process. Sources and installed skills are
hashed; prior records and observation logs are snapshotted before the next phase.
The grader compares guest facts, individual meal attendees, bed-night constraints,
authorized recipients/content, actual helper inputs/results, scheduler arguments,
receipt states and restored file hashes. It does not trust a model's assertion
that a tool ran or a plan is valid. The synthetic tool journal is kept outside the
agent's working folder; the contract prohibits editing or reading it. This remains
an instruction boundary, not OS-level isolation from an unrestricted agent.

`hosting.py harness` supports Codex or Claude using the existing runner and login.
It stops on a failed phase and retains the evidence. The default phase timeout is
900 seconds, configurable up to 3600. It does not retry a failed model run. For a
different harness, or fresh subagents, stage and grade each phase manually:

```sh
python evals/hosting.py prepare --run .eval-runs/my-run --package full-weekend --phase 1
# Give only the generated prompt-1.txt to a fresh agent. Wait for completion.
python evals/hosting.py grade --run .eval-runs/my-run --package full-weekend --phase 1
# Inspect the result, then repeat prepare/grade for phases 2 and 3 with fresh agents.
```

Do not give the evaluated agent `expected.json`, grader code, previous model
answers or parent reports. Do not repair its files manually and call the result a
model pass. Preserve failed runs; use a new run directory after a skill correction.
The JSON report records source, skill and grader hashes. Unit-test reference
outputs are explicitly synthetic test constructions, not model behavior evidence.
Regrading an earlier phase uses its saved event snapshot and journal prefix,
not the later session's records. The first grade is retained as
`grade-N.original.json` when grading again.

Automated passing and independent artifact review are separate. `overall_passed`
remains false in automatic reports. Record a separate review with evidence for
host readability, source grounding, actionable next steps, audience privacy and
honest execution claims. Owner acceptance requires the owner's own review.

The declared coverage is finite. It does not test real email delivery, live
bookings/payments, simultaneous cohost writes, every attachment format, every
provider or every harness. A passing simulation is not proof of those behaviors.
The [historical Luna development report](reports/hosting-luna.json) includes
failures and incomplete attempts. The [0.1.1 report](reports/hosting-luna-0.1.1.json)
passes all seven phases with separate artifact review, including one corrective
follow-up and documented grader repairs. Neither is a held-out benchmark or a
reliability estimate. A complete hosting scenario pass requires every package
phase to pass both automatic invariants and artifact review.

## Release gates

All deterministic tests pass; clear RSVP accuracy >=95%; no automatic confirmation
in the ambiguous set; every behavioral case passes; no observed critical violation
in three repetitions; full journey and fresh-session resume pass in both Codex and
Claude Code for a fully cross-harness verified release. Versions 0.1.0 and 0.1.1 are
scoped to Codex behavioral verification and native installation in both clients; the owner
authorized completion without waiting for Claude authentication. The maintainers
also inspect actual files for readability, source
grounding and usefulness. Missing authentication, denied tools or absent CLI means
blocked verification, not a pass and not a zero-quality model score.

The 24-case behavior grader checks returned artifacts/decisions. The integrated
journey separately inspects real files and the mock action ledger. Neither proves
real-world provider delivery or user acceptance. Do not infer measured coverage
beyond these scenarios.

`traceability.json` maps source assertions to preserved, adapted and excluded
service tests. Five pure engines and six original synthetic fixtures are reused.
Service isolation, payments, authenticated web pages and database recovery are
deliberately not plugin guarantees.

## Human artifact review

Inspect the journey's brief, summary, agenda, digest, rooming/meal tables,
communications ledger and wrap-up. Confirm that a host can identify what is
confirmed, what changed, why a plan is blocked, and what to do next. Check that a
guest-facing digest contains no private requirements. Record the review separately
from automatic scores and owner acceptance.
