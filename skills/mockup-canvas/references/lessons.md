# Improvement log

Only skill improvements the user approved, one line each. Format: `date, what happened -> rule that changed`.

- Artboards made in a cloud-only canvas format (custom tags, blob paths) did not open locally -> artboards are plain HTML that opens on its own and uses only relative paths.
- The user found a broken screen flow before the agent did -> flows between screens are drawn on the canvas with `link` arrows.
- `link` stored `boards/` prefixed names, so arrows never rendered -> board arguments are normalized to bare file names, unknown boards fail, and `check` reports dangling links.
