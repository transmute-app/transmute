import hashlib
import logging
import os
from pathlib import Path
from urllib.parse import urlparse, unquote

import httpx

from core import sanitize_filename, get_file_extension
from .downloader_interface import DownloaderInterface, DownloadResult, DownloadError

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 300

class HttpDownloader(DownloaderInterface):
    """Downloads files over plain HTTP/HTTPS."""

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    
    def fix_url(self, url: str) -> str:
        """Fixes commonly incorrect URLs, for example change GitHub URLs to raw content URLs."""
        if ((url.startswith("https://github.com") or url.startswith("http://github.com"))
             and not url.endswith(".git") and "/blob/" in url):
            # Convert GitHub blob URLs to raw URLs
            url = url.replace("github.com", "raw.githubusercontent.com", count=1).replace("/blob/", "/", count=1)
        normalized = url.strip()
        return normalized

    async def download(self, url: str, dest_dir: Path, filename_stem: str) -> DownloadResult:
        url = self.fix_url(url)
        original_filename = _extract_filename_from_url(url)
        file_extension = get_file_extension(original_filename)
        unique_filename = filename_stem
        if file_extension:
            unique_filename += f".{file_extension}"

        os.makedirs(dest_dir, exist_ok=True)
        file_path = dest_dir / unique_filename

        hasher = hashlib.sha256()
        size_bytes = 0

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT_SECONDS) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        raise DownloadError(
                            f"Failed to download file: remote server returned {response.status_code}"
                        )
                    with file_path.open("wb") as buffer:
                        async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                            size_bytes += len(chunk)
                            buffer.write(chunk)
                            hasher.update(chunk)
        except DownloadError:
            raise
        except httpx.HTTPError as exc:
            file_path.unlink(missing_ok=True)
            logger.warning("URL download failed for %s: %s", url, exc)
            raise DownloadError(f"Failed to download file from URL: {exc}")

        if size_bytes == 0:
            file_path.unlink(missing_ok=True)
            raise DownloadError("Downloaded file is empty")

        return DownloadResult(
            file_path=file_path,
            original_filename=original_filename,
            size_bytes=size_bytes,
            sha256_checksum=hasher.hexdigest(),
        )


def _extract_filename_from_url(url: str) -> str:
    """Extract a filename from a URL path, falling back to 'download'."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    basename = os.path.basename(path)
    if basename and "." in basename:
        return sanitize_filename(basename)
    return "download"
