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
![Status](https://img.shields.io/badge/status-beta-green)

![Docker Image Size](https://img.shields.io/docker/image-size/neonvariant/transmute?logo=docker&logoColor=white&color=gray&cacheSeconds=14400)
![GitHub repo size](https://img.shields.io/github/repo-size/transmute-app/transmute?logo=github&logoColor=white&color=gray&cacheSeconds=14400)


**Transmute** is a free, open source, self-hosted file converter built for privacy and automation. Convert images, video, audio, documents, spreadsheets, subtitles, and fonts entirely locally, with no file size limits and no third-party access to your files. Deploy in seconds with Docker.

Full documentation on [our website](https://transmute.sh/docs/)!

## Screenshots
| Converter / Home | Uploaded Files | Previously Converted | Settings |
| --- | --- | --- | --- |
| <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/converter.png" width=100%> | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/files.png" width=100%> | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/history.png" width=100%> | <img src="https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/assets/screenshots/settings.png" width=100%> |

This application is currently in early beta. Want to support us or follow along? Give us a star or jump in and contribute!

> [!NOTE]
> **This project is human-led and maintainer-reviewed.**
>
> AI tools assist during development (autocomplete, some boilerplate, help with tests) but all code is intentionally written, reviewed, and validated by a human who understands and takes responsibility for the result. This is not an autonomously generated project, and fully AI-generated or agent-submitted contributions are not accepted. See the [contributing guide](https://github.com/transmute-app/transmute?tab=contributing-ov-file#no-autonomous-agents-or-unreviewed-ai-contributions) for more details

## Demo
Want to see a video demo? Check out our [YouTube](https://www.youtube.com/watch?v=Gmh7gm2z6mk).

## Features

- **Privacy first**: Files are processed on your own server and never sent to third parties
- **OiDC / SSO support**: Login and account creation via OIDC providers such as Authentik, see the [docs](https://transmute.sh/docs/oidc/)
- **No file size limits**: Convert files as large as your storage allows
- **100+ formats supported**: Images, video, audio, documents, spreadsheets, subtitles, and fonts
- **Built-in authentication**: User accounts, role-based access, and API key support out of the box
- **Docker ready**: Deploy with a single command, no complex setup required
- **REST API**: Automate and integrate file conversions via the built-in OpenAPI-documented API
- **Multiple themes**: Seven built-in light and dark UI themes

> [!WARNING]
> **Think carefully before exposing Transmute to the public internet / WAN.**
> Transmute includes built-in authentication and per-user data isolation, but is designed for trusted networks. If you expose it beyond your LAN, place it behind a reverse proxy with TLS and rate limiting. The maintainers are not responsible for security issues arising from your deployment configuration.

## Quickstart
```bash
wget "https://raw.githubusercontent.com/transmute-app/transmute/refs/heads/main/docker-compose.yml" && docker compose up -d
```
Then visit [localhost:3313](http://localhost:3313)

Full "Getting Started" guide: https://transmute.sh/docs/getting-started/

## What Does Transmute Replace?
*For the record, I love all of these services and use them all frequently. Transmute is not up to par with any of them yet. But it will be!*
| Service | No Size Limits | Private | Free API |
| ------- | -------------- | ------- | -------- |
| [CloudConvert.com](https://cloudconvert.com/) | ❌ | ❌ | ❌ |
| [FreeConvert.com](https://www.freeconvert.com/) | ❌ | ❌ | ❌ |
| [Convertio.co](https://convertio.co/) | ❌ | ❌ | ❌ |
| [Vert.sh](https://vert.sh/) | ✅ | ✅ | ❌ |
| [ConvertX](https://github.com/C4illin/ConvertX) | ✅ | ✅ | ❌ |
| [Transmute](https://transmute.sh) | ✅ | ✅ | ✅ |

## Supported Formats

Transmute supports conversion across a wide range of file types, including images, video, audio, documents, structured data and spreadsheets, subtitles, fonts, and diagrams. The full list of supported formats and conversion pairs is maintained at [transmute.sh/conversions](https://transmute.sh/conversions)

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

Contributions are welcome! See the [contributing guide](https://github.com/transmute-app/transmute?tab=contributing-ov-file) for details.

### Our Awesome Contributors

<a href="https://github.com/transmute-app/transmute/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=transmute-app/transmute" alt="Image with all contributors"/>
</a>

## Star History

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=transmute-app/transmute&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=transmute-app/transmute&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/image?repos=transmute-app/transmute&type=Date" />
</picture>
