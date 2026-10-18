# Eventer

**Plan a group trip, retreat, or weekend together.**

Eventer helps your AI assistant keep track of guests, rooms, meals, rides, and
changing plans. Install it in the assistant you already use, give it the event
details, and work through the planning together.

It is an open-source plugin with twelve skills and local planning tools. Your
plans are saved as files you can read, edit, and take with you. There is no
Eventer account or subscription; you use your existing AI assistant and tools.

## Get started

**Codex** — run in your terminal:

```sh
codex plugin marketplace add bobuel/eventer-plugin
codex plugin add eventer@eventer-plugins
```

**Claude Code** — run inside Claude Code:

```text
/plugin marketplace add bobuel/eventer-plugin
/plugin install eventer@eventer-plugins
```

For Cursor, GitHub Copilot, Gemini CLI, OpenCode, and other assistants that support
Agent Skills, see the [installation guide](docs/installation.md). Local planning
calculations need Python 3.12+; the guide covers setup and dependencies.

Then start a new conversation:

> Use Eventer to help me plan a three-day weekend for 12 friends. We need a place
> to stay, two group dinners, and rides from the station. Start with what you
> need to know.

## From the first invitation to the last day

Start with the dates, budget, guest list, and anything the group needs. Eventer
helps you organize the details and identify the decisions still to make.

As replies arrive, ask it to update the guest list, suggest room assignments,
count meals, and check ride capacity. It keeps unanswered questions visible so
you can follow up before committing to a plan.

When something changes, bring it back to the same event:

> Jamie is arriving Saturday instead of Friday, and Alex can no longer come.
> Update the room and meal plans, show me what changes, and draft a guest update.

During the event, ask for the day's schedule or help handling a late arrival.
Afterward, review outstanding costs and follow-ups, then save an archive of the
event records.

## What it helps with

| Task | Skills |
|---|---|
| Get started and decide what to do next | `eventer`, `eventer-setup` |
| Track invitations, replies, and guest needs | `eventer-guests` |
| Draft messages and check sending status | `eventer-communications` |
| Plan rooms and meals | `eventer-lodging`, `eventer-meals` |
| Compare venues, activities, and vendor quotes | `eventer-research`, `eventer-vendors` |
| Coordinate the schedule and rides | `eventer-schedule-transport` |
| Review open tasks and handle changes on the day | `eventer-readiness-live` |
| Set up recurring reviews through your assistant | `eventer-setup-scheduling` |
| Review follow-ups and save the event records | `eventer-wrap-up` |

You can ask for Eventer generally or name a skill for a particular task. Install
the full collection so each skill can use the shared planning tools.

## Working with your tools

Eventer uses the email, search, and scheduling tools available to your assistant.
You decide what it may send or change. Without a connected tool, it can prepare
drafts and lists for you to use yourself. Recurring reviews require your
assistant's scheduler.

Review plans before making commitments with guests or vendors. Keep private
guest details in your event folder and share only what each recipient needs.
Your AI provider and connected tools may process information you share with
them; see the [privacy policy](PRIVACY.md).

## For contributors

The repository includes the skills, Python planning tools, examples, and tests.
To work on it locally, clone the repo and run:

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate.py
python evals/run.py offline
```

The [evaluation guide](evals/README.md) explains how to run the hosting scenarios.
The [verification record](docs/verification.md) documents tested behavior,
corrections, and limitations. For helper inputs and examples, see the
[planning tool reference](skills/eventer/references/helpers.md).

[Contributing](CONTRIBUTING.md) · [Report an issue](https://github.com/bobuel/eventer-plugin/issues)
· [Security](SECURITY.md) · [MIT license](LICENSE)
