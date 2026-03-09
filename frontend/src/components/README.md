# Components

This folder contains reusable UI components shared across one or more pages.

## Purpose

- Provide composable building blocks for the app shell and feature screens.
- Keep page files focused on workflows and state orchestration instead of low-level UI markup.

## Contents

- Layout and shell pieces such as `Header.tsx` and `Footer.tsx`.
- Shared interaction components such as dialogs, previews, and file tables.

## How To Work In This Folder

- Add a component here when it is reused or clearly reusable across pages.
- Keep components focused on presentation and localized interaction.
- Pass data and callbacks in through props rather than reaching into unrelated global state.
- Extract shared types from a component only when another part of the frontend needs them.

## Practical Guidelines

- If a component is only used by one route and is tightly coupled to that route's state, keep it near the page unless reuse becomes clear.
- Prefer explicit prop names over overly generic component APIs.
- Keep styling consistent with the current Tailwind and theme token patterns.
- Avoid duplicating auth, fetch, or routing logic across components when that logic belongs in pages or utilities.

## Typical Workflow

1. Build the feature in a page first if the shape is still unclear.
2. Extract stable, reusable UI into `components/`.
3. Keep the extracted component controlled by props where possible.
4. Reuse the same component across pages instead of creating near-duplicates.
