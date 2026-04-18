import inspect
from typing import Type

from downloaders import DownloaderInterface, HttpDownloader
import downloaders


class DownloaderRegistry:
    """Registry that auto-discovers downloader classes and selects one for a URL."""

    def __init__(self) -> None:
        self.downloaders: list[Type[DownloaderInterface]] = []
        self._auto_register()

    def _auto_register(self) -> None:
        for _name, obj in inspect.getmembers(downloaders, inspect.isclass):
            if issubclass(obj, DownloaderInterface) and obj is not DownloaderInterface:
                self.register(obj)

    def register(self, downloader_class: Type[DownloaderInterface]) -> None:
        if downloader_class not in self.downloaders:
            self.downloaders.append(downloader_class)

    def get_downloader_for_url(self, url: str) -> DownloaderInterface:
        """Return an appropriate downloader instance for the given URL.

        For now this always returns an ``HttpDownloader``.  As more
        downloaders are added (e.g. yt-dlp, authenticated) this method
        will inspect the URL and choose the best match.
        """
        if not HttpDownloader().can_handle(url):
            raise ValueError(f"No suitable downloader found for URL: {url}")
        return HttpDownloader()


# Shared singleton — import this instead of instantiating DownloaderRegistry() directly.
downloader_registry = DownloaderRegistry()
