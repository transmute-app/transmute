import asyncio
import hashlib

import httpx
import pytest

from downloaders import DownloadError
from downloaders.http_downloader import HttpDownloader


class _FakeResponse:
    def __init__(self, url: str, status_code: int, headers: dict[str, str] | None = None, body: bytes = b""):
        self.url = httpx.URL(url)
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    async def aiter_bytes(self, chunk_size: int = 1024 * 1024):
        del chunk_size
        if self._body:
            yield self._body


class _FakeStreamContext:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeResponse], **kwargs):
        self._responses = responses
        self.kwargs = kwargs
        self.requests: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str, **kwargs):
        del method, kwargs
        self.requests.append(url)
        return _FakeStreamContext(self._responses.pop(0))


def test_validate_public_url_rejects_loopback_literal():
    downloader = HttpDownloader()

    with pytest.raises(DownloadError, match="non-public address"):
        asyncio.run(downloader.validate_public_url("http://127.0.0.1/internal.txt"))


def test_download_revalidates_redirect_targets(monkeypatch, tmp_path):
    downloader = HttpDownloader()
    validated_urls: list[str] = []

    async def fake_validate(self, url: str) -> None:
        del self
        validated_urls.append(url)
        if url == "http://127.0.0.1/secret.txt":
            raise DownloadError("Refusing to download from non-public address: 127.0.0.1")

    responses = [
        _FakeResponse(
            "https://example.com/start.txt",
            302,
            headers={"location": "http://127.0.0.1/secret.txt"},
        )
    ]

    monkeypatch.setattr(HttpDownloader, "validate_public_url", fake_validate)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(responses, **kwargs))

    with pytest.raises(DownloadError, match="non-public address"):
        asyncio.run(downloader.download("https://example.com/start.txt", tmp_path, "abc123"))

    assert validated_urls == [
        "https://example.com/start.txt",
        "http://127.0.0.1/secret.txt",
    ]


def test_download_streams_public_response(monkeypatch, tmp_path):
    downloader = HttpDownloader()
    body = b"public file contents"
    responses = [
        _FakeResponse("https://example.com/file.txt", 200, body=body),
    ]

    async def fake_validate(self, url: str) -> None:
        del self
        assert url == "https://example.com/file.txt"

    monkeypatch.setattr(HttpDownloader, "validate_public_url", fake_validate)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(responses, **kwargs))

    results = asyncio.run(downloader.download("https://example.com/file.txt", tmp_path, "abc123"))

    assert len(results) == 1
    result = results[0]
    assert result.original_filename == "file.txt"
    assert result.size_bytes == len(body)
    assert result.sha256_checksum == hashlib.sha256(body).hexdigest()
    assert result.file_path.read_bytes() == body