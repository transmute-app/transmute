---
title: Pitch
descritpion: Short pitch explaining the what, why, and how of Transmute
created: March 12th, 2026
---

# What is Transmute?
Transmute is a free, open-source, self-hosted file converter built for privacy and flexibility. Convert images, video, audio, documents, spreadsheets, subtitles, fonts, and more entirely on your own infrastructure, with no file size limits and no third-party access to your files.

With a built-in REST API for automated and programmatic access, Transmute fits neatly into existing workflows and systems like the arr-stack, n8n, and Node-RED.

# Why Transmute?
There are plenty of cloud-based file converters out there like CloudConvert, FreeConvert, and Convertio. They’re widely used, but they’re still black boxes: closed-source platforms that give you little control over your files or data. Most also impose file size limits, and none offer a truly free API.

Self-hosted tools exist too, with ConvertX and Vert.sh being two of the better-known options. They’re incredible projects, but they still tend to feel dated, with clunky interfaces that make polished cloud tools hard not to miss. They also lack the API support needed for programmatic conversions.

# How Does Transmute Work?
Transmute is built on a FastAPI (Python) backend, giving it a familiar foundation for local file conversion, a snappy web UI, and programmatic API access. Upload a file and Transmute immediately shows the conversions available for that format, with per-user default actions available for common cases, like converting PNG to JPEG unless you choose otherwise.

Its modular converter architecture keeps new format support easy to extend by building on trusted open-source tools like FFmpeg, PyPandoc, Pillow, and more.