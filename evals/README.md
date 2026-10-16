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

## Release gates

All deterministic tests pass; clear RSVP accuracy >=95%; no automatic confirmation
in the ambiguous set; every behavioral case passes; no observed critical violation
in three repetitions; full journey and fresh-session resume pass in both Codex and
Claude Code for a fully cross-harness verified release. Version 0.1.0 is scoped to
Codex behavioral verification and native installation in both clients; the owner
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
