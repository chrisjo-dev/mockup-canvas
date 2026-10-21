# Final reply template

Reply in the user's language. Replace everything in angle brackets. Keep it short; the tables carry the detail.

```markdown
## Implemented

| Board | Route | Main files | Mismatch | Images |
| --- | --- | --- | --- | --- |
| W01-Home.html | / | src/pages/Home.tsx | 3.1% | design/<idea>/compare/W01/side.png, diff.png |

Shared shell and components: <files>. Token mapping: <file>, <n> new tokens added: <names or "none">.

## Remaining differences

- W01: <difference>, <why it is intentional or acceptable>

## Stubs and gaps

- <stub file or route>, marked `TODO(mockup-to-code)`, waiting for <API or decision>
- <approved boards not implemented, and why>

## Checks

- Tests: <command, result>
- Lint: <command, result>
- Typecheck: <command, result>
- `canvas impl <idea> --strict`: <result>

## Verified and unverified

- Verified: <what you ran and looked at, for example compare at mobile size for W01 to W03, tests passing>
- Unverified: <for example real backend, Safari, tablet width without a board, animations>

## Skill improvement suggestions

1. <what happened, impact, rule or command to change> (or "None this time")
```
