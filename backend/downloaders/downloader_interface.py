from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadResult:
    """Result of a successful download."""
    file_path: Path
    original_filename: str
    size_bytes: int
    sha256_checksum: str


class DownloaderInterface:
    """Base interface for all downloaders.

    Subclasses must implement ``download`` and may override ``can_handle``
    to declare which URLs they support.
    """

    def can_handle(self, url: str) -> bool:
        """Return True if this downloader can handle the given URL."""
        raise NotImplementedError

    async def download(self, url: str, dest_dir: Path, filename_stem: str) -> DownloadResult:
        """Download the resource at *url* into *dest_dir*.

        The implementation should use *filename_stem* (a UUID) as the base of
        the on-disk filename, appending an appropriate extension.

        Returns a ``DownloadResult`` on success.
        Raises ``DownloadError`` on failure.
        """
        raise NotImplementedError


class DownloadError(Exception):
    """Raised when a download fails."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code
