import hashlib
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from .downloader_interface import DownloaderInterface, DownloadResult, DownloadError

logger = logging.getLogger(__name__)

_YOUTUBE_HOSTS = re.compile(
    r"^(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com|m\.youtube\.com)$",
    re.IGNORECASE,
)


class YtDlpDownloader(DownloaderInterface):
    """Downloads media from YouTube URLs using yt-dlp."""

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return _YOUTUBE_HOSTS.match(parsed.netloc) is not None

    async def download(self, url: str, dest_dir: Path, filename_stem: str) -> DownloadResult:
        os.makedirs(dest_dir, exist_ok=True)

        # Use the UUID stem as the output template so filenames are predictable.
        # yt-dlp will append the extension based on the container format.
        output_template = str(dest_dir / f"{filename_stem}.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            # Best single-file format — avoids needing ffmpeg to merge
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "socket_timeout": 60,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            logger.warning("yt-dlp download failed for %s: %s", url, exc)
            raise DownloadError(f"Failed to download from YouTube: {exc}")

        if info is None:
            raise DownloadError("yt-dlp returned no info for the given URL")

        # Determine the actual file written by yt-dlp
        downloaded_path = _find_downloaded_file(dest_dir, filename_stem)
        if downloaded_path is None:
            raise DownloadError("yt-dlp completed but no output file was found")

        original_title = info.get("title", "video")
        ext = downloaded_path.suffix  # includes the dot
        original_filename = _safe_original_filename(original_title, ext)

        size_bytes = downloaded_path.stat().st_size
        if size_bytes == 0:
            downloaded_path.unlink(missing_ok=True)
            raise DownloadError("Downloaded file is empty")

        sha256 = hashlib.sha256()
        with downloaded_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                sha256.update(chunk)

        return DownloadResult(
            file_path=downloaded_path,
            original_filename=original_filename,
            size_bytes=size_bytes,
            sha256_checksum=sha256.hexdigest(),
        )


def _find_downloaded_file(dest_dir: Path, stem: str) -> Path | None:
    """Find the file yt-dlp wrote, matching by UUID stem."""
    for entry in dest_dir.iterdir():
        if entry.is_file() and entry.stem == stem:
            return entry
    # yt-dlp may add format info before the extension (e.g. stem.f137.mp4)
    for entry in dest_dir.iterdir():
        if entry.is_file() and entry.name.startswith(stem):
            return entry
    return None


def _safe_original_filename(title: str, ext: str) -> str:
    """Build a human-readable filename from the video title."""
    # Strip characters that are problematic in filenames
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(". ")
    if not clean:
        clean = "video"
    return clean + ext

