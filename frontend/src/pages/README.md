# Pages

This folder contains route-level screens for the frontend.

## Purpose

- Implement user-facing workflows such as authentication, conversion, history, files, settings, and account management.
- Own page-specific state, effects, and API orchestration.
- Provide the rendered content for routes declared in `App.tsx`.

## Contents

- `Auth.tsx`: sign-in and bootstrap flow.
- `Converter.tsx`: upload and conversion workflow.
- `Files.tsx`: uploaded file management.
- `History.tsx`: previously converted output history.
- `Settings.tsx`: user preferences and app settings UI.
- `Account.tsx`: account and API key management.
- `Users.tsx`: admin-only user management.
- `NotFound.tsx`: fallback route.

## How To Work In This Folder

- Put route-specific data fetching, state management, and orchestration here.
- Use shared components for repeated UI instead of duplicating layout fragments across screens.
- Use helpers from `utils/` for API requests and downloads.
- Keep route guards in `App.tsx`; page files should focus on the screen behavior after access is granted.

## Practical Guidelines

- Handle loading, empty, success, and failure states explicitly.
- Keep page modules readable by extracting repeated UI into `components/`.
- Avoid reaching into browser storage or auth headers directly when the utility layer already covers it.
- If multiple pages need the same behavior, consider extracting a hook or utility before copying logic.

## Typical Workflow

1. Add or update the page component.
2. Wire route changes in `App.tsx` if needed.
3. Reuse contexts and API helpers rather than rebuilding global logic locally.
4. Extract shared UI or helper code when duplication starts to appear.
