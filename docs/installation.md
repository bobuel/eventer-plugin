# Installation and compatibility

Use an up-to-date harness with Agent Skills support. The plugin is a local package;
GitHub hosts its source and releases, not an event service. No connector is mandatory.
Your harness's login and tool permissions remain authoritative.

## Codex

```sh
codex plugin marketplace add bobuel/eventer-plugin
codex plugin add eventer@eventer-plugins
codex plugin list
```

In the desktop app, restart or refresh the plugin directory if needed and choose
the Eventer marketplace. Invoke `eventer` or a specialist skill. Some older Codex
clients expose installation only through the directory UI; the compatibility
manifest and repo marketplace are included for those clients.

To refresh the source: `codex plugin marketplace upgrade eventer-plugins`, then
use your client's plugin update/reinstall action and check the reported version.
To remove: `codex plugin remove eventer@eventer-plugins`. Remove the marketplace
separately with `codex plugin marketplace remove eventer-plugins` if no longer needed.
Removal does not delete event files or cancel scheduled tasks.

## Claude Code

Inside Claude Code:

```text
/plugin marketplace add bobuel/eventer-plugin
/plugin install eventer@eventer-plugins
```

Start a fresh session and invoke `/eventer:eventer` or
`/eventer:eventer-setup`. For local authoring use
`claude --plugin-dir /absolute/path/to/eventer-plugin`.
Use `/plugin` to inspect, update, disable or uninstall. `claude plugin validate .`
checks packaging; it does not execute the skills or establish behavioral quality.

## Portable Agent Skills installation

Clone or download a tagged release. Install all twelve skill folders together.
The installer previews by default and never edits global harness configuration:

```sh
python scripts/install.py --destination /path/to/project/.agents/skills
python scripts/install.py --destination /path/to/project/.agents/skills --apply
```

| Harness | Recommended project destination | Validation claim |
|---|---|---|
| Cursor | `.cursor/skills` | Documented compatibility; actual status in verification.md |
| GitHub Copilot | `.github/skills` | Documented compatibility; actual status in verification.md |
| Gemini CLI | `.gemini/skills` | Documented compatibility; actual status in verification.md |
| OpenCode | `.opencode/skills` | Documented compatibility; actual status in verification.md |
| Other Agent Skills harness | Its supported skills directory | Requires discovery, file access and optional script execution |

Replace the example destination with an absolute path on your system. On Windows,
PowerShell accepts quoted `C:/path/to/project/.agents/skills` paths. Shared
`.agents/skills` is supported by several harnesses, but use one destination to avoid
duplicate discovery. Native plugin and portable skill installations should not both
be enabled for the same project.

Run the same install command after downloading an update. Modified installed files
cause a refusal rather than silent overwrite. Preserve or reconcile your changes
first. Uninstall previews then removes only manifest-owned, unchanged files:

```sh
python scripts/install.py --destination /path/to/project/.agents/skills --uninstall
python scripts/install.py --destination /path/to/project/.agents/skills --uninstall --apply
```

Use `python -B` for installed helpers to avoid cache files inside the installation.
The installer refuses unexpected files or symlinks in owned skill directories.
Keep event data in a separate private folder. Scripts require Python 3.12+ and
IANA timezone data (`python -m pip install -r requirements.txt`).

## Capabilities and graceful fallbacks

- Files: needed for durable event records; without write access, return a draft
  artifact and explain it has not been saved.
- Email/calendar/search: use existing authenticated tools when available; otherwise
  produce drafts, import templates or a research checklist.
- Scheduler: use existing create/read/update/cancel tools. If absent, provide a
  manual cadence. Never imply the plugin keeps running after the harness stops.
- Script execution: needed for deterministic helpers. If absent, produce the input
  and instructions to run it; do not label a hand calculation as a tested helper run.

## Source documentation

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex packaging](https://developers.openai.com/plugins/build/plugins)
- [Claude Code marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Cursor skills](https://cursor.com/docs/skills)
- [Copilot skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/)
- [OpenCode skills](https://opencode.ai/docs/skills/)

Documentation checked October 15, 2026 (America/New_York). Supported installation
formats are not proof that every harness/model produces equivalent behavior.
