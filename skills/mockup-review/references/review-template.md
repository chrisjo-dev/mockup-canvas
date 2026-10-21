# Review template

Write to `design/<idea>/review.md`. If the file exists, put the new review at the top under a new dated heading and keep older reviews below. Replace everything in angle brackets.

```markdown
# Review: <idea>

## <YYYY-MM-DD>, <reviewer name or agent>

**Scope**: <boards reviewed, e.g. W01 to W06 in group "current">. Skipped: <boards or checklist sections skipped, and why>.
**Sources**: <spec or brief path>, shared/tokens.css, canvas.json. <"No spec found" if none.>
**Independence**: <"Separate session from the author" or "Same session that drew the boards">.

### Summary

- `canvas check`: <0 problems | N problems>
- Findings: <n> must, <n> should, <n> could
- <One or two sentences on the overall state: ready to approve, close, or needs another round.>

### Status recommendations

The user decides approval. These are recommendations only.

| Board | Current status | Recommendation | Reason |
| --- | --- | --- | --- |
| W01-Home.html | draft | approve | <one line> |
| W02-Send.html | draft | revise | <one line, point to the must findings> |

### Findings

Each finding is also a comment on its board.

| Severity | Board | Finding | Basis |
| --- | --- | --- | --- |
| [must] | W02-Send.html | <what is wrong> | <checklist section, spec item, or token> |
| [should] | W03-Done.html | <what is wrong> | <basis> |

### Flow

- Entry: <board>
- Dead ends: <list or "none">
- Unreachable boards: <list or "none">

### Missing screens or states

- <state or screen, which flow it belongs to, severity>

### Not checked

- <for example motion, real data volume, sizes that were not drawn>
```
