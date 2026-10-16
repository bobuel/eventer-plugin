# Verification record: 0.1.0

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
