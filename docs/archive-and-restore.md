# Export and resume an event

The archive helper copies the selected event tree and optional source tree into
one portable directory. It verifies every file against a SHA-256 manifest and can
make a second identical copy as a restore rehearsal. It never deletes originals
or applies a retention policy automatically.

Finish event records first. Keep the input, helper result, manifest and completion
record outside the event tree so saving them does not invalidate the archive.
Review the contents before sharing: filename checks cannot detect every secret or
private fact inside a document.

For the standard workspace layout (`event/` and `sources/`), use:

```json
{
  "event": "event",
  "sources": "sources",
  "destination": "export/event",
  "manifest": "export-manifest.json",
  "restore_to": "restored/event",
  "retention_days": null
}
```

Run the installed `eventer.py archive --input archive-input.json`. The export and
restore directories must be new, separate from the inputs and from each other.
Check `verified` and `restored_verified` in the returned result. A failed run can
leave partial copies; preserve them and choose new targets for a retry.

## Resume from the archive

The archive is a frozen package, not automatically a working folder. For the
standard layout, copy `restored/event/` into a new workspace's `event/`, then copy
its bundled `sources/` into that workspace's `sources/`. Keep the frozen archive
unchanged. This reconstructs both workspace-relative source links (`sources/...`)
and saved event references (`event/...`). The extra bundled source copy is harmless.
If the original records used another source directory, reconstruct that path from
the evidence index instead. Never silently rewrite historical source references.

Run `validate` against the new `event/event.json`, then `audit-records` with the
new workspace path and `event: "event"`. An index can retain a quarantine entry
for an unrelated event whose original file was deliberately excluded. Do not
copy that private source into the new workspace to silence an audit. Preserve the
original index separately, check that no current fact, decision, blocker or
communication uses the excluded entry, and detach only that unused entry from the
new working index. If anything still depends on it, resolve that dependency first.
Record this restore reconciliation and rerun the audit. Frozen archives stay intact.
Inspect the history, communications and
outstanding-work list before continuing. Passing these checks establishes file
integrity and resolvable saved evidence; it does not verify provider delivery,
payment truth or external schedule state. Reconnect existing tools and reconcile
those facts before taking another external action.

Exporting, restoring or uninstalling Eventer does not cancel a harness schedule.
Cancel only when authorized and verify that scheduler's own readback.
