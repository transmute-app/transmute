import hashlib
import logging
import os
import re
import shutil
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from yt_dlp.extractor import gen_extractors

from .downloader_interface import DownloaderInterface, DownloadResult, DownloadError

logger = logging.getLogger(__name__)


class _YtDlpLogger:
    """Keep the last download error while allowing playlist entries to fail."""

    def __init__(self) -> None:
        self.last_error: str | None = None

    def debug(self, message: str) -> None:
        logger.debug("%s", message)

    def warning(self, message: str) -> None:
        logger.warning("%s", message)

    def error(self, message: str) -> None:
        self.last_error = message
        logger.warning("%s", message)

    def failure_message(self, fallback: str) -> str:
        if self.last_error:
            return f"Failed to download from supported site: {self.last_error}"
        return fallback


@lru_cache(maxsize=1)
def _site_specific_extractors() -> tuple[object, ...]:
    """Return yt-dlp extractors, excluding the generic catch-all extractor."""
    return tuple(
        extractor
        for extractor in gen_extractors()
        if getattr(extractor, "IE_NAME", "").lower() != "generic"
    )


class YtDlpDownloader(DownloaderInterface):
    """Downloads media from site-specific yt-dlp supported URLs.

    Supports single videos as well as playlists — for a playlist, every
    successfully downloaded entry is returned as a separate ``DownloadResult``.
    """

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return any(extractor.suitable(url) for extractor in _site_specific_extractors())

    async def download(self, url: str, dest_dir: Path, filename_stem: str) -> list[DownloadResult]:
        os.makedirs(dest_dir, exist_ok=True)
        download_status = {"status": "unknown"}
        download_logger = _YtDlpLogger()

        # Only treat the URL as a playlist when the user actually pasted a
        # playlist-style URL. A regular watch URL that happens to carry a
        # `list=` parameter (e.g. YouTube showing the surrounding playlist)
        # should still download just the single video the user linked to.
        is_playlist_url = _is_playlist_url(url)

        # Stage yt-dlp downloads in a temp subdirectory so we can reliably
        # pair each output file with its entry metadata before renaming into
        # the final UUID-based layout expected by the rest of the app.
        staging_dir = dest_dir / f".ytdlp_{filename_stem}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Use the yt-dlp video id + playlist index in the staging filename so
        # we can match each entry back to the file it produced.
        output_template = str(staging_dir / "%(playlist_index)s_%(id)s.%(ext)s")

        def _record_download_status(progress: dict) -> None:
            status = progress.get("status")
            if status:
                download_status["status"] = status

        ydl_opts = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [_record_download_status],
            "logger": download_logger,
            # The Python API does not apply yt-dlp's CLI retry defaults.
            "retries": 10,
            "extractor_retries": 3,
            "fragment_retries": 10,
            # Prefer merged mp4+m4a for video sources, fall back to the best
            # available single-file video format, and finally to bestaudio for
            # audio-only sources (e.g. YouTube Music, SoundCloud, Bandcamp).
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestaudio[ext=m4a]/bestaudio/best",
            "merge_output_format": "mp4",
            # Opt into playlist expansion only when the URL is playlist-shaped.
            "noplaylist": not is_playlist_url,
            # Don't abort the whole playlist on a single failed entry.
            "ignoreerrors": True,
            "socket_timeout": 60,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            logger.warning("yt-dlp download failed for %s: %s", url, exc)
            raise DownloadError(f"Failed to download from supported site: {exc}")

        if info is None:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise DownloadError(download_logger.failure_message("yt-dlp returned no info for the given URL"))

        is_playlist = info.get("_type") == "playlist" or "entries" in info
        raw_entries = info.get("entries") if is_playlist else [info]
        entries = [entry for entry in (raw_entries or []) if entry]

        if not entries:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise DownloadError(download_logger.failure_message("yt-dlp completed but no files were downloaded"))

        extractor_key = info.get("extractor_key", "unknown")
        results: list[DownloadResult] = []

        for idx, entry in enumerate(entries):
            video_id = entry.get("id", "")
            staged_path = _find_entry_file(staging_dir, video_id)
            if staged_path is None:
                logger.warning(
                    "yt-dlp entry %s produced no output file, skipping",
                    video_id or entry.get("title", "<unknown>"),
                )
                continue

            # The first file re-uses the caller-provided UUID stem so the DB id
            # matches for single-file downloads; every additional playlist
            # entry gets its own freshly minted UUID.
            file_id = filename_stem if idx == 0 else str(uuid.uuid4())
            ext = staged_path.suffix
            final_path = dest_dir / f"{file_id}{ext}"
            try:
                shutil.move(str(staged_path), str(final_path))
            except OSError as exc:
                logger.warning("Failed to move %s to %s: %s", staged_path, final_path, exc)
                continue

            size_bytes = final_path.stat().st_size
            if size_bytes == 0:
                final_path.unlink(missing_ok=True)
                continue

            sha256 = hashlib.sha256()
            with final_path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    sha256.update(chunk)

            title = entry.get("title") or "video"
            original_filename = _safe_original_filename(title, ext)

            results.append(DownloadResult(
                id=file_id,
                file_path=final_path,
                original_filename=original_filename,
                size_bytes=size_bytes,
                sha256_checksum=sha256.hexdigest(),
            ))

        shutil.rmtree(staging_dir, ignore_errors=True)

        if not results:
            raise DownloadError(download_logger.failure_message("yt-dlp completed but no valid output files were found"))

        logger.info(
            "yt-dlp download: url=%s status=%s extractor=%s files=%d",
            url,
            download_status["status"],
            extractor_key,
            len(results),
        )

        return results


# Path segments that unambiguously indicate a playlist/album/set URL across
# the major yt-dlp-supported sites. A single-video watch URL that merely
# carries a `list=` query param is intentionally excluded so users can share
# a specific video from within a playlist without pulling the whole playlist.
_PLAYLIST_PATH_MARKERS: tuple[str, ...] = (
    "/playlist",       # youtube.com/playlist, music.youtube.com/playlist
    "/playlists/",
    "/album/",         # bandcamp, soundcloud-style album URLs
    "/albums/",
    "/sets/",          # soundcloud sets
    "/set/",
    "/channel/",       # whole-channel URLs behave as playlists on YouTube
    "/c/",
    "/user/",
    "/@",              # youtube @handle canonical URLs
    "/series/",
    "/show/",
)


def _is_playlist_url(url: str) -> bool:
    """Return True if the URL points at a playlist/album rather than a single item."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(marker in path for marker in _PLAYLIST_PATH_MARKERS):
        return True
    # YouTube's dedicated "watch later" and "liked videos" lists have no path
    # of their own — they live at /playlist?list=... which is already covered
    # above. An ordinary /watch URL is treated as a single video even when a
    # `list=` query param is present.
    return False


def _find_entry_file(staging_dir: Path, video_id: str) -> Path | None:
    """Find the file yt-dlp wrote for a given playlist entry id."""
    if not staging_dir.exists():
        return None
    if not video_id:
        for entry in staging_dir.iterdir():
            if entry.is_file():
                return entry
        return None
    # Our staging template embeds %(id)s between the playlist index and
    # the extension, so a substring match on video_id is sufficient.
    for entry in staging_dir.iterdir():
        if entry.is_file() and video_id in entry.name:
            return entry
    return None


def _safe_original_filename(title: str, ext: str) -> str:
    """Build a human-readable filename from the video title."""
    # Strip characters that are problematic in filenames
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(". ")
    if not clean:
        clean = "video"
    return clean + ext
