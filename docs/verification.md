# Verification record

The original 0.1.0 results below describe the narrower suite available at release.
A later coverage audit found that its journey grader could accept corrupted
recipients, assignments, scheduler scope and meaningless prose. Those historical
scores must not be read as comprehensive hosting verification. The graders now
check those invariants, with mutation tests for the previously accepted failures.

The repository now also includes three [full hosting packages](../evals/README.md#full-hosting-packages)
covering 24 synthetic guests across seven phases. Their independently observed
actions, saved records, fresh-session changes and export restoration are evaluated
separately from prose quality. Current Luna findings and exact tested content hashes
are recorded in [the hosting report](../evals/reports/hosting-luna.json).

## Current hosting evaluation findings

The expanded offline suite passes 136 tests locally on Windows, and all twelve
skills pass package validation. These deterministic results include negative
grader tests and do not imply model success.

The development Luna run attempted all seven phases with fresh subagents. Only
the full-weekend setup and change phases passed both automatic checks and the
implementing parent's artifact review. This is **not an overall behavioral pass**.
The review is separate from the evaluated agents, but is not human acceptance or
a blinded external assessment.

- Correspondence preserved the corrected opt-out in the retest, but malformed
  send arguments and a renamed evidence source still failed. The simulator also
  accepted invalid arguments; it now rejects them before creating a receipt.
- Live operations correctly calculated quotes and changed the agenda. Its final
  check-in draft withheld the code needed for the host to approve the complete
  message, so the phase failed despite correct send scope and receipt readback.
- Closeout reconciled the duplicate receipt and cancelled the schedule. The parent
  stopped the attempt with export/restore unfinished. Its premature completion
  claim failed artifact review.

The report retains failed checks, original grades, reviewed artifact hashes,
protocol defects and the exact installed skill versions. Changes made after those
runs are explicitly marked as not behaviorally retested. Main contains these
unreleased improvements; the published and installed 0.1.0 version is unchanged.

## Historical 0.1.0 release

This release contains the full twelve-skill collection and offline helpers. Actual
model behavior was evaluated in Codex. Claude Code installation was verified;
Claude model behavior and other harness behavior are outside the verified scope.

| Area | Observed result |
|---|---|
| Offline domain, helper, installer, package and grader tests | 87 passed locally, in a fresh public clone, and in Windows/Linux/macOS CI; Python 3.12 |
| Codex RSVP extraction | 12/12 clear and 6/6 ambiguous cases passed |
| Codex skill behavior | 24/24 cases passed |
| Codex critical behavior | 14/14 cases in each of three runs; zero critical failures under the corrected grader |
| Codex integrated journey | Initial 13 artifacts and fresh-session 14-artifact correction passed |
| Codex native installation | Public GitHub marketplace add, install, removal, reinstall and readback passed in isolated configuration; installed helper executed |
| Claude Code native installation | Manifest validation and public GitHub marketplace add, install, removal, reinstall and readback passed in isolated configuration; installed helper executed |
| Cursor, Copilot, Gemini CLI, OpenCode | Portable installer and documented skill directories; no model runs claimed |
| External delivery, bookings or unattended real actions | Not performed; evaluation actions used fake adapters |
| Human owner acceptance | Not claimed |

The Codex CLI was `0.162.0-alpha.17.2`; Claude Code was `2.1.301`. Codex runs
used the existing subscription and harness-default model. The CLI transcript did
not expose a resolved model identifier. Claude Code was not authenticated; the
owner requested completion using the available verification rather than waiting
for authentication. This is a scoped 0.1.0 release, not a claim of equivalent
behavior across all harnesses.

Reports are in [evals/reports](../evals/reports). They record timestamps, skill
hashes, CLI versions, usage and case outcomes. Development failures are preserved
in the findings report. Two graders were corrected after inspecting real output:
the journey compares the actual starting revision and changed artifacts; critical
checks accept equivalent unresolved-accommodation states and exact USD currency
formatting. Saved outputs were regraded, not changed or rerun. The critical report
retains original grades and response hashes. Negative grader tests reject unsafe
coverage claims, incorrect balances and other currencies.

The implementing agent reviewed the generated host summary, correction review,
guest digest and action ledger. They show one uncertain mock send followed by
lookup, no duplicate send, a cancelled schedule that stays cancelled, preserved
evidence, changed rooming/meal counts and no named private requirements in the
guest digest. Selected actual synthetic output is in
[examples/completed](../examples/completed).

GitHub Actions passed the offline suite on Linux, Windows and macOS for
[the implementation commit](https://github.com/bobuel/eventer-plugin/actions/runs/38840848041).
Every installed skill file in both clients matched the published source byte for
byte. See [public installation evidence](../evals/reports/public-installation.json)
and [workflow runs](https://github.com/bobuel/eventer-plugin/actions) for exact
commit results. The original Eventer service, deployment and data are unchanged.
