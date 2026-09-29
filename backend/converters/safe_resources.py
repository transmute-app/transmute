"""Resource-fetching policy for HTML-to-PDF rendering.

WeasyPrint's default URL fetcher resolves whatever the document references,
including ``http(s)://`` and ``file://`` URLs. Because the rendered HTML is
built from attacker-controlled uploads, the default fetcher turns any
conversion into a server-side request forgery and local file read primitive.

All legitimate inline media reaches the renderer already inlined as a
``data:`` URI, so the renderer never needs to touch the network or disk.
"""

from urllib.parse import urlparse


class BlockedResourceError(Exception):
    """Raised when a document references a resource the renderer may not fetch."""


def safe_url_fetcher(url: str, timeout: int = 10, ssl_context=None):
    """Allow only self-contained ``data:`` URIs; refuse every other scheme."""
    scheme = urlparse(url).scheme.lower()
    if scheme != 'data':
        raise BlockedResourceError(
            f"Refusing to fetch external resource from rendered document: {scheme or 'relative'}"
        )

    # Imported lazily: WeasyPrint needs native libraries that are absent in some
    # development environments, and this module is imported on non-PDF paths.
    from weasyprint.urls import default_url_fetcher

    return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
