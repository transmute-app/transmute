<h1>
  <picture height=23px>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/brand/beaker-white.svg" height=23px />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/brand/beaker-black.svg" height=23px />
    <img alt="Transmute logo, a small flask" src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/brand/beaker-white.svg" height=23px />
  </picture>
  Transmute
</h1>

[![License](https://img.shields.io/badge/license-MIT-green?logo=git&logoColor=white)](https://github.com/transmute-app/transmute/blob/main/LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://github.com/transmute-app/transmute/blob/main/docker-compose.yml)
![Status](https://img.shields.io/badge/status-development-orange)

![Docker Image Size](https://img.shields.io/docker/image-size/neonvariant/transmute?logo=docker&logoColor=white&color=gray&cacheSeconds=14400)
![GitHub repo size](https://img.shields.io/github/repo-size/transmute-app/transmute?logo=github&logoColor=white&color=gray&cacheSeconds=14400)


**Transmute** is a **free, open source, self-hosted file converter** built for privacy and flexibility. Convert **images, video, audio, documents, spreadsheets, subtitles, and fonts** entirely locally, with no file size limits and no third-party access to your files. Deploy in seconds with Docker.

This application is under active development. Want to support us? Give us a star or jump in and contribute!

> [!NOTE]
> **This project is human-led and maintainer-reviewed.**
> AI tools may be used during development, but all code is intentionally written, reviewed, and validated by a human who understands and takes responsibility for the result. This is not an autonomously generated project, and fully AI-generated or agent-submitted contributions are not accepted. See the [contributing guide](https://github.com/transmute-app/transmute?tab=contributing-ov-file#no-autonomous-agents-or-ai-assistants) for more details

## Screenshots
| Converter / Home | Uploaded Files | Previously Converted | Settings |
| --- | --- | --- | --- |
| <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/converter.png" width=100%> | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/files.png" width=100%> | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/history.png" width=100%> | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/settings.png" width=100%> |

## Demo
Want to see a video demo? Check out our [YouTube](https://www.youtube.com/watch?v=lod7Fze9oPY).

## Features

- **Privacy first**: Files are processed on your own server and never sent to third parties
- **No file size limits**: Convert files as large as your storage allows
- **100+ formats supported**: Images, video, audio, documents, spreadsheets, subtitles, and fonts
- **Built-in authentication**: User accounts, role-based access, and API key support out of the box
- **Docker ready**: Deploy with a single command, no complex setup required
- **REST API**: Automate and integrate file conversions via the built-in OpenAPI-documented API
- **Multiple themes**: Seven built-in light and dark UI themes

<!-- PRE_GIF_MARKER 
<div align="center">
  <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/demos/demo.gif" alt="GIF showind the Transmute workflow" width=75%>
  <p><i>Fun fact, this gif was created by converting a screen recording using Transmute!</i></p>
</div>
 POST_GIF_MARKER -->

> [!WARNING]
> **Think carefully before exposing Transmute to the public internet / WAN.**
> Transmute includes built-in authentication and per-user data isolation, but is designed for trusted networks. If you expose it beyond your LAN, place it behind a reverse proxy with TLS and rate limiting. The maintainers are not responsible for security issues arising from your deployment configuration.

## Quickstart
```bash
wget "https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/docker-compose.yml" && docker compose up -d
```

## What Does Transmute Replace?
*For the record, I love all of these services and use them all frequently. Transmute is not up to par with any of them yet. But it will be!*
| Service | Why Replace? |
| ------- | --------------- |
| [cloudconvert.com](https://cloudconvert.com/) |  File size limits, API is paid only, 3rd-party gets my files |
| [freeconvert.com](https://www.freeconvert.com/) | File size limits, 3rd-party gets my files |
| [cconvertio.co](https://convertio.co/) | File size limits, 3rd-party gets my files |

## Supported Formats

| Category | Formats |
| -------- | ------- |
| Images | JPEG, PNG, WebP, AVIF, HEIC/HEIF, JXL, GIF, BMP, TIFF, SVG, ICO, PSD, and more |
| Video | MP4, MKV, MOV, WebM, AVI, FLV, WMV, TS, 3GP, and more |
| Audio | MP3, WAV, FLAC, AAC, M4A, OPUS, OGG, AIFF, WMA, and more |
| Documents | Markdown, HTML, DOCX, PDF, EPUB, ODT, RST, LaTeX, RTF, PPTX, and more |
| Data / Spreadsheets | CSV, XLSX, JSON, Parquet, YAML, TSV, XML, ODS, and more |
| Subtitles | SRT, ASS, SSA, VTT, SUB |
| Fonts | TTF, OTF, WOFF, WOFF2 |
| Diagrams | DrawIO |

## Themes

| Dark Theme       | Screenshot | Light Theme      | Screenshot |
| ---------------- | ---------- | ---------------- | ---------- |
| Rubedo (Default) | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/rubedo.png" width=100%> | Albedo           | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/albedo.png" width=100%> |
| Citrinitas       | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/citrinitas.png" width=100%> | Aurora           | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/aurora.png" width=100%> |
| Viriditas        | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/viriditas.png" width=100%> | Caelum           | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/caelum.png" width=100%> |
| Nigredo          | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/nigredo.png" width=100%> | Argentum | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/argentum.png" width=100%> |

## API Documentation
When the app is running the API docs are available at http://TRANSMUTE_IP:3313/api/docs

## Contributing

Contributions are welcome! This project is human-driven - autonomous agents and AI assistants are not welcome contributors and such submissions will be rejected. See the [contributing guide](https://github.com/transmute-app/transmute?tab=contributing-ov-file#no-autonomous-agents-or-ai-assistants) for details.

### Our Awesome Contributors

<a href="https://github.com/transmute-app/transmute/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=transmute-app/transmute" alt="Image with all contributors"/>
</a>
