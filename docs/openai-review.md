# OpenAI directory package notes

Eventer is a skills-only plugin for planning group trips, retreats, and multi-day
events. It runs in the user's existing assistant and saves event records as local
files. The package contains twelve skills, Python planning tools, examples, and
public evaluations. It is distributed under the MIT license.

## Package contents

- Portable and Codex plugin manifests with listing metadata and an SVG icon.
- [Privacy policy](../PRIVACY.md) and [support](https://github.com/bobuel/eventer-plugin/issues).
- A versioned ZIP and checksum on the [releases page](https://github.com/bobuel/eventer-plugin/releases).
- [Evaluation instructions](../evals/README.md), test fixtures, and
  [verification results](verification.md).

The Python tools require local execution, so both supported OpenAI manifests
declare `requires_local_executor: true`. Eventer has no MCP server or hosted
backend. See OpenAI's
[desktop execution guidance](https://developers.openai.com/plugins/deploy/desktop-only).

## Data handling

Guests obtain property access instructions directly through the property's
secure channel. Eventer keeps access codes out of its drafts, records, and
exports. Personal requirements are limited to what the host needs for planning
and shared only with the appropriate recipients. The privacy policy describes
how the assistant and connected tools may process those records.

## Evaluation scope

The tests cover guest replies and corrections, room and meal planning, vendor
quotes, schedules, transport, communications, and event closeout. The verification
record distinguishes automated tests, simulated event scenarios, artifact review,
and native installation checks, including corrections made during development.
Real provider delivery and independent human hosting trials are outside that scope.

## Directory submission

Directory approval is separate from installation through GitHub. Maintainers can
submit the release ZIP through the [Plugins portal](https://platform.openai.com/plugins),
using a verified developer identity and following the
[submission instructions](https://developers.openai.com/plugins/deploy/submission)
and [plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines).

Eventer has not been submitted to or approved for the OpenAI directory as of
October 17, 2026.
