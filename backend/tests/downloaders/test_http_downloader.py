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
        self.request_kwargs: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str, **kwargs):
        del method
        self.requests.append(url)
        self.request_kwargs.append(kwargs)
        return _FakeStreamContext(self._responses.pop(0))


def test_validate_public_url_rejects_loopback_literal():
    downloader = HttpDownloader()

    with pytest.raises(DownloadError, match="non-public address"):
        asyncio.run(downloader.validate_public_url("http://127.0.0.1/internal.txt"))


def test_download_revalidates_redirect_targets(monkeypatch, tmp_path):
    downloader = HttpDownloader()
    validated_urls: list[str] = []

    async def fake_validate(self, url: str) -> str:
        del self
        validated_urls.append(url)
        if url == "http://127.0.0.1/secret.txt":
            raise DownloadError("Refusing to download from non-public address: 127.0.0.1")
        return "93.184.216.34"

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

    async def fake_validate(self, url: str) -> str:
        del self
        assert url == "https://example.com/file.txt"
        return "93.184.216.34"

    monkeypatch.setattr(HttpDownloader, "validate_public_url", fake_validate)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(responses, **kwargs))

    results = asyncio.run(downloader.download("https://example.com/file.txt", tmp_path, "abc123"))

    assert len(results) == 1
    result = results[0]
    assert result.original_filename == "file.txt"
    assert result.size_bytes == len(body)
    assert result.sha256_checksum == hashlib.sha256(body).hexdigest()
    assert result.file_path.read_bytes() == body


# --- DNS rebinding (GHSA-8mfq-273g-2cr7) ---------------------------------


def _stub_resolver(monkeypatch, answers: list[str]):
    """Hand out one DNS answer per lookup so rebinding can be simulated."""
    calls = {"n": 0}

    async def fake_resolve(self, hostname: str, port: int | None) -> set[str]:
        del self, hostname, port
        answer = answers[min(calls["n"], len(answers) - 1)]
        calls["n"] += 1
        return {answer}

    monkeypatch.setattr(HttpDownloader, "_resolve_hostname_ips", fake_resolve)
    return calls


def test_download_connects_to_the_validated_address(monkeypatch, tmp_path):
    """The hostname must never be re-resolved after it passes validation."""
    downloader = HttpDownloader()
    body = b"public file contents"
    responses = [_FakeResponse("https://example.com/file.txt", 200, body=body)]

    # A rebinding nameserver: public on the first lookup, loopback after.
    calls = _stub_resolver(monkeypatch, ["93.184.216.34", "127.0.0.1"])

    client_box = {}

    def _make_client(**kwargs):
        client_box["client"] = _FakeAsyncClient(responses, **kwargs)
        return client_box["client"]

    monkeypatch.setattr(httpx, "AsyncClient", _make_client)

    asyncio.run(downloader.download("https://example.com/file.txt", tmp_path, "abc123"))

    # Exactly one resolution, and the connection targets its result.
    assert calls["n"] == 1
    assert client_box["client"].requests == ["https://93.184.216.34/file.txt"]

    sent = client_box["client"].request_kwargs[0]
    assert sent["headers"]["Host"] == "example.com"
    assert sent["extensions"]["sni_hostname"] == "example.com"


def test_download_rejects_host_resolving_to_loopback(monkeypatch, tmp_path):
    downloader = HttpDownloader()
    _stub_resolver(monkeypatch, ["127.0.0.1"])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient([], **kwargs))

    with pytest.raises(DownloadError, match="non-public address"):
        asyncio.run(downloader.download("http://rebind.attacker.test/secret", tmp_path, "abc123"))


def test_pinning_preserves_port_and_brackets_ipv6():
    connect_url, extra = HttpDownloader._pin_to_address(
        "https://example.com:8443/a/b?q=1", "2606:4700::1111"
    )

    assert connect_url == "https://[2606:4700::1111]:8443/a/b?q=1"
    # Host must carry the port so the origin routes the request correctly.
    assert extra["headers"]["Host"] == "example.com:8443"
    assert extra["extensions"]["sni_hostname"] == "example.com"


def test_redirect_target_is_resolved_against_the_logical_url(monkeypatch, tmp_path):
    """A relative redirect must join the hostname URL, not the pinned IP."""
    downloader = HttpDownloader()
    validated: list[str] = []
    body = b"redirected body"

    async def fake_validate(self, url: str) -> str:
        del self
        validated.append(url)
        return "93.184.216.34"

    responses = [
        _FakeResponse("https://93.184.216.34/a/start.txt", 302, headers={"location": "/b/final.txt"}),
        _FakeResponse("https://93.184.216.34/b/final.txt", 200, body=body),
    ]

    monkeypatch.setattr(HttpDownloader, "validate_public_url", fake_validate)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(responses, **kwargs))

    asyncio.run(downloader.download("https://example.com/a/start.txt", tmp_path, "abc123"))

    assert validated == [
        "https://example.com/a/start.txt",
        "https://example.com/b/final.txt",
    ]
