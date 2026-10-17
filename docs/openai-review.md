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
attempts instead of reporting only the successful retests. Historical iterations
have different recorded hashes; the final qualification checks one frozen set of
skill files across all seven phases. This is development evidence, not a held-out
reliability benchmark or a claim that every harness behaves identically.

The suites cover invitations and corrections, household authority, opt-outs,
private requirements, nightly rooming, meal intervals, vendor quote changes,
research freshness, conflicting schedules, ride capacity/permissions, late
incidents, uncertain-send reconciliation, scheduler readback/cancellation and
export/restore integrity. All external actions are synthetic. Real delivery,
bookings, payments, production schedulers and independent human hosting acceptance
are outside the evidence. Claude installation is tested; Claude model behavior
is not claimed. Other documented harnesses use the portable installer.

## Privacy boundary

The owner approved removing property access codes from Eventer's workflow.
Eventer now directs guests to the property's secure check-in channel, and keeps
codes out of drafts, evidence excerpts, records and exports. Synthetic adversarial
tests check that supplied code-like canaries do not enter generated artifacts.
This responds to the guideline restriction on access credentials and authentication
secrets; it is not an OpenAI decision or a certification of directory compliance.
[Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines).

Accommodation requirements also need data minimization and appropriate consent.
The privacy policy explains the intended handling. A fixture's privacy-screen
pass does not establish consent or legal compliance for a real event.

## Contact draft

> I maintain Eventer, an MIT-licensed, skills-only event-hosting plugin at
> https://github.com/bobuel/eventer-plugin. It uses the user's existing AI harness
> and tools, without an Eventer service. The repository includes reproducible
> synthetic hosting evaluations, preserved failure/retest reports, native Codex
> and Claude installation checks, and privacy/listing assets. Property access
> codes stay outside Eventer; guests use the property's secure check-in channel.
> I'd welcome feedback on directory suitability and the package's review
> readiness. Please see docs/verification.md for the exact tested scope,
> preserved development failures and limitations.

This is an unsent draft. It deliberately does not claim approval or universal
behavioral reliability.

## Submission route

Open [Plugins](https://platform.openai.com/plugins),
select the appropriate organization/project and verified developer identity,
upload the versioned ZIP, resolve metadata/skill findings and submit for review.
The maintainer's verified identity and account permissions have not been inspected.
The manifest's public GitHub handle does not establish publisher verification.
Approval precedes directory publication. Skills-only packages do not require the
MCP-specific test-case/demo materials. Follow the current
[official submission instructions](https://developers.openai.com/plugins/deploy/submission).

Eventer's local Python helpers require desktop execution in the OpenAI directory.
Both supported manifests declare `requires_local_executor: true`. There is no
local MCP server. If the portal rejects that field, contact your OpenAI
representative with the submitting organization ID to confirm access, as described
in the [desktop-only instructions](https://developers.openai.com/plugins/deploy/desktop-only).
This OpenAI declaration does not change portable installation in other harnesses.

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
