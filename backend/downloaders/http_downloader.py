import asyncio
import hashlib
import ipaddress
import logging
import os
import socket
from pathlib import Path
from urllib.parse import urlparse, unquote

import httpx

from core import sanitize_filename, get_file_extension, get_domain_auth_for_url
from .downloader_interface import DownloaderInterface, DownloadResult, DownloadError

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 300
MAX_REDIRECTS = 5

class HttpDownloader(DownloaderInterface):
    """Downloads files over plain HTTP/HTTPS."""

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    
    def fix_url(self, url: str) -> str:
        """Fixes commonly incorrect URLs, for example change GitHub URLs to raw content URLs."""
        normalized = url.strip()
        parsed = urlparse(normalized)
        if parsed.hostname == "github.com" and not parsed.path.endswith(".git") and "/blob/" in parsed.path:
            # Convert GitHub blob URLs to raw URLs
            normalized = normalized.replace("github.com", "raw.githubusercontent.com", count=1).replace("/blob/", "/", count=1)
        return normalized

    async def validate_public_url(self, url: str) -> None:
        """Reject URLs that resolve to non-public IP addresses."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise DownloadError("Only HTTP and HTTPS URLs are supported")

        hostname = parsed.hostname
        if not hostname:
            raise DownloadError("URL must include a hostname")

        for address in await self._resolve_hostname_ips(hostname, parsed.port):
            if not _is_public_ip(address):
                raise DownloadError(
                    f"Refusing to download from non-public address: {hostname}"
                )

    async def _resolve_hostname_ips(self, hostname: str, port: int | None) -> set[str]:
        try:
            ipaddress.ip_address(hostname)
            return {hostname}
        except ValueError:
            pass

        try:
            loop = asyncio.get_running_loop()
            addrinfo = await loop.getaddrinfo(
                hostname,
                port or 80,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise DownloadError(f"Failed to resolve URL host: {hostname}") from exc

        addresses: set[str] = set()
        for _family, _type, _proto, _canonname, sockaddr in addrinfo:
            if sockaddr:
                addresses.add(sockaddr[0])

        if not addresses:
            raise DownloadError(f"Failed to resolve URL host: {hostname}")

        return addresses

    @staticmethod
    def _request_kwargs(url: str) -> dict:
        domain_auth = get_domain_auth_for_url(url)
        request_kwargs: dict = {}
        if domain_auth is not None:
            if domain_auth.auth is not None:
                request_kwargs["auth"] = domain_auth.auth
            if domain_auth.headers:
                request_kwargs["headers"] = domain_auth.headers
            logger.debug("Applying configured domain auth for %s", domain_auth.domain)
        return request_kwargs

    async def download(self, url: str, dest_dir: Path, filename_stem: str) -> list[DownloadResult]:
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

        client_kwargs: dict = {"follow_redirects": False, "timeout": TIMEOUT_SECONDS}

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                current_url = url
                for _redirect_count in range(MAX_REDIRECTS + 1):
                    await self.validate_public_url(current_url)
                    request_kwargs = self._request_kwargs(current_url)
                    async with client.stream("GET", current_url, **request_kwargs) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise DownloadError("Failed to download file: redirect missing location header")
                            current_url = str(response.url.join(location))
                            continue

                        if response.status_code != 200:
                            raise DownloadError(
                                f"Failed to download file: remote server returned {response.status_code}"
                            )

                        with file_path.open("wb") as buffer:
                            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                                size_bytes += len(chunk)
                                buffer.write(chunk)
                                hasher.update(chunk)
                        break
                else:
                    raise DownloadError("Failed to download file: too many redirects")
        except DownloadError:
            file_path.unlink(missing_ok=True)
            raise
        except httpx.HTTPError as exc:
            file_path.unlink(missing_ok=True)
            logger.warning("URL download failed for %s: %s", url, exc)
            raise DownloadError(f"Failed to download file from URL: {exc}")

        if size_bytes == 0:
            file_path.unlink(missing_ok=True)
            raise DownloadError("Downloaded file is empty")

        return [DownloadResult(
            id=filename_stem,
            file_path=file_path,
            original_filename=original_filename,
            size_bytes=size_bytes,
            sha256_checksum=hasher.hexdigest(),
        )]


def _extract_filename_from_url(url: str) -> str:
    """Extract a filename from a URL path, falling back to 'download'."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    basename = os.path.basename(path)
    if basename and "." in basename:
        return sanitize_filename(basename)
    return "download"


def _is_public_ip(address: str) -> bool:
    ip_obj = ipaddress.ip_address(address)

    if isinstance(ip_obj, ipaddress.IPv6Address):
        if ip_obj.ipv4_mapped is not None:
            ip_obj = ip_obj.ipv4_mapped
        elif ip_obj.sixtofour is not None:
            ip_obj = ip_obj.sixtofour

    return ip_obj.is_global
