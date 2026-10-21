# Improvement log

Only skill improvements the user approved, one line each. Format: `date, what happened -> rule that changed`.

- Artboards made in a cloud-only canvas format (custom tags, blob paths) did not open locally -> artboards are plain HTML that opens on its own and uses only relative paths.
- The user found a broken screen flow before the agent did -> flows between screens are drawn on the canvas with `link` arrows.
- `link` stored `boards/` prefixed names, so arrows never rendered -> board arguments are normalized to bare file names, unknown boards fail, and `check` reports dangling links.
- 2026-10-21, a long board (F09) was cut off and there was no way to resize it, so content was trimmed by hand -> `add` with a new `--size` resizes a registered board.
- 2026-10-21, another session left `canvas.py` half-edited (`NameError: cmd_snap`) and `add` failed mid-work -> skill changes are made in one step or a worktree, tested, then committed.
- 2026-10-21, subagents used a forbidden character (U+00B7) in 3 boards despite the brief -> a subagent runs `canvas check` and fixes its own boards before reporting.
