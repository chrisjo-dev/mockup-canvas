# Review checklist

Go through every section for each current artboard, then the flow section once for the whole idea. Skip a line only when it clearly does not apply (for example thumb reach on a desktop board), and say which lines you skipped in `review.md`.

## Severity

| Tag | Use when | Effect |
| --- | --- | --- |
| `[must]` | The flow breaks, a state the spec requires is missing, the screen contradicts the spec, text is unreadable, a `check` problem | Blocks an `approve` recommendation |
| `[should]` | A real problem a user would hit, or a rule below is broken, but the screen still works | Fix before implementation |
| `[could]` | Polish, an alternative worth trying, a nice-to-have | Optional |

When unsure between two levels, pick the lower one and explain why in the comment.

## 1. State coverage

For each screen that shows data or takes input, is there a board (or a clearly marked variant) for:

- [ ] Empty: no items yet, with a next action, not just blank space
- [ ] Loading: skeleton or progress, layout does not jump when data arrives
- [ ] Error: what went wrong in plain words and a way to retry or go back
- [ ] Permission: no access, signed out, or a denied system permission (camera, location, notifications)
- [ ] Long content: long names, long numbers, many items, wrapped lines, emoji and non-Latin text
- [ ] First run: onboarding, first item, defaults that make sense before the user has any data

If the user fixed the number of screens, a missing state is a `[should]` suggestion in the report, not a `[must]` on a board.

## 2. Flow

- [ ] Every tappable element on a board leads to a linked board or is a stated end of the flow
- [ ] No board is unreachable from the entry screen (except deliberate state variants)
- [ ] Every flow has a way back or out (back, close, cancel)
- [ ] Destructive actions have a confirmation or undo
- [ ] `check` reports no dangling links; arrow labels match the button text on the board

## 3. Consistency with tokens

Read the HTML, not only the PNG.

- [ ] Colors use `var(--...)` from `shared/tokens.css`; no hex, `rgb()`, or named colors in the artboard
- [ ] Font families, sizes, spacing, and radius come from tokens, not one-off values
- [ ] The same component (button, card, tab bar, header) looks and behaves the same on every board
- [ ] Icons come from one set and one style

## 4. Accessibility basics

- [ ] Text contrast at least 4.5:1 for body text, 3:1 for large text and icons that carry meaning
- [ ] Tap targets at least 44x44px, with space between neighboring targets
- [ ] Body text at least 16px on mobile, nothing below 12px
- [ ] Meaning is not carried by color alone (errors have text or an icon too)
- [ ] Form fields have visible labels, not only placeholders

## 5. Mobile thumb reach

For mobile boards:

- [ ] The primary action is in the lower half of the screen or in a bottom bar
- [ ] Frequent actions are not only in the top corners
- [ ] Nothing important sits under the home indicator or the status bar

## 6. Copy

- [ ] Button labels say what happens ("Send 20,000 won", not "OK")
- [ ] Errors say what to do next
- [ ] The same thing has the same name on every board
- [ ] No placeholder text (lorem ipsum, "Title", "TODO") left on a board meant for approval

## 7. Spec match

- [ ] Every required feature in the spec has a screen or a state
- [ ] Field names, limits, and rules shown on boards match the spec
- [ ] Nothing on a board promises a feature the spec does not include, unless it is marked as a proposal
