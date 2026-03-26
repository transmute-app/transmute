# Public

This folder contains static assets that Vite serves directly without passing through the React build pipeline.

## Purpose

- Store files that must keep stable public paths at runtime.
- Hold app icons and other browser-facing assets referenced by HTML, manifests, or metadata.

## Contents

- `icons/`: icon files used by the app shell and browser integration points.
- `site.webmanifest`: install metadata for browsers and home-screen launches.

## How To Work In This Folder

- Put assets here only when they need a fixed URL in the built frontend.
- Prefer `src/` imports for images or assets that should participate in bundling, hashing, or tree-shaking.
- Keep filenames stable when they are referenced by `index.html`, browser metadata, or external tooling.

## Practical Guidelines

- Avoid storing generated build output here.
- Keep assets optimized before committing them.
- If an asset is only used by one React component, it usually belongs under `src` instead.
