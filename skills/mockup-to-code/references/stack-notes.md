# Stack notes

Short mapping tips. The project's existing conventions always win over these notes.

## Tokens: CSS variables or a theme config

`shared/tokens.css` defines custom properties such as `--color-bg`, `--font-body`, `--space-4`, `--radius-md`.

- **CSS variables (any stack)**: copy the `:root { ... }` block into the app's global stylesheet once (for example `src/styles/tokens.css`) and import it at the app entry. Rename only if the app already has a naming scheme, and keep a one-line comment that maps board names to app names.
- **Tailwind**: keep the variables in a global CSS file and point the theme at them, so there is one source of values.
  - Tailwind v4: `@theme { --color-bg: ...; }` in the main CSS file generates `bg-bg`, `text-...` utilities directly.
  - Tailwind v3: in `tailwind.config.js`, `theme.extend.colors.bg = 'var(--color-bg)'`, and the same for `spacing`, `borderRadius`, `fontFamily`.
  - Do not use arbitrary values like `bg-[#1a1a1a]` or `p-[13px]` for anything a token covers.
- **Existing design system or UI kit**: map board tokens onto the kit's theme (MUI `createTheme`, Chakra `extendTheme`, shadcn CSS variables). Add new tokens only for values the kit has no slot for, and list them in the report.
- **Fonts**: if the board loads a Google Font, load it the way the app loads fonts (`next/font`, a `<link>` in `index.html`, or a self-hosted file). Do not add a second loading path.

## React with Vite

- Routes usually live in a router file (`react-router` `createBrowserRouter` or `<Routes>`). Add one route per board; reuse the existing layout route for the shared shell.
- Import the token CSS in `src/main.tsx` (or `.jsx`).
- Dev server: `npm run dev`, default `http://localhost:5173/`. Pass `--port` to use a free port.

## Next.js

- App Router: the shared shell is `app/layout.tsx` (or a route group layout like `app/(app)/layout.tsx`); each board is `app/<route>/page.tsx`. Pages Router: `pages/_app.tsx` for the shell, `pages/<route>.tsx` per board.
- Import the token CSS in the root layout (`app/globals.css` is common).
- Server components cannot use client state; put interactive parts from the board in `'use client'` components.
- Dev server: `npm run dev`, default `http://localhost:3000/`.

## Vue

- Vue Router: the shell is `App.vue` or a layout component with `<RouterView />`; each board is a view in `src/views/`.
- Import the token CSS in `src/main.ts`. Scoped styles use `var(--...)` like any CSS.
- Nuxt: shell in `layouts/default.vue`, boards in `pages/`. Dev server default `http://localhost:3000/`; Vite-based Vue default `http://localhost:5173/`.

## Svelte and SvelteKit

- SvelteKit: shell in `src/routes/+layout.svelte`, each board in `src/routes/<route>/+page.svelte`. Import the token CSS in the root layout.
- Component `<style>` blocks are scoped; tokens still come from the global variables.
- Dev server: `npm run dev`, default `http://localhost:5173/`.

## Plain HTML

- One page per board, one shared `tokens.css` and one shared layout stylesheet linked from every page.
- Extract repeated parts by convention (a shared header partial if there is a build step, otherwise keep the markup identical and note it).
- Serve with any static server for `compare`, for example `python3 -m http.server 8000`, and stop it by PID afterward.

## Responsive breakpoints from board sizes

The canvas size presets are `mobile` 390x844, `tablet` 768x1024, `desktop` 1440x900, or a custom `WxH`.

- Build mobile first when the approved boards include a mobile size, then add breakpoints for the larger boards.
- Put breakpoints between board widths, not at them, so each board size lands inside one range. A common choice: base styles for mobile, `min-width: 768px` for tablet, `min-width: 1200px` for desktop. Reuse the app's existing breakpoints if it has them.
- If only one size was approved, implement that size faithfully and keep other widths usable (no horizontal scroll, readable text), then list the other sizes as unverified in the report.
- `compare` captures at the board's size. Check other approved sizes with their own boards, and extra widths with `canvas snap <url> --size WxH`.
- Height in a board is the viewport, not a fixed page height. Let content scroll; do not hard-code the board height into the layout.
