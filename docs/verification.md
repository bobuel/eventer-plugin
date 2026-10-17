# Verification record

## Version 0.1.2

The [fresh qualification report](../evals/reports/qualification-0.1.2.json) records
ten Luna phase attempts across three 24-person hosting packages. Three attempts
failed and are preserved. After correction, the seven selected phases pass both
automatic checks and the implementing parent's artifact review. Each phase used a
fresh Luna subagent without expected answers or corrective follow-up prompts.
These are development runs on known fixtures, not a measured reliability rate.

The failed attempts found omitted canonical meal fields, invented meal overrides
and serving categories, and a household sender whose confirmed RSVP appeared only
in prose. Skills/helper validation were corrected and affected scenarios rerun.
Correspondence, weekend and live packages use successive recorded skill hashes;
we do not claim that one final revision ran all seven phases. Local self-correction
remains visible, including a failed closeout cancellation call missing its input
file, followed by a successful corrected call.

The offline suite passes **223 tests**. The independent code reviewer reproduced
and fixed three additional gaps: grading the wrong meal invocation, missing
privacy context across Markdown headings, and accepting remote SVG resources.
Regressions are included in the repository. These privacy checks are conservative
fixture screens and still require prose review.

Native installation of the candidate ZIP passed in isolated Codex and Claude Code
homes. Both reported 0.1.2 enabled; all 40 installed skill files matched the source
and the installed quote helper returned USD 131.70. The icon was rendered and
visually checked. Closeout exported and restored **85 byte-identical files**,
preserved originals, and observed zero scheduled executions after cancellation.
Reconstructing a separate workspace from that restored archive passed structural
and evidence-link validation without editing or normalizing any saved records.
[Public GitHub installation](../evals/reports/public-installation-0.1.2.json) also
passed in both clients with the same installed file hashes and helper result.

The public package includes listing metadata, icon and privacy policy. See
[the OpenAI review brief](openai-review.md) before contacting OpenAI: the existing
private door-code draft needs policy clarification or a product change. Publisher
verification, portal scans and directory approval have not been performed. This
does not prevent public GitHub installation.

No real provider delivery, bookings, payments, production scheduler, Claude model
behavior, other native harness behavior or independent human acceptance is claimed.
The original Eventer service remains outside this plugin work.

## Version 0.1.1

All seven phases in the three 24-guest hosting packages pass automatic checks and
the implementing parent's artifact review against the same installed skill files.
The [0.1.1 Luna report](../evals/reports/hosting-luna-0.1.1.json) preserves exact
hashes, original failures and review notes. This is a development evaluation with
one corrective follow-up for live phase 1, not seven unaided first-attempt passes
or a measured reliability rate. The evaluator supplied no expected answers.

The offline suite passes 186 tests, including archive safety/integrity, evidence
links, installer/package checks and negative grader tests. Twelve skills pass
package validation. The source is checked on Windows, Linux and macOS by
[GitHub Actions](https://github.com/bobuel/eventer-plugin/actions).

The final two grader corrections accept a complete check-in draft under a filename
the task did not constrain, and repeated cancellation of the same authorized task
in the explicitly idempotent simulator. Wrong audiences, missing code, sent drafts,
unrelated cancellation targets, missing readback and future execution still fail.
The actual closeout agent made two cancel calls; that inefficiency is retained in
the review, not reported as a one-call cancellation. A Windows delete-pending lock
race in the test recorder was also fixed with bounded retry and regression tests.

The archive/restore contained 128 identical files. A separate
[restore usability check](../evals/reports/restore-usability-0.1.1.json) reconstructed
a new workspace and passed event/evidence validation. It required explicit
separation of one unused foreign-event index entry whose protected source was
intentionally excluded. The maintainer performed that reconciliation in the new
working copy; the evaluated artifacts and frozen archive were not changed. See
[the restore procedure](archive-and-restore.md).

[Public GitHub installation](../evals/reports/public-installation-0.1.1.json) passed
in Codex and Claude Code. All 40 installed skill files matched the tested source,
both clients reported 0.1.1 enabled, and an installed helper ran successfully.
Cursor, Copilot, Gemini CLI and OpenCode have documented destinations supported by
the tested portable installer; their native clients/models were not exercised.

No real email delivery, bookings, payments or production scheduler were tested.
Claude model behavior, concurrent cohost writes and human owner acceptance remain
outside this verification. The original hosted service and its data are unchanged.

## Historical development findings before 0.1.1

The original 0.1.0 results below describe the narrower suite available at release.
A later coverage audit found that its journey grader could accept corrupted
recipients, assignments, scheduler scope and meaningless prose. Those historical
scores must not be read as comprehensive hosting verification. The graders now
check those invariants, with mutation tests for the previously accepted failures.

The repository now also includes three [full hosting packages](../evals/README.md#full-hosting-packages)
covering 24 synthetic guests across seven phases. Their independently observed
actions, saved records, fresh-session changes and export restoration are evaluated
separately from prose quality. The earlier failures and tested content hashes
remain in [the historical hosting report](../evals/reports/hosting-luna.json).

### Earlier expanded-suite attempt

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
runs were explicitly marked as not behaviorally retested at that time. Version
0.1.1 above supersedes that status without rewriting the historical report.

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
