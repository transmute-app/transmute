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
        # HttpDownloader is a generic catch-all; move it to the end so
        # more specific downloaders (e.g. YtDlpDownloader) are tried first.
        if HttpDownloader in self.downloaders:
            self.downloaders.remove(HttpDownloader)
            self.downloaders.append(HttpDownloader)

    def register(self, downloader_class: Type[DownloaderInterface]) -> None:
        if downloader_class not in self.downloaders:
            self.downloaders.append(downloader_class)

    def get_downloader_for_url(self, url: str) -> DownloaderInterface:
        """Return an appropriate downloader instance for the given URL.

        Iterates registered downloaders and returns the first one that
        can handle the URL.
        """
        for downloader_cls in self.downloaders:
            instance = downloader_cls()
            if instance.can_handle(url):
                return instance
        raise ValueError(f"No suitable downloader found for URL: {url}")


# Shared singleton — import this instead of instantiating DownloaderRegistry() directly.
downloader_registry = DownloaderRegistry()
