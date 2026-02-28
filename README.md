<h1>
  <picture height=23px>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/brand/beaker-white.svg" height=23px />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/brand/beaker-black.svg" height=23px />
    <img alt="Transmute logo, a small flask" src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/brand/beaker-white.svg" height=23px />
  </picture>
  Transmute
</h1>

The self-hosted file converter that lets you convert anything, anywhere.

This application is under active development, want to support us? Give us a star or jump in and contribute!

<!-- PRE_GIF_MARKER -->
<div align="center">
  <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/demos/demo.gif" alt="GIF showind the Transmute workflow" width=75%>
  <p><i>Fun fact, this gif was created by converting a screen recording using Transmute!</i></p>
</div>
<!-- POST_GIF_MARKER -->

## What Does Transmute Replace?
*For the record, I love all of these services and use them all frequently. Transmute is not up to par with any of them yet. But it will be!*
| Service | Why Replace? |
| ------- | --------------- |
| [cloudconvert.com](https://cloudconvert.com/) |  File size limits, API is paid only, 3rd-party gets my files |
| [freeconvert.com](https://www.freeconvert.com/) | File size limits, 3rd-party gets my files |
| [cconvertio.co](https://convertio.co/) | File size limits, 3rd-party gets my files |


## Status
This project is under heavy development, come back soon to see where it goes!

# Quickstart
```bash
wget "https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/docker-compose,yml" && docker compose up -d
```

## Themes & Screenshots

| Theme            | Screenshot |
| ---------------- | ---------- |
| Rubedo (Default) | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/rubedo.png" width=50%> |
| Citrinitas       | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/citrinitas.png" width=50%> |
| Viriditas        | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/viriditas.png" width=50%> |
| Nigredo          | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/nigredo.png" width=50%> |
| Albedo           | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/albedo.png" width=50%> |
| Aurora           | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/aurora.png" width=50%> |
| Caelum           | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/caelum.png" width=50%> |

## Diagrams
Shoutout to [draw.io](https://www.drawio.com/) - formerly diagrams.net. I love their software and have always planned out projects using it. 

Recently I discovered [@hediet](https://github.com/hediet) has a [draw.io vscode extension](https://github.com/hediet/vscode-drawio) so now we have our diagrams stored in git at [docs/diagrams/source](https://github.com/transmute-app/transmute/tree/main/docs/diagrams/source). 

They are also exported to [docs/diagrams/exports](https://github.com/transmute-app/transmute/tree/main/docs/diagrams/exports) for easy viewing from the UI.

## API Documentation
When the app is running the API docs are available at APP_URL/api/docs/

My plan is to eventually make these available on our website as well but I haven't worked out a proper way of doing that automatically just yet.