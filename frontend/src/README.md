# Source

This folder contains the React application source for the frontend.

## Purpose

- Define the application shell, routing, global styling, state providers, pages, and shared UI.
- Keep the frontend organized by responsibility: app bootstrap, contexts, components, pages, and utilities.

## Contents

- `main.tsx`: Vite entrypoint that mounts the React app.
- `App.tsx`: app shell, route guards, route definitions, and shared layout wiring.
- `AuthContext.tsx`: authentication state and bootstrap-aware session handling.
- `ThemeContext.tsx`: theme and UI preference state shared across the app.
- `index.css`: global styles and theme tokens.
- `components/`: shared presentational and reusable UI building blocks.
- `pages/`: route-level screens.
- `utils/`: API and browser helper utilities.

## How To Work In This Folder

- Keep route-level state and workflows in `pages/`.
- Keep reusable UI pieces in `components/`.
- Keep cross-cutting app state in context providers only when it is needed broadly.
- Keep request helpers and storage helpers in `utils/` instead of duplicating fetch logic inside pages.

## Practical Guidelines

- Preserve the current separation between app shell code in `App.tsx` and feature code in pages/components.
- Avoid pushing unrelated business logic into contexts; use them for shared state, not as a catch-all service layer.
- Reuse the API helpers in `utils/api.ts` so auth and error handling stay consistent.
- Keep new code aligned with the existing React + TypeScript + Tailwind patterns already used in this app.

## Typical Workflow

1. Add route-level behavior in a page.
2. Extract repeated UI into a shared component.
3. Reuse or extend a utility helper if multiple screens need the same API or browser behavior.
4. Update the app shell or providers only when the change affects global routing or state.
