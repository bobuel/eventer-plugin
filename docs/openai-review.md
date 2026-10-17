# OpenAI review brief

Prepared October 17, 2026 for the maintainer. No contact, upload, submission,
directory approval or publication has been performed through the OpenAI portal.

## Product and user journey

Eventer helps one host organize a multi-day group event: collect a brief, reconcile
guest replies, propose rooms/meals/rides, compare quotes, handle changes, draft
authorized communications, and close with a portable archive. Twelve skills and
offline Python helpers run inside the user's existing harness. GitHub hosts the
MIT-licensed package. There is no Eventer backend or mandatory connector.

Source: https://github.com/bobuel/eventer-plugin

The candidate includes consistent portable/Codex listing metadata, a square SVG
icon, support and privacy links, a reproducible ZIP and public evals. Local
validation is a preflight; it cannot certify OpenAI's scans or policy approval.

## Verification to present

Use [the verification record](verification.md) and the versioned reports in
`evals/reports/`. They separate offline tests, native installation, simulated
hosting behavior and artifact review. The fresh qualification preserves failed
attempts instead of reporting only the successful retests. Different skill
iterations have different recorded hashes; this is development evidence, not a
held-out reliability benchmark or a claim that every harness behaves identically.

The suites cover invitations and corrections, household authority, opt-outs,
private requirements, nightly rooming, meal intervals, vendor quote changes,
research freshness, conflicting schedules, ride capacity/permissions, late
incidents, uncertain-send reconciliation, scheduler readback/cancellation and
export/restore integrity. All external actions are synthetic. Real delivery,
bookings, payments, production schedulers and independent human hosting acceptance
are outside the evidence. Claude installation is tested; Claude model behavior
is not claimed. Other documented harnesses use the portable installer.

## Policy question before directory submission

The existing check-in workflow supports a host-approved, restricted draft
containing a property door code. The synthetic live-event evaluation tests that
behavior; public guest digests must exclude the code. OpenAI's current guidelines
restrict collecting or processing access credentials and authentication secrets.
We interpret property access codes as a potential conflict that requires removal
from the workflow or clarification from OpenAI. This is our interpretation, not
an OpenAI decision on Eventer. Do not describe directory compliance as established.
[Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines).

Accommodation requirements also need data minimization and appropriate consent.
The privacy policy explains the intended handling. A fixture's privacy-screen
pass does not establish consent or legal compliance for a real event.

## Contact draft

> I maintain Eventer, an MIT-licensed, skills-only event-hosting plugin at
> https://github.com/bobuel/eventer-plugin. It uses the user's existing AI harness
> and tools, without an Eventer service. The repository includes reproducible
> synthetic hosting evaluations, preserved failure/retest reports, native Codex
> and Claude installation checks, and privacy/listing assets. Before submitting,
> I'd like to clarify whether a host-approved private draft containing a property
> door code falls under the restricted access-credentials rule. We can route
> access instructions through the property's secure channel instead. Please see
> docs/verification.md for the exact tested scope and limitations.

This is an unsent draft. It deliberately does not claim approval or universal
behavioral reliability.

## Submission route

After resolving the policy question, open [Plugins](https://platform.openai.com/plugins),
select the appropriate organization/project and verified developer identity,
upload the versioned ZIP, resolve metadata/skill findings and submit for review.
The maintainer's verified identity and account permissions have not been inspected.
The manifest's public GitHub handle does not establish publisher verification.
Approval precedes directory publication. Skills-only packages do not require the
MCP-specific test-case/demo materials. Follow the current
[official submission instructions](https://developers.openai.com/plugins/deploy/submission).

For local reproduction:

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate.py
python evals/run.py offline
python scripts/package.py
```

For behavioral reproduction, use the bounded, observed workflows in
[evals/README.md](../evals/README.md). Do not give evaluated agents the graders or
expected answers. A reviewer must read the actual host/guest artifacts separately
from the automatic score.
